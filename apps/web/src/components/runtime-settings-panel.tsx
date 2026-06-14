"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  getRuntimeSettings,
  updateRuntimeSettings,
  type RuntimeSettingsPayload,
  type RuntimeSettingsUpdatePayload
} from "@/lib/client-api";

type SaveState = "idle" | "saving" | "saved" | "failed";

const defaultDraft: RuntimeSettingsUpdatePayload = {
  openai_research_enabled: true,
  openai_research_model: "gpt-5.5",
  openai_base_url: "https://api.openai.com/v1",
  openai_timeout_seconds: 20
};

function draftFromSettings(settings: RuntimeSettingsPayload): RuntimeSettingsUpdatePayload {
  return {
    openai_research_enabled: settings.openai_research_enabled,
    openai_research_model: settings.openai_research_model,
    openai_base_url: settings.openai_base_url,
    openai_timeout_seconds: settings.openai_timeout_seconds
  };
}

export function RuntimeSettingsPanel() {
  const [settings, setSettings] = useState<RuntimeSettingsPayload | null>(null);
  const [draft, setDraft] = useState<RuntimeSettingsUpdatePayload>(defaultDraft);
  const [saveState, setSaveState] = useState<SaveState>("idle");

  useEffect(() => {
    let active = true;
    getRuntimeSettings().then((payload) => {
      if (active) {
        setSettings(payload);
        setDraft(draftFromSettings(payload));
      }
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaveState("saving");
    const payload = await updateRuntimeSettings(draft);
    setSettings(payload);
    setDraft(draftFromSettings(payload));
    setSaveState(payload.source === "fallback" ? "failed" : "saved");
  }

  return (
    <section className="data-panel status-panel runtime-settings-panel" aria-label="运行配置">
      <div className="panel-heading">
        <div>
          <h3>运行配置</h3>
          <p>OpenAI Research LLM 与本地运行参数</p>
        </div>
        <span className={settings?.source === "database" ? "status-pill success" : "status-pill neutral"}>
          {settings?.source === "database" ? "已保存" : "默认值"}
        </span>
      </div>

      <form className="settings-form" onSubmit={handleSubmit}>
        <label className="settings-toggle">
          <input
            checked={draft.openai_research_enabled}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                openai_research_enabled: event.target.checked
              }))
            }
            type="checkbox"
          />
          <span>启用 OpenAI Research LLM</span>
        </label>

        <label className="settings-field">
          <span>模型</span>
          <input
            aria-label="模型"
            value={draft.openai_research_model}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                openai_research_model: event.target.value
              }))
            }
          />
        </label>

        <label className="settings-field">
          <span>Base URL</span>
          <input
            aria-label="Base URL"
            value={draft.openai_base_url}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                openai_base_url: event.target.value
              }))
            }
          />
        </label>

        <label className="settings-field">
          <span>超时秒数</span>
          <input
            aria-label="超时秒数"
            inputMode="decimal"
            min={1}
            max={120}
            step={0.5}
            type="number"
            value={draft.openai_timeout_seconds}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                openai_timeout_seconds: Number(event.target.value)
              }))
            }
          />
        </label>

        <article className="module-row settings-secret-row">
          <div>
            <strong>API Key</strong>
            <p>{settings?.openai_api_key_source ?? "环境变量未配置"}</p>
          </div>
          <span className={settings?.openai_api_key_configured ? "state-ok" : "state-warn"}>
            {settings?.openai_api_key_configured ? "已配置" : "未配置"}
          </span>
        </article>

        <div className="settings-actions">
          <button disabled={saveState === "saving"} type="submit">
            {saveState === "saving" ? "保存中" : "保存设置"}
          </button>
          {saveState !== "idle" ? (
            <span className={saveState === "failed" ? "state-warn" : "state-ok"}>
              {saveState === "failed" ? "保存失败" : saveState === "saved" ? "已保存" : "保存中"}
            </span>
          ) : null}
        </div>
      </form>
    </section>
  );
}
