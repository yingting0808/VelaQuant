"use client";

import { useEffect, useState } from "react";
import { getDataSourcesStatus, type DataSourcesStatusPayload } from "@/lib/client-api";

export function DataSourceStatusPanel() {
  const [status, setStatus] = useState<DataSourcesStatusPayload | null>(null);

  useEffect(() => {
    let active = true;
    getDataSourcesStatus().then((payload) => {
      if (active) {
        setStatus(payload);
      }
    });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="data-panel status-panel" aria-label="数据源状态">
      <div className="panel-heading">
        <div>
          <h3>数据源状态</h3>
          <p>区分 Mock、本地 API、SEC EDGAR 和可选 OpenBB 数据层</p>
        </div>
        <span className="status-pill neutral">{status?.provider_mode ?? "加载中"}</span>
      </div>

      <div className="module-list">
        {(status?.data_sources ?? []).map((source) => (
          <article className="module-row" key={`${source.mode}-${source.name}`}>
            <div>
              <strong>{source.name}</strong>
              <p>{source.message}</p>
            </div>
            <span className={source.available ? "state-ok" : "state-warn"}>
              {source.available ? "可用" : "未就绪"}
              {source.version ? ` · ${source.version}` : ""}
            </span>
          </article>
        ))}
      </div>
    </section>
  );
}
