"use client";

import { FormEvent, useEffect, useState } from "react";
import { Save } from "lucide-react";
import { createNote, getNotes, type NotePayload } from "@/lib/client-api";

export function NotesWorkspace() {
  const [notes, setNotes] = useState<NotePayload[]>([]);
  const [ticker, setTicker] = useState("");
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [message, setMessage] = useState("正在读取研究笔记。");
  const [isSaving, setIsSaving] = useState(false);

  async function refreshNotes() {
    const payload = await getNotes();
    setNotes(payload.notes);
    setMessage(payload.notes.length ? "研究笔记已同步。" : "暂无研究笔记。");
  }

  useEffect(() => {
    let active = true;
    getNotes().then((payload) => {
      if (!active) {
        return;
      }
      setNotes(payload.notes);
      setMessage(payload.notes.length ? "研究笔记已同步。" : "暂无研究笔记。");
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalizedTitle = title.trim();
    const normalizedBody = body.trim();
    const normalizedTicker = ticker.trim().toUpperCase();
    if (!normalizedTitle || !normalizedBody) {
      setMessage("请填写标题和正文。");
      return;
    }

    setIsSaving(true);
    setMessage("正在保存笔记。");
    try {
      const saved = await createNote({
        body: normalizedBody,
        ticker: normalizedTicker || null,
        title: normalizedTitle
      });
      if (!saved) {
        setMessage("保存失败，请检查后端 API。");
        return;
      }
      setTicker("");
      setTitle("");
      setBody("");
      await refreshNotes();
    } finally {
      setIsSaving(false);
    }
  }

  return (
    <div className="module-view">
      <header className="page-header">
        <div>
          <p>投研假设、证据和复盘沉淀</p>
          <h2>研究笔记</h2>
        </div>
        <div className="status-pill neutral">{notes.length} 篇</div>
      </header>

      <section className="data-panel workspace-panel" aria-label="研究笔记工作区">
        <div className="panel-heading">
          <div>
            <h3>笔记</h3>
            <p>记录 Ticker 相关结论，保存到本地 SQLite</p>
          </div>
        </div>

        <form className="workspace-form note-form" onSubmit={handleSubmit}>
          <label className="workspace-field">
            <span>Ticker</span>
            <input
              value={ticker}
              onChange={(event) => setTicker(event.target.value.toUpperCase())}
              placeholder="MSFT"
              spellCheck={false}
            />
          </label>
          <label className="workspace-field wide-field">
            <span>标题</span>
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Azure 需求" />
          </label>
          <label className="workspace-field full-field">
            <span>正文</span>
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              placeholder="跟踪云增速、AI capex、利润率和管理层指引。"
              rows={5}
            />
          </label>
          <button className="primary-action" type="submit" disabled={isSaving}>
            <Save size={15} aria-hidden="true" />
            {isSaving ? "保存中" : "保存笔记"}
          </button>
        </form>

        <p className="workspace-message" aria-live="polite">
          {message}
        </p>

        <div className="module-list">
          {notes.map((note) => (
            <article className="module-row note-row" key={note.id}>
              <div>
                <strong>{note.title}</strong>
                <p>
                  {note.ticker ? `${note.ticker} · ` : ""}
                  {note.body}
                </p>
              </div>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}
