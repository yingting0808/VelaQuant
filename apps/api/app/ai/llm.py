from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict

from app.ai.schemas import ResearchRequest, ResearchResult, TradePlanDraft
from app.core.config import Settings, get_settings


class OpenAIResearchStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    mode: str
    configured: bool
    available: bool
    model: str
    base_url: str
    message: str


class OpenAIResponsesResearchClient:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        base_url: str,
        timeout_seconds: float = 20.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    def generate_research_result(self, request: ResearchRequest) -> ResearchResult:
        payload = _responses_payload(request, model=self.model)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        client_owner = self._http_client is None
        client = self._http_client or httpx.Client(timeout=self.timeout_seconds)
        try:
            response = client.post(f"{self.base_url}/responses", headers=headers, json=payload)
            if response.status_code in {404, 405}:
                chat_response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=_chat_completions_payload(request, model=self.model),
                )
                chat_response.raise_for_status()
                data = json.loads(extract_chat_completion_text(chat_response.json()))
                return _research_result_from_llm_json(request, data)
        finally:
            if client_owner:
                client.close()
        response.raise_for_status()
        output_text = extract_response_text(response.json())
        data = json.loads(output_text)
        return _research_result_from_llm_json(request, data)


def build_openai_research_client(settings: Settings | None = None) -> OpenAIResponsesResearchClient | None:
    active_settings = settings or get_settings()
    api_key = _openai_api_key(active_settings)
    if not active_settings.openai_research_enabled or not api_key:
        return None
    return OpenAIResponsesResearchClient(
        api_key=api_key,
        model=active_settings.openai_research_model,
        base_url=active_settings.openai_base_url,
        timeout_seconds=active_settings.openai_timeout_seconds,
    )


def build_openai_research_status(settings: Settings | None = None) -> OpenAIResearchStatus:
    active_settings = settings or get_settings()
    api_key = _openai_api_key(active_settings)
    configured = bool(api_key)
    available = active_settings.openai_research_enabled and configured
    if not active_settings.openai_research_enabled:
        message = "OpenAI research LLM is disabled by configuration."
    elif configured:
        message = "OpenAI-compatible research LLM is configured for research explanations only."
    else:
        message = "OpenAI-compatible research LLM is not configured; set AI_STOCKS_OPENAI_API_KEY or OPENAI_API_KEY."
    return OpenAIResearchStatus(
        provider="openai_responses_or_chat_completions",
        mode="research_only",
        configured=configured,
        available=available,
        model=active_settings.openai_research_model,
        base_url=active_settings.openai_base_url,
        message=message,
    )


def extract_response_text(payload: dict[str, Any]) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text

    for item in payload.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if content.get("type") == "output_text" and isinstance(text, str) and text.strip():
                return text
    raise ValueError("OpenAI response did not include output text.")


def extract_chat_completion_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list):
        raise ValueError("Chat completion did not include choices.")
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(content, list):
            joined = "".join(
                item.get("text", "")
                for item in content
                if isinstance(item, dict) and isinstance(item.get("text"), str)
            ).strip()
            if joined:
                return joined
    raise ValueError("Chat completion did not include message content.")


def _openai_api_key(settings: Settings) -> str | None:
    return settings.openai_api_key or os.getenv("OPENAI_API_KEY")


def _research_system_prompt() -> str:
    return (
        "你是 VelaQuant 的投研解释助手。AI 只能输出投研解释、风险观察和人工复核草稿；"
        "禁止输出可执行订单、TradeIntent、仓位指令、风控决策或绕过 Trading Core 的动作。"
        "必须返回符合 schema 的 JSON。"
    )


def _research_user_payload(request: ResearchRequest) -> dict[str, Any]:
    return {
        "ticker": request.ticker.strip().upper(),
        "question": request.question,
        "evidence": [item.model_dump() for item in request.evidence],
    }


def _responses_payload(request: ResearchRequest, *, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "input": [
            {
                "role": "developer",
                "content": _research_system_prompt(),
            },
            {
                "role": "user",
                "content": json.dumps(_research_user_payload(request), ensure_ascii=False),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "velaquant_research_result",
                "strict": True,
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                        "bull_case": {"type": "string"},
                        "bear_case": {"type": "string"},
                        "watch_items": {"type": "array", "items": {"type": "string"}},
                        "entry_condition": {"type": "string"},
                        "invalidation_condition": {"type": "string"},
                        "risk_notes": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": [
                        "summary",
                        "bull_case",
                        "bear_case",
                        "watch_items",
                        "entry_condition",
                        "invalidation_condition",
                        "risk_notes",
                    ],
                },
            }
        },
    }


def _chat_completions_payload(request: ResearchRequest, *, model: str) -> dict[str, Any]:
    return {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    f"{_research_system_prompt()} 只返回一个 JSON object，字段必须包含 summary、bull_case、"
                    "bear_case、watch_items、entry_condition、invalidation_condition、risk_notes。"
                ),
            },
            {
                "role": "user",
                "content": json.dumps(_research_user_payload(request), ensure_ascii=False),
            },
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.2,
    }


def _research_result_from_llm_json(request: ResearchRequest, data: dict[str, Any]) -> ResearchResult:
    return ResearchResult(
        ticker=request.ticker.strip().upper(),
        status="complete_llm",
        summary=_required_text(data, "summary"),
        bull_case=_required_text(data, "bull_case"),
        bear_case=_required_text(data, "bear_case"),
        watch_items=_string_list(data.get("watch_items")),
        evidence_count=len(request.evidence),
        trade_plan_draft=TradePlanDraft(
            entry_condition=_required_text(data, "entry_condition"),
            invalidation_condition=_required_text(data, "invalidation_condition"),
            risk_notes=_string_list(data.get("risk_notes")),
            requires_human_review=True,
        ),
    )


def _required_text(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"LLM response missing required text field: {key}")
    return value.strip()


def _string_list(value: Any) -> list[str]:
    if isinstance(value, str):
        normalized = value.replace("\\r\\n", "\n").replace("\\n", "\n")
        items = [
            _clean_list_item(item)
            for item in re.split(r"[\r\n]+|(?<=[.!?。；;])\s*(?=\d+[.)、]\s*)", normalized)
            if _clean_list_item(item)
        ]
    elif isinstance(value, list):
        items = [str(item).strip() for item in value if str(item).strip()]
    else:
        raise ValueError("LLM response list field must be an array or newline-delimited string.")
    if not items:
        raise ValueError("LLM response list field must not be empty.")
    return items


def _clean_list_item(value: str) -> str:
    return re.sub(r"^\s*(?:[-*]|\d+[.)、])\s*", "", value).strip()
