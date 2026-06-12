"use client";

import { useEffect, useState } from "react";
import { getStrategyLabStatus, type StrategyLabStatusPayload } from "@/lib/client-api";

export function StrategyLabStatusPanel() {
  const [status, setStatus] = useState<StrategyLabStatusPayload | null>(null);

  useEffect(() => {
    let active = true;
    getStrategyLabStatus().then((payload) => {
      if (active) {
        setStatus(payload);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const canRun = status?.can_run_backtests ?? false;

  return (
    <section className="data-panel status-panel" aria-label="策略实验室状态">
      <div className="panel-heading">
        <div>
          <h3>回测环境</h3>
          <p>{status?.summary ?? "正在检查 Docker / Compose / LEAN 状态"}</p>
        </div>
        <span className={canRun ? "status-pill success" : "status-pill warning"}>
          {canRun ? "可回测" : "不可回测"}
        </span>
      </div>

      <div className="module-list">
        {(status?.tools ?? []).map((tool) => (
          <article className="module-row" key={tool.name}>
            <div>
              <strong>{tool.name}</strong>
              <p>{tool.message}</p>
            </div>
            <span className={tool.available ? "state-ok" : "state-warn"}>
              {tool.version ?? "未就绪"}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
