"use client";

import { FormEvent, useState } from "react";
import { Upload } from "lucide-react";
import { importPositionsCsv, type PositionImportPayload } from "@/lib/client-api";

const starterCsv = "ticker,quantity,average_cost\nAAPL,10,165\nMSFT,5,310\n";

export function ImportsWorkspace() {
  const [content, setContent] = useState(starterCsv);
  const [result, setResult] = useState<PositionImportPayload | null>(null);
  const [isImporting, setIsImporting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsImporting(true);
    try {
      const payload = await importPositionsCsv(content);
      setResult(payload);
    } finally {
      setIsImporting(false);
    }
  }

  return (
    <div className="module-view">
      <header className="page-header">
        <div>
          <p>批量导入持仓数据到本地组合</p>
          <h2>数据导入</h2>
        </div>
        <div className="status-pill neutral">CSV</div>
      </header>

      <section className="data-panel workspace-panel" aria-label="持仓导入">
        <div className="panel-heading">
          <div>
            <h3>持仓 CSV</h3>
            <p>支持 ticker、quantity、average_cost 三列</p>
          </div>
        </div>

        <form className="workspace-form import-form" onSubmit={handleSubmit}>
          <label className="workspace-field full-field">
            <span>CSV 内容</span>
            <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={8} spellCheck={false} />
          </label>
          <button className="primary-action" type="submit" disabled={isImporting}>
            <Upload size={15} aria-hidden="true" />
            {isImporting ? "导入中" : "导入持仓"}
          </button>
        </form>

        <div className="import-result" aria-live="polite">
          {result ? (
            <>
              <strong>已导入 {result.imported_count} 条持仓</strong>
              {result.errors.length ? (
                <ul>
                  {result.errors.map((error) => (
                    <li key={`${error.row}-${error.field}-${error.message}`}>
                      第 {error.row} 行 {error.field}：{error.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p>没有发现行级错误。</p>
              )}
            </>
          ) : (
            <p>粘贴 CSV 后点击导入。</p>
          )}
        </div>
      </section>
    </div>
  );
}
