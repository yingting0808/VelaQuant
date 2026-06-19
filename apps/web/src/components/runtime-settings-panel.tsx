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
  data_mode: "hybrid",
  sec_user_agent: "VelaQuant research app contact@example.com",
  lean_backtest_timeout_seconds: 600,
  openai_research_enabled: true,
  openai_research_model: "gpt-5.5",
  openai_base_url: "https://api.openai.com/v1",
  openai_timeout_seconds: 20
};

function draftFromSettings(settings: RuntimeSettingsPayload): RuntimeSettingsUpdatePayload {
  return {
    data_mode: settings.data_mode,
    sec_user_agent: settings.sec_user_agent,
    lean_backtest_timeout_seconds: settings.lean_backtest_timeout_seconds,
    openai_research_enabled: settings.openai_research_enabled,
    openai_research_model: settings.openai_research_model,
    openai_base_url: settings.openai_base_url,
    openai_timeout_seconds: settings.openai_timeout_seconds
  };
}

export function RuntimeSettingsPanel() {
  const [settings, setSettings] = useState<RuntimeSettingsPayload | null>(null);
  const [draft, setDraft] = useState<RuntimeSettingsUpdatePayload>(defaultDraft);
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [clearOpenaiApiKey, setClearOpenaiApiKey] = useState(false);
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
    const trimmedOpenaiApiKey = openaiApiKey.trim();
    const payload = await updateRuntimeSettings({
      ...draft,
      clear_openai_api_key: clearOpenaiApiKey,
      ...(trimmedOpenaiApiKey ? { openai_api_key: trimmedOpenaiApiKey } : {})
    });
    setSettings(payload);
    setDraft(draftFromSettings(payload));
    setOpenaiApiKey("");
    setClearOpenaiApiKey(false);
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
        <label className="settings-field">
          <span>数据模式</span>
          <select
            aria-label="数据模式"
            value={draft.data_mode}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                data_mode: event.target.value
              }))
            }
          >
            <option value="hybrid">hybrid · OpenBB + SEC EDGAR</option>
            <option value="openbb_optional">openbb_optional · OpenBB only</option>
            <option value="sec_edgar">sec_edgar · SEC EDGAR + OpenBB</option>
            <option value="mock">mock · development only</option>
          </select>
        </label>

        <label className="settings-field">
          <span>LEAN 超时秒数</span>
          <input
            aria-label="LEAN 超时秒数"
            inputMode="decimal"
            min={30}
            max={3600}
            step={30}
            type="number"
            value={draft.lean_backtest_timeout_seconds}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                lean_backtest_timeout_seconds: Number(event.target.value)
              }))
            }
          />
        </label>

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
          <span>OpenAI API Key</span>
          <input
            aria-label="OpenAI API Key"
            autoComplete="new-password"
            placeholder={settings?.openai_api_key_configured ? "已配置，留空则不变" : "sk-..."}
            type="password"
            value={openaiApiKey}
            onChange={(event) => setOpenaiApiKey(event.target.value)}
          />
        </label>

        <label className="settings-toggle">
          <input
            checked={clearOpenaiApiKey}
            disabled={!settings?.openai_api_key_configured}
            onChange={(event) => setClearOpenaiApiKey(event.target.checked)}
            type="checkbox"
          />
          <span>清除已保存 OpenAI API Key</span>
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
          <span>OpenAI 超时秒数</span>
          <input
            aria-label="OpenAI 超时秒数"
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

        <label className="settings-field">
          <span>SEC User-Agent</span>
          <input
            aria-label="SEC User-Agent"
            value={draft.sec_user_agent}
            onChange={(event) =>
              setDraft((current) => ({
                ...current,
                sec_user_agent: event.target.value
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

        <article className="module-row settings-secret-row">
          <div>
            <strong>每日调度</strong>
            <p>
              {settings
                ? `${settings.paper_scheduler_cron} · ${settings.paper_scheduler_timezone}`
                : "加载中"}
            </p>
          </div>
          <span className={settings?.paper_scheduler_enabled ? "state-ok" : "state-warn"}>
            {settings?.paper_scheduler_enabled ? "已启用" : "未启用"}
          </span>
        </article>

        <article className="module-row settings-secret-row">
          <div>
            <strong>Event Bus</strong>
            <p>
              {settings ? `${settings.event_bus_mode} · ${settings.redis_stream_name}` : "加载中"}
            </p>
          </div>
          <span className={settings?.redis_configured ? "state-ok" : "state-warn"}>
            {settings?.redis_configured ? "Redis 已配置" : "本地内存"}
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
