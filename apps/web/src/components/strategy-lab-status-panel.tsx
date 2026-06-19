"use client";

import { useEffect, useState } from "react";
import { Ban, CheckCircle, Eye, RotateCcw } from "lucide-react";
import {
  approveLiveSmallPromotion,
  approveShadowPromotion,
  approveStrategyKill,
  getLiveSmallReviewPacket,
  getAlphaValidationSnapshots,
  getShadowDailyReport,
  getShadowObservationHealth,
  getShadowObservations,
  getStrategyAlphaValidation,
  getStrategyAttribution,
  getStrategyCompetition,
  getStrategyCompetitionSnapshots,
  getStrategyEvaluation,
  getStrategyExecutionAccounts,
  getStrategyLabStatus,
  getStrategyLifecycle,
  getStrategyLifecycleAudit,
  getStrategyRegistry,
  getStrategyRuntime,
  getStrategyVersionControl,
  getShadowReviewPacket,
  getShadowValidation,
  getTradingSystemReadiness,
  reconcileLifecycleWithAlphaValidation,
  recordAlphaValidationSnapshot,
  recordStrategyCompetitionSnapshot,
  recordShadowObservation,
  type AlphaValidationSnapshotHistoryPayload,
  type LiveSmallReviewPayload,
  type ShadowDailyReportPayload,
  type StrategyAlphaValidationPayload,
  type StrategyAttributionPayload,
  type StrategyCompetitionPayload,
  type StrategyCompetitionSnapshotHistoryPayload,
  type StrategyEvaluationPayload,
  type StrategyExecutionAccountsPayload,
  type StrategyLabStatusPayload,
  type StrategyLifecycleAuditPayload,
  type StrategyLifecyclePayload,
  type StrategyRegistryPayload,
  type StrategyRuntimePayload,
  type StrategyVersionControlPayload,
  type ShadowObservationHealthPayload,
  type ShadowObservationSummaryPayload,
  type ShadowReviewPayload,
  type ShadowValidationPayload,
  type TradingSystemReadinessPayload
} from "@/lib/client-api";

export function StrategyLabStatusPanel() {
  const [status, setStatus] = useState<StrategyLabStatusPayload | null>(null);
  const [evaluation, setEvaluation] = useState<StrategyEvaluationPayload | null>(null);
  const [attribution, setAttribution] = useState<StrategyAttributionPayload | null>(null);
  const [registry, setRegistry] = useState<StrategyRegistryPayload | null>(null);
  const [strategyCompetition, setStrategyCompetition] = useState<StrategyCompetitionPayload | null>(null);
  const [strategyCompetitionSnapshots, setStrategyCompetitionSnapshots] =
    useState<StrategyCompetitionSnapshotHistoryPayload | null>(null);
  const [lifecycle, setLifecycle] = useState<StrategyLifecyclePayload | null>(null);
  const [lifecycleAudit, setLifecycleAudit] = useState<StrategyLifecycleAuditPayload | null>(null);
  const [systemReadiness, setSystemReadiness] = useState<TradingSystemReadinessPayload | null>(null);
  const [alphaValidation, setAlphaValidation] = useState<StrategyAlphaValidationPayload | null>(null);
  const [alphaSnapshots, setAlphaSnapshots] = useState<AlphaValidationSnapshotHistoryPayload | null>(null);
  const [versionControl, setVersionControl] = useState<StrategyVersionControlPayload | null>(null);
  const [runtime, setRuntime] = useState<StrategyRuntimePayload | null>(null);
  const [executionAccounts, setExecutionAccounts] = useState<StrategyExecutionAccountsPayload | null>(null);
  const [shadowReview, setShadowReview] = useState<ShadowReviewPayload | null>(null);
  const [shadowObservations, setShadowObservations] = useState<ShadowObservationSummaryPayload | null>(null);
  const [shadowObservationHealth, setShadowObservationHealth] = useState<ShadowObservationHealthPayload | null>(null);
  const [shadowValidation, setShadowValidation] = useState<ShadowValidationPayload | null>(null);
  const [shadowDailyReport, setShadowDailyReport] = useState<ShadowDailyReportPayload | null>(null);
  const [liveSmallReview, setLiveSmallReview] = useState<LiveSmallReviewPayload | null>(null);
  const [isRecordingAlphaSnapshot, setIsRecordingAlphaSnapshot] = useState(false);
  const [isRecordingCompetitionSnapshot, setIsRecordingCompetitionSnapshot] = useState(false);
  const [isRecordingShadow, setIsRecordingShadow] = useState(false);
  const [isApprovingShadow, setIsApprovingShadow] = useState(false);
  const [isApprovingLiveSmall, setIsApprovingLiveSmall] = useState(false);
  const [isApprovingKill, setIsApprovingKill] = useState(false);
  const [isReconcilingLifecycle, setIsReconcilingLifecycle] = useState(false);
  const [shadowApprovalMessage, setShadowApprovalMessage] = useState<string | null>(null);
  const [liveSmallApprovalMessage, setLiveSmallApprovalMessage] = useState<string | null>(null);
  const [killApprovalMessage, setKillApprovalMessage] = useState<string | null>(null);
  const [lifecycleReconcileMessage, setLifecycleReconcileMessage] = useState<string | null>(null);
  const [alphaSnapshotMessage, setAlphaSnapshotMessage] = useState<string | null>(null);
  const [competitionSnapshotMessage, setCompetitionSnapshotMessage] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const setIfActive = <T,>(setter: (payload: T) => void) => (payload: T) => {
      if (active) {
        setter(payload);
      }
    };
    void getStrategyLabStatus().then(setIfActive(setStatus));
    void getStrategyEvaluation().then(setIfActive(setEvaluation));
    void getStrategyAttribution().then(setIfActive(setAttribution));
    void getStrategyRegistry().then(setIfActive(setRegistry));
    void getStrategyCompetition().then(setIfActive(setStrategyCompetition));
    void getStrategyCompetitionSnapshots().then(setIfActive(setStrategyCompetitionSnapshots));
    void getStrategyLifecycle().then(setIfActive(setLifecycle));
    void getStrategyLifecycleAudit().then(setIfActive(setLifecycleAudit));
    void getTradingSystemReadiness().then(setIfActive(setSystemReadiness));
    void getStrategyAlphaValidation().then(setIfActive(setAlphaValidation));
    void getAlphaValidationSnapshots().then(setIfActive(setAlphaSnapshots));
    void getStrategyVersionControl().then(setIfActive(setVersionControl));
    void getStrategyRuntime().then(setIfActive(setRuntime));
    void getStrategyExecutionAccounts().then(setIfActive(setExecutionAccounts));
    void getShadowReviewPacket().then(setIfActive(setShadowReview));
    void getShadowObservations().then(setIfActive(setShadowObservations));
    void getShadowObservationHealth().then(setIfActive(setShadowObservationHealth));
    void getShadowValidation().then(setIfActive(setShadowValidation));
    void getShadowDailyReport().then(setIfActive(setShadowDailyReport));
    void getLiveSmallReviewPacket().then(setIfActive(setLiveSmallReview));
    return () => {
      active = false;
    };
  }, []);

  const canRun = status?.can_run_backtests ?? false;
  const readiness = evaluation?.readiness ?? "insufficient_sample";
  const activeRegistryEntry = registry?.entries.find((item) => item.strategy_id === registry.active_strategy_id) ?? null;
  const registryEntries = registry?.entries.slice(0, 4) ?? [];
  const displayedStrategyCompetition = strategyCompetition ?? strategyCompetitionSnapshots?.latest ?? null;
  const competitionEntries = displayedStrategyCompetition?.entries.slice(0, 4) ?? [];
  const activeVersion = versionControl?.versions.find((item) => item.is_active) ?? null;
  const runtimeEntries = runtime?.entries.slice(0, 4) ?? [];
  const accounts = executionAccounts?.accounts ?? [];
  const lifecycleRules = selectVisibleLifecycleRules(lifecycle?.rules ?? []);
  const alphaBlockers = alphaValidation?.blockers ?? [];
  const topAlphaSnapshotBlocker = alphaSnapshots?.blocker_counts[0] ?? null;
  const topTicker = attribution?.ticker_diagnostics[0] ?? null;
  const volatilityComponent =
    attribution?.expectancy_decomposition.components.find((item) => item.name === "volatility_component") ?? null;
  const timingComponent =
    attribution?.expectancy_decomposition.components.find((item) => item.name === "timing_component") ?? null;
  const riskContributor = attribution?.drawdown.contributors.find((item) => item.name === "risk_overreach") ?? null;
  const primaryRegime =
    attribution?.regime_breakdown.items.find((item) => item.regime === attribution.regime_breakdown.primary_regime) ??
    null;
  const canReconcileLifecycle =
    systemReadiness?.blockers.includes("lifecycle_stage_ahead_of_alpha_validation") ?? false;

  async function handleRecordAlphaSnapshot() {
    setIsRecordingAlphaSnapshot(true);
    setAlphaSnapshotMessage(null);
    try {
      const result = await recordAlphaValidationSnapshot();
      const [snapshotsPayload, alphaPayload] = await Promise.all([
        getAlphaValidationSnapshots(),
        getStrategyAlphaValidation()
      ]);
      setAlphaSnapshots(snapshotsPayload);
      setAlphaValidation(alphaPayload);
      if (result) {
        setAlphaSnapshotMessage(`已记录 ${result.trading_day} Alpha 快照`);
      }
    } finally {
      setIsRecordingAlphaSnapshot(false);
    }
  }

  async function handleRecordCompetitionSnapshot() {
    setIsRecordingCompetitionSnapshot(true);
    setCompetitionSnapshotMessage(null);
    try {
      const result = await recordStrategyCompetitionSnapshot();
      const snapshotsPayload = await getStrategyCompetitionSnapshots();
      setStrategyCompetitionSnapshots(snapshotsPayload);
      if (result) {
        setStrategyCompetition(result);
        setCompetitionSnapshotMessage(`已记录 ${result.trading_day} 策略竞争快照`);
      } else {
        setCompetitionSnapshotMessage("策略竞争快照记录失败，请复核运行态。");
      }
    } finally {
      setIsRecordingCompetitionSnapshot(false);
    }
  }

  async function handleRecordShadowObservation() {
    setIsRecordingShadow(true);
    try {
      await recordShadowObservation();
      const [
        observationsPayload,
        observationHealthPayload,
        validationPayload,
        shadowDailyReportPayload,
        liveSmallReviewPayload,
        systemReadinessPayload
      ] = await Promise.all([
        getShadowObservations(),
        getShadowObservationHealth(),
        getShadowValidation(),
        getShadowDailyReport(),
        getLiveSmallReviewPacket(),
        getTradingSystemReadiness()
      ]);
      setShadowObservations(observationsPayload);
      setShadowObservationHealth(observationHealthPayload);
      setShadowValidation(validationPayload);
      setShadowDailyReport(shadowDailyReportPayload);
      setLiveSmallReview(liveSmallReviewPayload);
      setSystemReadiness(systemReadinessPayload);
    } finally {
      setIsRecordingShadow(false);
    }
  }

  async function handleApproveShadow() {
    setIsApprovingShadow(true);
    setShadowApprovalMessage(null);
    try {
      const result = await approveShadowPromotion({
        approved_by: "manual_review",
        reason: "Reviewed in Strategy Lab."
      });
      if (result) {
        setShadowApprovalMessage(result.summary);
        const [
          lifecyclePayload,
          lifecycleAuditPayload,
          systemReadinessPayload,
          shadowReviewPayload,
          shadowObservationHealthPayload,
          shadowValidationPayload,
          shadowDailyReportPayload,
          liveSmallReviewPayload
        ] = await Promise.all([
          getStrategyLifecycle(),
          getStrategyLifecycleAudit(),
          getTradingSystemReadiness(),
          getShadowReviewPacket(),
          getShadowObservationHealth(),
          getShadowValidation(),
          getShadowDailyReport(),
          getLiveSmallReviewPacket()
        ]);
        setLifecycle(lifecyclePayload);
        setLifecycleAudit(lifecycleAuditPayload);
        setSystemReadiness(systemReadinessPayload);
        setShadowReview(shadowReviewPayload);
        setShadowObservationHealth(shadowObservationHealthPayload);
        setShadowValidation(shadowValidationPayload);
        setShadowDailyReport(shadowDailyReportPayload);
        setLiveSmallReview(liveSmallReviewPayload);
      } else {
        setShadowApprovalMessage("Shadow 批准失败，请复核评审包。");
      }
    } finally {
      setIsApprovingShadow(false);
    }
  }

  async function handleApproveLiveSmall() {
    setIsApprovingLiveSmall(true);
    setLiveSmallApprovalMessage(null);
    try {
      const result = await approveLiveSmallPromotion({
        approved_by: "manual_review",
        reason: "Reviewed in Strategy Lab."
      });
      if (result) {
        setLiveSmallApprovalMessage(result.summary);
        const [
          lifecyclePayload,
          lifecycleAuditPayload,
          systemReadinessPayload,
          shadowDailyReportPayload,
          liveSmallReviewPayload
        ] = await Promise.all([
          getStrategyLifecycle(),
          getStrategyLifecycleAudit(),
          getTradingSystemReadiness(),
          getShadowDailyReport(),
          getLiveSmallReviewPacket()
        ]);
        setLifecycle(lifecyclePayload);
        setLifecycleAudit(lifecycleAuditPayload);
        setSystemReadiness(systemReadinessPayload);
        setShadowDailyReport(shadowDailyReportPayload);
        setLiveSmallReview(liveSmallReviewPayload);
      } else {
        setLiveSmallApprovalMessage("Live-small 批准失败，请复核评审包。");
      }
    } finally {
      setIsApprovingLiveSmall(false);
    }
  }

  async function handleApproveKill() {
    setIsApprovingKill(true);
    setKillApprovalMessage(null);
    try {
      const result = await approveStrategyKill({
        approved_by: "manual_review",
        reason: "Reviewed in Strategy Lab."
      });
      if (result) {
        setKillApprovalMessage(result.summary);
        const [
          lifecyclePayload,
          lifecycleAuditPayload,
          systemReadinessPayload,
          registryPayload,
          runtimePayload
        ] = await Promise.all([
          getStrategyLifecycle(),
          getStrategyLifecycleAudit(),
          getTradingSystemReadiness(),
          getStrategyRegistry(),
          getStrategyRuntime()
        ]);
        setLifecycle(lifecyclePayload);
        setLifecycleAudit(lifecycleAuditPayload);
        setSystemReadiness(systemReadinessPayload);
        setRegistry(registryPayload);
        setRuntime(runtimePayload);
      } else {
        setKillApprovalMessage("策略停用失败，请复核生命周期门禁。");
      }
    } finally {
      setIsApprovingKill(false);
    }
  }

  async function handleReconcileLifecycle() {
    setIsReconcilingLifecycle(true);
    setLifecycleReconcileMessage(null);
    try {
      const result = await reconcileLifecycleWithAlphaValidation();
      if (result) {
        setLifecycleReconcileMessage(result.summary);
        const [
          lifecyclePayload,
          lifecycleAuditPayload,
          systemReadinessPayload,
          shadowReviewPayload,
          shadowObservationsPayload,
          shadowObservationHealthPayload,
          shadowValidationPayload,
          shadowDailyReportPayload,
          liveSmallReviewPayload,
          runtimePayload
        ] = await Promise.all([
          getStrategyLifecycle(),
          getStrategyLifecycleAudit(),
          getTradingSystemReadiness(),
          getShadowReviewPacket(),
          getShadowObservations(),
          getShadowObservationHealth(),
          getShadowValidation(),
          getShadowDailyReport(),
          getLiveSmallReviewPacket(),
          getStrategyRuntime()
        ]);
        setLifecycle(lifecyclePayload);
        setLifecycleAudit(lifecycleAuditPayload);
        setSystemReadiness(systemReadinessPayload);
        setShadowReview(shadowReviewPayload);
        setShadowObservations(shadowObservationsPayload);
        setShadowObservationHealth(shadowObservationHealthPayload);
        setShadowValidation(shadowValidationPayload);
        setShadowDailyReport(shadowDailyReportPayload);
        setLiveSmallReview(liveSmallReviewPayload);
        setRuntime(runtimePayload);
      } else {
        setLifecycleReconcileMessage("生命周期纠偏失败，请复核 readiness blocker。");
      }
    } finally {
      setIsReconcilingLifecycle(false);
    }
  }

  return (
    <>
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

      <section className="data-panel status-panel" aria-label="交易系统运行态">
        <div className="panel-heading">
          <div>
            <h3>交易系统运行态</h3>
            <p>{systemReadiness?.summary ?? "正在读取交易内核运行态。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={systemReadiness?.status === "operational" ? "status-pill success" : "status-pill warning"}>
              {systemReadiness?.status ?? "checking"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleReconcileLifecycle}
              disabled={isReconcilingLifecycle || !canReconcileLifecycle}
            >
              <RotateCcw size={14} aria-hidden="true" />
              {isReconcilingLifecycle ? "纠偏中" : "纠偏到 Paper"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>定时任务 {systemReadiness?.scheduler_running ? "运行中" : "未运行"}</strong>
              <p>下一次 {systemReadiness?.scheduler_next_run_at ?? "未知"}</p>
            </div>
            <span className={systemReadiness?.scheduler_running ? "state-ok" : "state-warn"}>scheduler</span>
          </article>
          <article className="module-row">
            <div>
              <strong>生命周期 {systemReadiness?.lifecycle_stage ?? "unknown"}</strong>
              <p>
                Alpha {systemReadiness?.alpha_ready ? "ready" : "collecting"} · Ledger{" "}
                {systemReadiness?.event_ledger_replay_ready ? "replayable" : "blocked"}
              </p>
            </div>
            <span className={systemReadiness?.shadow_can_record ? "state-ok" : "state-warn"}>
              Shadow {systemReadiness?.shadow_can_record ? "可记录" : "不可记录"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>Event Bus {systemReadiness?.event_bus_mode ?? "unknown"}</strong>
              <p>Redis stream {systemReadiness?.event_bus_stream_length ?? 0} events</p>
            </div>
            <span className={systemReadiness?.event_bus_ready ? "state-ok" : "state-warn"}>
              {systemReadiness?.event_bus_ready ? "stream ok" : "stream blocked"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                事件链完整率 {Math.round((systemReadiness?.event_ledger_traceability_ratio ?? 0) * 100)}%
              </strong>
              <p>
                完整链 {systemReadiness?.event_ledger_complete_order_chain_count ?? 0} · 断链{" "}
                {systemReadiness?.event_ledger_broken_chain_count ?? 0} · 可追溯链{" "}
                {systemReadiness?.event_ledger_traceable_chain_count ?? 0}
              </p>
            </div>
            <span className={(systemReadiness?.event_ledger_broken_chain_count ?? 0) === 0 ? "state-ok" : "state-warn"}>
              ledger trace
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>Shadow 剩余 {systemReadiness?.shadow_remaining_observations ?? 5}</strong>
              <p>Live-small {systemReadiness?.live_small_review_ready ? "可评审" : "未开放"} · 实盘执行关闭</p>
            </div>
            <span className={systemReadiness?.live_or_broker_execution_enabled ? "state-warn" : "state-ok"}>
              broker off
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>手工覆盖 {systemReadiness?.manual_override_isolated ? "已隔离" : "未隔离"}</strong>
              <p>
                手工订单 {systemReadiness?.manual_override_order_count ?? 0} · 手工链{" "}
                {systemReadiness?.manual_override_event_chain_count ?? 0} · Alpha 链{" "}
                {systemReadiness?.alpha_filtered_event_chain_count ?? 0}
              </p>
            </div>
            <span className={systemReadiness?.manual_override_isolated ? "state-ok" : "state-warn"}>
              alpha isolation
            </span>
          </article>
          {(systemReadiness?.blockers ?? []).map((blocker) => (
            <article className="module-row" key={blocker}>
              <div>
                <strong>{blocker}</strong>
                <p>该阻断项解除前，日跑状态不是 operational。</p>
              </div>
              <span className="state-warn">blocker</span>
            </article>
          ))}
          {(systemReadiness?.pending_gates ?? []).slice(0, 4).map((gate) => (
            <article className="module-row" key={gate}>
              <div>
                <strong>{gate}</strong>
                <p>该门禁仍在等待样本或人工评审。</p>
              </div>
              <span className="state-warn">pending</span>
            </article>
          ))}
          {lifecycleReconcileMessage ? (
            <article className="module-row">
              <div>
                <strong>生命周期纠偏结果</strong>
                <p>{lifecycleReconcileMessage}</p>
              </div>
              <span className="state-ok">reconcile</span>
            </article>
          ) : null}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="策略注册表">
        <div className="panel-heading">
          <div>
            <h3>策略注册表</h3>
            <p>{registry?.summary ?? "正在读取策略控制平面。"}</p>
          </div>
          <span className={activeRegistryEntry?.supports_hot_swap ? "status-pill success" : "status-pill warning"}>
            {activeRegistryEntry?.supports_hot_swap ? "可热切换" : "只读"}
          </span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>{activeRegistryEntry?.name ?? "Deterministic Watchlist Strategy"}</strong>
              <p>{registry?.active_strategy_id ?? "deterministic_watchlist_v1"}</p>
            </div>
            <span className="state-ok">评分 {formatNumber(activeRegistryEntry?.ranking_score ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>晋级 {activeRegistryEntry?.promotion_gate ?? "blocked"}</strong>
              <p>
                样本 {activeRegistryEntry?.sample_size ?? 0} · 成交{" "}
                {activeRegistryEntry?.filled_order_count ?? 0} · 环境{" "}
                {activeRegistryEntry?.primary_regime ?? "insufficient_data"}
              </p>
            </div>
            <span className="state-ok">{formatSignedCurrency(activeRegistryEntry?.observed_pnl ?? 0)}</span>
          </article>
          {registryEntries.map((entry) => (
            <article className="module-row" key={`${entry.source}:${entry.strategy_id}`}>
              <div>
                <strong>
                  #{entry.rank} {entry.name}
                </strong>
                <p>
                  {entry.strategy_id} · {entry.source} · {entry.execution_mode}
                </p>
              </div>
              <span className={entry.status === "active" ? "state-ok" : "state-warn"}>
                {entry.backtest_status ?? entry.readiness}
              </span>
            </article>
          ))}
          <article className="module-row">
            <div>
              <strong>控制缺口 {registry?.missing_capabilities.length ?? 0}</strong>
              <p>{(registry?.missing_capabilities ?? []).slice(0, 2).join(" / ") || "控制层缺口已补齐。"}</p>
            </div>
            <span className={activeRegistryEntry?.supports_live ? "state-ok" : "state-warn"}>
              {activeRegistryEntry?.supports_live ? "可实盘" : "实盘关闭"}
            </span>
          </article>
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="策略竞争层">
        <div className="panel-heading">
          <div>
            <h3>策略竞争层</h3>
            <p>{displayedStrategyCompetition?.summary ?? "正在读取策略池排名和资金分配建议。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={displayedStrategyCompetition?.competition_ready ? "status-pill success" : "status-pill warning"}>
              {displayedStrategyCompetition?.status ?? "checking"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleRecordCompetitionSnapshot}
              disabled={isRecordingCompetitionSnapshot}
            >
              <CheckCircle size={14} aria-hidden="true" />
              {isRecordingCompetitionSnapshot ? "记录中" : "记录竞争快照"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>策略池 {displayedStrategyCompetition?.strategy_count ?? 0}</strong>
              <p>
                可分配 {displayedStrategyCompetition?.allocatable_strategy_count ?? 0} · 选中{" "}
                {displayedStrategyCompetition?.selected_strategy_id ?? "无"}
              </p>
            </div>
            <span className={displayedStrategyCompetition?.competition_ready ? "state-ok" : "state-warn"}>
              {displayedStrategyCompetition?.trading_day ?? "unknown"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>竞争账本 {strategyCompetitionSnapshots?.snapshot_count ?? 0} 天</strong>
              <p>
                最新 {strategyCompetitionSnapshots?.latest?.trading_day ?? "无"} · 可分配{" "}
                {strategyCompetitionSnapshots?.latest?.allocatable_strategy_count ?? 0}
              </p>
            </div>
            <span className={strategyCompetitionSnapshots?.latest?.competition_ready ? "state-ok" : "state-warn"}>
              {strategyCompetitionSnapshots?.latest ? `快照 ${strategyCompetitionSnapshots.latest.status}` : "no snapshot"}
            </span>
          </article>
          {competitionEntries.map((entry) => (
            <article className="module-row" key={`${entry.source}:${entry.strategy_id}:${entry.version}`}>
              <div>
                <strong>
                  #{entry.rank} {entry.name}
                </strong>
                <p>
                  {entry.strategy_id} · {entry.source} · {entry.execution_mode}
                </p>
                <p>
                  {entry.recommended_action} · {entry.blockers.join(" / ") || "no blockers"}
                </p>
                <p>
                  成交 {entry.filled_order_count}/30 · 还差 {entry.filled_order_remaining} 笔 · 排名分{" "}
                  {formatNumber(entry.ranking_score)}
                </p>
              </div>
              <span className={entry.eligible_for_allocation ? "state-ok" : "state-warn"}>
                allocation {formatPercent(entry.allocation_weight)}
              </span>
            </article>
          ))}
          {competitionSnapshotMessage ? (
            <article className="module-row">
              <div>
                <strong>竞争快照</strong>
                <p>{competitionSnapshotMessage}</p>
              </div>
              <span className="state-ok">snapshot</span>
            </article>
          ) : null}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="策略控制平面">
        <div className="panel-heading">
          <div>
            <h3>控制平面</h3>
            <p>{runtime?.summary ?? "正在读取策略 runtime 和版本绑定。"}</p>
          </div>
          <span className="status-pill success">
            {runtime?.winner ? `${runtime.winner.strategy_id}@${runtime.winner.version}` : "无 winner"}
          </span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                当前版本 {versionControl?.active_version ?? "v1"}
              </strong>
              <p>
                上一版本 {versionControl?.previous_version ?? "无"} · 参数{" "}
                {activeVersion?.parameters_json ?? "{\"notional\": 2000}"}
              </p>
            </div>
            <span className="state-ok">版本 {versionControl?.versions.length ?? 1}</span>
          </article>
          {runtimeEntries.map((entry) => (
            <article className="module-row" key={`${entry.strategy_id}:${entry.version}`}>
              <div>
                <strong>
                  #{entry.rank} {entry.strategy_id}@{entry.version}
                </strong>
                <p>{entry.block_reason ?? "runtime eligible"}</p>
              </div>
              <span className={entry.eligible ? "state-ok" : "state-warn"}>
                {formatNumber(entry.ranking_score)}
              </span>
            </article>
          ))}
          {accounts.map((account) => (
            <article className="module-row" key={`${account.strategy_id}:${account.mode}`}>
              <div>
                <strong>{account.mode}</strong>
                <p>
                  {account.strategy_id} · 起始 {formatCurrency(account.starting_cash)}
                </p>
              </div>
              <span className="state-ok">{formatCurrency(account.cash)}</span>
            </article>
          ))}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="策略生命周期">
        <div className="panel-heading">
          <div>
            <h3>策略生命周期</h3>
            <p>{lifecycle?.summary ?? "正在读取生命周期门禁。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={lifecycle?.gate_status === "eligible" ? "status-pill success" : "status-pill warning"}>
              {lifecycle?.gate_status ?? "watch"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleApproveKill}
              disabled={isApprovingKill || !(lifecycle?.can_kill ?? false)}
            >
              <Ban size={14} aria-hidden="true" />
              {isApprovingKill ? "停用中" : "停用策略"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                {lifecycle?.current_stage ?? "paper"} → {lifecycle?.recommended_stage ?? "paper"}
              </strong>
              <p>{lifecycle?.recommended_action ?? "continue_collecting_samples"}</p>
            </div>
            <span className={lifecycle?.can_promote ? "state-ok" : "state-warn"}>
              {lifecycle?.can_promote ? "可复核晋级" : "禁止晋级"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>自动动作 {lifecycle?.auto_actions_enabled ? "开启" : "关闭"}</strong>
              <p>{lifecycle?.promotion_gate ?? "blocked"}</p>
            </div>
            <span className={lifecycle?.can_kill ? "state-warn" : "state-ok"}>
              {lifecycle?.can_kill ? "淘汰复核" : "继续观察"}
            </span>
          </article>
          {lifecycleRules.map((rule) => (
            <article className="module-row" key={rule.name}>
              <div>
                <strong>
                  {rule.passed ? "通过" : "阻断"} {rule.name}
                </strong>
                <p>
                  {rule.actual} / {rule.required}
                </p>
              </div>
              <span className={rule.passed ? "state-ok" : "state-warn"}>{rule.severity}</span>
            </article>
          ))}
          <article className="module-row">
            <div>
              <strong>生命周期缺口 {lifecycle?.missing_capabilities.length ?? 0}</strong>
              <p>{(lifecycle?.missing_capabilities ?? []).slice(0, 2).join(" / ") || "生命周期适配已补齐。"}</p>
            </div>
            <span className="state-ok">受控</span>
          </article>
          {killApprovalMessage ? (
            <article className="module-row">
              <div>
                <strong>停用结果</strong>
                <p>{killApprovalMessage}</p>
              </div>
              <span className="state-warn">manual</span>
            </article>
          ) : null}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="生命周期审计">
        <div className="panel-heading">
          <div>
            <h3>生命周期审计</h3>
            <p>{lifecycleAudit?.summary ?? "正在读取生命周期审计。"}</p>
          </div>
          <span className={(lifecycleAudit?.items.length ?? 0) > 0 ? "status-pill success" : "status-pill warning"}>
            {(lifecycleAudit?.items.length ?? 0) > 0 ? "有记录" : "无记录"}
          </span>
        </div>

        <div className="module-list compact-list">
          {(lifecycleAudit?.items ?? []).slice(0, 5).map((item) => (
            <article className="module-row" key={item.id}>
              <div>
                <strong>
                  {item.previous_stage ?? "unknown"} → {item.current_stage ?? "unknown"}
                </strong>
                <p>
                  {item.action} · {item.approved_by ?? "unknown"} · {item.reason ?? "无说明"}
                </p>
              </div>
              <span className={lifecycleAuditBadgeClass(item)}>
                {lifecycleAuditBadgeLabel(item)}
              </span>
            </article>
          ))}
          {(lifecycleAudit?.items.length ?? 0) === 0 ? (
            <article className="module-row">
              <div>
                <strong>暂无审批记录</strong>
                <p>Shadow / live-small 审批会在这里留下审计轨迹。</p>
              </div>
              <span className="state-warn">audit</span>
            </article>
          ) : null}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Shadow 评审包">
        <div className="panel-heading">
          <div>
            <h3>Shadow 评审包</h3>
            <p>{shadowReview?.summary ?? "正在生成 Shadow 人工评审材料。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={shadowReview?.can_request_shadow_review ? "status-pill success" : "status-pill warning"}>
              {shadowReview?.status ?? "blocked"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleApproveShadow}
              disabled={isApprovingShadow || !(shadowReview?.can_request_shadow_review ?? false)}
            >
              <CheckCircle size={14} aria-hidden="true" />
              {isApprovingShadow ? "批准中" : "批准进入 Shadow"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                {shadowReview?.strategy_id ?? "deterministic_watchlist_v1"} →{" "}
                {shadowReview?.recommended_stage ?? "paper"}
              </strong>
              <p>自动晋级 {shadowReview?.auto_promotion_enabled ? "开启" : "关闭"}</p>
            </div>
            <span className={shadowReview?.can_request_shadow_review ? "state-ok" : "state-warn"}>
              {shadowReview?.can_request_shadow_review ? "可提交评审" : "继续验证"}
            </span>
          </article>
          {(shadowReview?.checklist ?? []).map((item) => (
            <article className="module-row" key={item.code}>
              <div>
                <strong>
                  {item.passed ? "通过" : "阻断"} {item.label}
                </strong>
                <p>{item.evidence.join(" / ") || item.code}</p>
              </div>
              <span className={item.passed ? "state-ok" : "state-warn"}>{item.code}</span>
            </article>
          ))}
          {(shadowReview?.residual_risks ?? []).map((risk) => (
            <article className="module-row" key={risk.code}>
              <div>
                <strong>{risk.detail}</strong>
                <p>{risk.evidence.join(" / ") || risk.code}</p>
              </div>
              <span className={risk.severity === "info" ? "state-ok" : "state-warn"}>{risk.severity}</span>
            </article>
          ))}
          {shadowApprovalMessage ? (
            <article className="module-row">
              <div>
                <strong>批准结果</strong>
                <p>{shadowApprovalMessage}</p>
              </div>
              <span className="state-ok">manual</span>
            </article>
          ) : null}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Shadow 观察">
        <div className="panel-heading">
          <div>
            <h3>Shadow 观察</h3>
            <p>{shadowObservations?.summary ?? "正在读取 Shadow 观察记录。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={shadowObservations?.can_record_shadow_observation ? "status-pill success" : "status-pill warning"}>
              {shadowObservations?.can_record_shadow_observation ? "可记录" : "未就绪"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleRecordShadowObservation}
              disabled={isRecordingShadow || !(shadowObservations?.can_record_shadow_observation ?? false)}
            >
              <Eye size={14} aria-hidden="true" />
              {isRecordingShadow ? "记录中" : "记录观察"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>{shadowObservations?.latest?.status ?? "暂无观察"}</strong>
              <p>
                交易日 {shadowObservations?.latest?.trading_day ?? "未记录"} · 阻断{" "}
                {shadowObservations?.latest?.blocked_reason ?? "无"}
              </p>
            </div>
            <span className="state-ok">{shadowObservations?.items.length ?? 0} 条</span>
          </article>
          {(shadowObservations?.items ?? []).slice(0, 5).map((item) => (
            <article className="module-row" key={item.id}>
              <div>
                <strong>
                  {item.trading_day} · {item.status}
                </strong>
                <p>
                  intent {item.observed_intent_count} / would-route {item.would_route_order_count} / chain{" "}
                  {item.event_chain_count}
                </p>
              </div>
              <span className={item.can_request_shadow_review ? "state-ok" : "state-warn"}>
                residual {item.residual_risk_count}
              </span>
            </article>
          ))}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Shadow 日报">
        <div className="panel-heading">
          <div>
            <h3>Shadow 日报</h3>
            <p>{shadowDailyReport?.summary ?? "正在生成 Shadow 每日复盘。"}</p>
          </div>
          <span className={shadowDailyReport?.status === "ready_for_manual_review" ? "status-pill success" : "status-pill warning"}>
            {shadowDailyReport?.status ?? "collecting"}
          </span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                交易日 {shadowDailyReport?.trading_day ?? "未记录"} · observation{" "}
                {shadowDailyReport?.observation_status ?? "not_recorded"}
              </strong>
              <p>
                health {shadowDailyReport?.health_status ?? "collecting"} · validation{" "}
                {shadowDailyReport?.validation_status ?? "collecting"} · live-small{" "}
                {shadowDailyReport?.live_small_status ?? "blocked"}
              </p>
            </div>
            <span className={shadowDailyReport?.live_or_broker_execution_enabled ? "state-warn" : "state-ok"}>
              broker {shadowDailyReport?.live_or_broker_execution_enabled ? "on" : "off"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                intent {shadowDailyReport?.observed_intent_count ?? 0} / would-route{" "}
                {shadowDailyReport?.would_route_order_count ?? 0} / chain {shadowDailyReport?.event_chain_count ?? 0}
              </strong>
              <p>
                残余风险 {shadowDailyReport?.residual_risk_count ?? 0} · 剩余样本{" "}
                {shadowDailyReport?.remaining_observations ?? 5}
              </p>
            </div>
            <span className={(shadowDailyReport?.remaining_observations ?? 5) === 0 ? "state-ok" : "state-warn"}>
              sample
            </span>
          </article>
          {(shadowDailyReport?.next_actions ?? []).slice(0, 3).map((action) => (
            <article className="module-row" key={action.action_code}>
              <div>
                <strong>{action.title}</strong>
                <p>{action.detail}</p>
              </div>
              <span className="state-warn">{action.action_code}</span>
            </article>
          ))}
          {(shadowDailyReport?.warnings ?? []).map((warning) => (
            <article className="module-row" key={`warning:${warning}`}>
              <div>
                <strong>{warning}</strong>
                <p>该提示会进入 Shadow 日报，作为 live-small 评审前的复盘证据。</p>
              </div>
              <span className="state-warn">warning</span>
            </article>
          ))}
          {(shadowDailyReport?.blockers ?? []).map((blocker) => (
            <article className="module-row" key={`blocker:${blocker}`}>
              <div>
                <strong>{blocker}</strong>
                <p>该阻断项解除前，不提交 live-small 人工评审。</p>
              </div>
              <span className="state-warn">blocker</span>
            </article>
          ))}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Shadow 健康">
        <div className="panel-heading">
          <div>
            <h3>Shadow 健康</h3>
            <p>{shadowObservationHealth?.summary ?? "正在计算 Shadow 观察质量。"}</p>
          </div>
          <span className={shadowObservationHealth?.sample_ready ? "status-pill success" : "status-pill warning"}>
            {shadowObservationHealth?.status ?? "collecting"}
          </span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                样本 {shadowObservationHealth?.observing_count ?? 0} / 连续{" "}
                {shadowObservationHealth?.consecutive_observing_count ?? 0}
              </strong>
              <p>
                最新交易日 {shadowObservationHealth?.latest_trading_day ?? "未记录"} · 阻断{" "}
                {shadowObservationHealth?.blocked_count ?? 0}
              </p>
            </div>
            <span className={shadowObservationHealth?.sample_ready ? "state-ok" : "state-warn"}>
              {shadowObservationHealth?.sample_ready ? "sample ready" : "collecting"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>平均 would-route {formatNumber(shadowObservationHealth?.average_would_route_order_count ?? 0)}</strong>
              <p>
                事件链 {formatNumber(shadowObservationHealth?.average_event_chain_count ?? 0)} · 残余风险{" "}
                {formatNumber(shadowObservationHealth?.average_residual_risk_count ?? 0)}
              </p>
            </div>
            <span className="state-ok">quality</span>
          </article>
          {(shadowObservationHealth?.warnings ?? []).map((warning) => (
            <article className="module-row" key={warning}>
              <div>
                <strong>{warning}</strong>
                <p>该提示解除前，不开放 live-small 样本通过。</p>
              </div>
              <span className="state-warn">warning</span>
            </article>
          ))}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Shadow 验证">
        <div className="panel-heading">
          <div>
            <h3>Shadow 验证</h3>
            <p>{shadowValidation?.summary ?? "正在计算 Shadow 到 live-small 的人工门禁。"}</p>
          </div>
          <span className={shadowValidation?.shadow_ready ? "status-pill success" : "status-pill warning"}>
            {shadowValidation?.status ?? "collecting"}
          </span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                观察样本 {shadowValidation?.observing_count ?? 0} /{" "}
                {shadowValidation?.min_observations_required ?? 5}
              </strong>
              <p>
                剩余 {shadowValidation?.remaining_observations ?? 5} 次 · 最新交易日{" "}
                {shadowValidation?.latest_trading_day ?? "未记录"}
              </p>
            </div>
            <span className={shadowValidation?.shadow_ready ? "state-ok" : "state-warn"}>
              {shadowValidation?.shadow_ready ? "可人工复核" : "继续观察"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>阻断观察 {shadowValidation?.blocked_count ?? 0}</strong>
              <p>残余风险记录 {shadowValidation?.residual_risk_count ?? 0}</p>
            </div>
            <span className={(shadowValidation?.blocked_count ?? 0) === 0 ? "state-ok" : "state-warn"}>
              gate
            </span>
          </article>
          {(shadowValidation?.blockers ?? []).map((blocker) => (
            <article className="module-row" key={blocker}>
              <div>
                <strong>{blocker}</strong>
                <p>该阻断项解除前，不进入 live-small 评审。</p>
              </div>
              <span className="state-warn">blocker</span>
            </article>
          ))}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Live-small 评审包">
        <div className="panel-heading">
          <div>
            <h3>Live-small 评审包</h3>
            <p>{liveSmallReview?.summary ?? "正在生成 live-small 人工评审材料。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={liveSmallReview?.can_request_live_small_review ? "status-pill success" : "status-pill warning"}>
              {liveSmallReview?.status ?? "blocked"}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleApproveLiveSmall}
              disabled={isApprovingLiveSmall || !(liveSmallReview?.can_request_live_small_review ?? false)}
            >
              <CheckCircle size={14} aria-hidden="true" />
              {isApprovingLiveSmall ? "批准中" : "批准进入 Live-small"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>
                {liveSmallReview?.strategy_id ?? "deterministic_watchlist_v1"} →{" "}
                {liveSmallReview?.recommended_stage ?? "shadow"}
              </strong>
              <p>自动晋级 {liveSmallReview?.auto_promotion_enabled ? "开启" : "关闭"}</p>
            </div>
            <span className={liveSmallReview?.can_request_live_small_review ? "state-ok" : "state-warn"}>
              {liveSmallReview?.can_request_live_small_review ? "可人工评审" : "继续 Shadow"}
            </span>
          </article>
          {(liveSmallReview?.checklist ?? []).map((item) => (
            <article className="module-row" key={item.code}>
              <div>
                <strong>
                  {item.passed ? "通过" : "阻断"} {item.label}
                </strong>
                <p>{item.evidence.join(" / ") || item.code}</p>
              </div>
              <span className={item.passed ? "state-ok" : "state-warn"}>{item.code}</span>
            </article>
          ))}
          {(liveSmallReview?.residual_risks ?? []).map((risk) => (
            <article className="module-row" key={risk.code}>
              <div>
                <strong>{risk.detail}</strong>
                <p>{risk.evidence.join(" / ") || risk.code}</p>
              </div>
              <span className={risk.severity === "info" ? "state-ok" : "state-warn"}>{risk.severity}</span>
            </article>
          ))}
          {liveSmallApprovalMessage ? (
            <article className="module-row">
              <div>
                <strong>批准结果</strong>
                <p>{liveSmallApprovalMessage}</p>
              </div>
              <span className="state-ok">manual</span>
            </article>
          ) : null}
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="归因分析">
        <div className="panel-heading">
          <div>
            <h3>归因分析</h3>
            <p>{attribution?.summary ?? "正在读取策略归因。"}</p>
          </div>
          <span className="status-pill warning">{attribution?.regime.regime ?? "insufficient_data"}</span>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>可行动信号 {formatPercent(attribution?.signal_quality.actionable_signal_rate ?? 0)}</strong>
              <p>
                事件 {attribution?.signal_quality.market_event_count ?? 0} / 意图{" "}
                {attribution?.signal_quality.trade_intent_count ?? 0}
              </p>
            </div>
            <span className="state-ok">
              置信 {formatPercent(attribution?.signal_quality.average_confidence ?? 0)}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>误报率 {formatPercent(attribution?.signal_quality.false_positive_rate ?? 0)}</strong>
              <p>{attribution?.regime.basis ?? "等待复盘样本。"}</p>
            </div>
            <span className="state-warn">复盘 {attribution?.regime.review_count ?? 0}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>观测盈亏 {formatCurrency(attribution?.expectancy_decomposition.total_observed_pnl ?? 0)}</strong>
              <p>
                已实现 {formatCurrency(attribution?.expectancy_decomposition.realized_pnl ?? 0)} / 浮动{" "}
                {formatCurrency(attribution?.expectancy_decomposition.unrealized_pnl ?? 0)}
              </p>
            </div>
            <span className="state-ok">回撤 {formatPercent(attribution?.drawdown.max_drawdown ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>{attribution?.drawdown.source ?? "insufficient_data"}</strong>
              <p>{attribution?.drawdown.basis ?? "等待更多复盘样本。"}</p>
            </div>
            <span className="state-warn">警告 {attribution?.data_quality_warnings.length ?? 0}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                {topTicker?.ticker ?? "暂无 Ticker"} 贡献 {formatSignedCurrency(topTicker?.observed_pnl ?? 0)}
              </strong>
              <p>
                事件 {topTicker?.market_event_count ?? 0} / 意图 {topTicker?.trade_intent_count ?? 0} · 误报{" "}
                {formatPercent(topTicker?.false_positive_rate ?? 0)} · 候选分{" "}
                {topTicker?.latest_candidate_score == null
                  ? "暂无"
                  : `${formatNumber(topTicker.latest_candidate_score)} / 均值 ${formatNumber(
                      topTicker.average_candidate_score
                    )}`}
              </p>
            </div>
            <span className={scorePnlAlignmentBadgeClass(topTicker?.score_pnl_alignment)}>
              {scorePnlAlignmentLabel(topTicker?.score_pnl_alignment)} · 置信{" "}
              {formatPercent(topTicker?.average_confidence ?? 0)}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                衰减 {attribution?.signal_decay.stale_open_position_count ?? 0} /{" "}
                {attribution?.signal_decay.open_position_count ?? 0}
              </strong>
              <p>{attribution?.signal_decay.basis ?? "等待持仓和订单样本。"}</p>
            </div>
            <span className="state-warn">
              持仓 {formatNumber(attribution?.signal_decay.average_holding_days ?? 0)} 天
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                {volatilityComponent?.name ?? "volatility_component"}{" "}
                {formatSignedCurrency(volatilityComponent?.value ?? 0)}
              </strong>
              <p>{volatilityComponent?.basis ?? "等待波动环境组件样本。"}</p>
            </div>
            <span className="state-warn">高波动桶</span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                {timingComponent?.name ?? "timing_component"} {formatSignedCurrency(timingComponent?.value ?? 0)}
              </strong>
              <p>{timingComponent?.basis ?? "等待时点组件样本。"}</p>
            </div>
            <span className="state-warn">
              {riskContributor?.name ?? "risk_overreach"} {formatNumber(riskContributor?.value ?? 0)}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>市场环境 {primaryRegime?.regime ?? "insufficient_data"}</strong>
              <p>
                Ticker {primaryRegime?.ticker_count ?? 0} · 贡献{" "}
                {formatSignedCurrency(primaryRegime?.observed_pnl ?? 0)}
              </p>
            </div>
            <span className="state-ok">
              收益 {formatPercent(primaryRegime?.average_return ?? 0)} / 波动{" "}
              {formatPercent(primaryRegime?.average_volatility ?? 0)} / Sharpe{" "}
              {formatNumber(primaryRegime?.sharpe_proxy ?? 0)}
            </span>
          </article>
        </div>
      </section>

      <section className="data-panel status-panel" aria-label="Alpha 验证">
        <div className="panel-heading">
          <div>
            <h3>Alpha 验证</h3>
            <p>{alphaValidation?.summary ?? evaluation?.notes ?? "正在读取策略评价。"}</p>
          </div>
          <div className="panel-heading-actions">
            <span className={alphaValidation?.alpha_ready ? "status-pill success" : "status-pill warning"}>
              {alphaValidation?.validation_level ?? readiness}
            </span>
            <button
              className="ghost-action"
              type="button"
              onClick={handleRecordAlphaSnapshot}
              disabled={isRecordingAlphaSnapshot}
            >
              <CheckCircle size={14} aria-hidden="true" />
              {isRecordingAlphaSnapshot ? "记录中" : "记录快照"}
            </button>
          </div>
        </div>

        <div className="module-list compact-list">
          <article className="module-row">
            <div>
              <strong>{evaluation?.strategy_name ?? "Deterministic Watchlist Strategy"}</strong>
              <p>{evaluation?.promotion_gate ?? "blocked"}</p>
            </div>
            <span className="state-ok">样本 {evaluation?.sample_size ?? 0}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>信号精度 {formatPercent(evaluation?.signal_precision ?? 0)}</strong>
              <p>成交 {evaluation?.filled_order_count ?? 0} / 拒单 {evaluation?.rejected_order_count ?? 0}</p>
            </div>
            <span className="state-ok">期望 {formatNumber(evaluation?.expectancy ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>
                连续正期望 {alphaValidation?.consecutive_positive_expectancy_days ?? 0} / 5 天
              </strong>
              <p>
                复盘 {alphaValidation?.review_day_count ?? 0} · 最新{" "}
                {formatNumber(alphaValidation?.latest_expectancy ?? 0)} · 平均{" "}
                {formatNumber(alphaValidation?.average_expectancy ?? 0)}
              </p>
            </div>
            <span className={alphaValidation?.alpha_ready ? "state-ok" : "state-warn"}>
              {alphaValidation?.alpha_ready ? "验证通过" : "继续模拟"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>最大回撤 {formatPercent(evaluation?.max_drawdown ?? 0)}</strong>
              <p>事件链 {evaluation?.event_chain_count ?? 0} · 已平仓 {evaluation?.closed_trade_count ?? 0}</p>
            </div>
            <span className="state-ok">稳定 {formatPercent(evaluation?.stability_score ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>验证阻断 {alphaBlockers.join(" / ") || "无"}</strong>
              <p>
                成交 {alphaValidation?.filled_order_count ?? 0} · 已平仓{" "}
                {alphaValidation?.closed_trade_count ?? 0} · 事件{" "}
                {alphaValidation?.event_chain_count ?? 0} · 评分反向{" "}
                {alphaValidation?.score_pnl_inversion_count ?? 0}
              </p>
            </div>
            <span className="state-ok">回撤 {formatPercent(alphaValidation?.max_drawdown ?? 0)}</span>
          </article>
          <article className="module-row">
            <div>
              <strong>真实历史回测</strong>
              <p>
                {alphaValidation?.has_real_market_backtest
                  ? "已记录同策略真实市场数据回测。"
                  : "Alpha gate 需要至少一次同策略真实历史回测。"}
              </p>
            </div>
            <span className={alphaValidation?.has_real_market_backtest ? "state-ok" : "state-warn"}>
              {alphaValidation?.has_real_market_backtest ? "已通过" : "待补"}
            </span>
          </article>
          <article className="module-row">
            <div>
              <strong>快照账本 {alphaSnapshots?.snapshot_count ?? 0} 天</strong>
              <p>
                正期望 {alphaSnapshots?.positive_expectancy_snapshot_count ?? 0} · Ready{" "}
                {alphaSnapshots?.ready_snapshot_count ?? 0} · 最新{" "}
                {alphaSnapshots?.latest?.trading_day ?? "无"}
              </p>
              <p>
                连续正期望 {alphaSnapshots?.positive_expectancy_streak ?? 0} 天 · 连续 Ready{" "}
                {alphaSnapshots?.ready_streak ?? 0} 天
              </p>
              <p>
                主要阻断{" "}
                {topAlphaSnapshotBlocker
                  ? `${topAlphaSnapshotBlocker.blocker} ×${topAlphaSnapshotBlocker.count}`
                  : "无"}
              </p>
              {alphaSnapshotMessage ? <p>{alphaSnapshotMessage}</p> : null}
            </div>
            <span className={alphaSnapshots?.latest?.alpha_ready ? "state-ok" : "state-warn"}>
              {alphaSnapshots?.latest ? `快照 ${alphaSnapshots.latest.validation_level}` : "no snapshot"}
            </span>
          </article>
        </div>
      </section>
    </>
  );
}

function lifecycleAuditBadgeLabel(item: StrategyLifecycleAuditPayload["items"][number]): string {
  if (item.execution_enabled === false) {
    return "execution off";
  }
  return item.auto_promotion_enabled ? "auto" : "manual";
}

function lifecycleAuditBadgeClass(item: StrategyLifecycleAuditPayload["items"][number]): string {
  if (item.execution_enabled === false || item.auto_promotion_enabled) {
    return "state-warn";
  }
  return "state-ok";
}

function scorePnlAlignmentLabel(
  alignment: StrategyAttributionPayload["ticker_diagnostics"][number]["score_pnl_alignment"] | undefined
): string {
  if (alignment === "aligned") {
    return "评分一致";
  }
  if (alignment === "inverted") {
    return "评分反向";
  }
  return "待验证";
}

function scorePnlAlignmentBadgeClass(
  alignment: StrategyAttributionPayload["ticker_diagnostics"][number]["score_pnl_alignment"] | undefined
): string {
  if (alignment === "aligned") {
    return "state-ok";
  }
  return "state-warn";
}

function formatPercent(value: number): string {
  return `${(value * 100).toFixed(2)}%`;
}

function selectVisibleLifecycleRules(rules: StrategyLifecyclePayload["rules"]) {
  const visible = rules.slice(0, 5);
  const alphaRule = rules.find((rule) => rule.name === "alpha_validation_ready");
  if (alphaRule && !visible.some((rule) => rule.name === alphaRule.name)) {
    return [...visible, alphaRule];
  }
  return visible;
}

function formatNumber(value: number): string {
  return value.toFixed(2);
}

function formatCurrency(value: number): string {
  return `$${value.toFixed(2)}`;
}

function formatSignedCurrency(value: number): string {
  if (value < 0) {
    return `-$${Math.abs(value).toFixed(2)}`;
  }
  return `$${value.toFixed(2)}`;
}
