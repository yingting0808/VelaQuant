import json

import httpx

from app.ai.llm import OpenAIResponsesResearchClient, build_openai_research_status, extract_response_text
from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.core.config import Settings


def test_openai_research_status_reports_unconfigured_without_key(monkeypatch):
    monkeypatch.delenv("AI_STOCKS_OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    status = build_openai_research_status(Settings(openai_api_key=None))

    assert status.provider == "openai_responses"
    assert status.available is False
    assert status.configured is False
    assert "not configured" in status.message


def test_openai_responses_client_posts_research_prompt_and_parses_output_text():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["authorization"] = request.headers.get("authorization")
        payload = json.loads(request.content.decode("utf-8"))
        captured["payload"] = payload
        return httpx.Response(
            200,
            json={
                "output_text": json.dumps(
                    {
                        "summary": "AAPL evidence summary.",
                        "bull_case": "Revenue evidence is improving.",
                        "bear_case": "Margins remain a risk.",
                        "watch_items": ["Next filing trend."],
                        "entry_condition": "Human review confirms the thesis.",
                        "invalidation_condition": "Evidence turns negative.",
                        "risk_notes": ["Position sizing must remain capped."],
                    }
                )
            },
        )

    client = OpenAIResponsesResearchClient(
        api_key="test-key",
        model="gpt-5.5",
        base_url="https://api.openai.test/v1",
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    request = ResearchRequest(
        ticker="AAPL",
        question="What should we watch?",
        evidence=[
            EvidenceItemInput(
                title="AAPL filing",
                summary="Revenue grew but margin narrowed.",
                source="mock_filing",
                source_url="https://example.local/aapl",
            )
        ],
    )

    result = client.generate_research_result(request)

    assert captured["url"] == "https://api.openai.test/v1/responses"
    assert captured["authorization"] == "Bearer test-key"
    assert captured["payload"]["model"] == "gpt-5.5"
    assert captured["payload"]["text"]["format"]["type"] == "json_schema"
    assert "AI 只能输出投研解释" in json.dumps(captured["payload"], ensure_ascii=False)
    assert result.status == "complete_llm"
    assert result.summary == "AAPL evidence summary."
    assert result.trade_plan_draft.requires_human_review is True


def test_extract_response_text_reads_nested_responses_output():
    payload = {
        "output": [
            {
                "type": "message",
                "content": [
                    {"type": "output_text", "text": "{\"summary\":\"ok\"}"},
                ],
            }
        ]
    }

    assert extract_response_text(payload) == '{"summary":"ok"}'
