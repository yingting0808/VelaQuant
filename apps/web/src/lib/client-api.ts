export type ResearchResultPayload = {
  ticker: string;
  status: string;
  summary: string;
  bull_case: string;
  bear_case: string;
  watch_items: string[];
  evidence_count: number;
  trade_plan_draft: {
    entry_condition: string;
    invalidation_condition: string;
    risk_notes: string[];
  };
};

export type ProviderStatusPayload = {
  name: string;
  mode: string;
  available: boolean;
  message: string;
  checked_at: string;
  version: string | null;
};

export type DataSourcesStatusPayload = {
  provider_mode: string;
  data_sources: ProviderStatusPayload[];
};

export type AIStatusPayload = {
  langgraph: {
    available: boolean;
    mode: string;
    message: string;
  };
  research_llm: {
    provider: string;
    mode: string;
    configured: boolean;
    available: boolean;
    model: string;
    base_url: string;
    message: string;
  };
  execution_path: {
    ai_generates_trade_intent: boolean;
    ai_influences_risk: boolean;
    ai_calls_execution: boolean;
  };
};

export type RuntimeSettingsPayload = {
  source: string;
  data_mode: string;
  sec_user_agent: string;
  lean_backtest_timeout_seconds: number;
  paper_scheduler_enabled: boolean;
  paper_scheduler_cron: string;
  paper_scheduler_timezone: string;
  event_bus_mode: string;
  redis_stream_name: string;
  redis_configured: boolean;
  openai_research_enabled: boolean;
  openai_research_model: string;
  openai_base_url: string;
  openai_timeout_seconds: number;
  openai_api_key_configured: boolean;
  openai_api_key_source: string | null;
};

export type RuntimeSettingsUpdatePayload = {
  data_mode: string;
  sec_user_agent: string;
  lean_backtest_timeout_seconds: number;
  openai_research_enabled: boolean;
  openai_research_model: string;
  openai_base_url: string;
  openai_timeout_seconds: number;
  openai_api_key?: string;
  clear_openai_api_key?: boolean;
};

export type StrategyToolStatusPayload = {
  name: string;
  available: boolean;
  version: string | null;
  message: string;
};

export type StrategyLabStatusPayload = {
  can_run_backtests: boolean;
  summary: string;
  tools: StrategyToolStatusPayload[];
};

export type StrategyEvaluationPayload = {
  strategy_id: string;
  strategy_name: string;
  sample_size: number;
  filled_order_count: number;
  rejected_order_count: number;
  closed_trade_count: number;
  signal_precision: number;
  expectancy: number;
  max_drawdown: number;
  stability_score: number;
  readiness: "insufficient_sample" | "negative_expectancy" | "watch" | "paper_ready";
  promotion_gate: string;
  event_chain_count: number;
  notes: string;
};

export type TickerSignalAttributionPayload = {
  ticker: string;
  market_event_count: number;
  trade_intent_count: number;
  candidate_score_count: number;
  average_candidate_score: number;
  latest_candidate_score: number | null;
  score_pnl_alignment: "aligned" | "inverted" | "unresolved";
  filled_order_count: number;
  false_positive_count: number;
  false_positive_rate: number;
  average_confidence: number;
  realized_pnl: number;
  unrealized_pnl: number;
  observed_pnl: number;
};

export type SignalDecayAttributionPayload = {
  threshold_days: number;
  open_position_count: number;
  stale_open_position_count: number;
  stale_tickers: string[];
  average_holding_days: number;
  basis: string;
};

export type AttributionComponentPayload = {
  name: "trend_component" | "volatility_component" | "timing_component" | "risk_component" | "noise_component";
  value: number;
  basis: string;
};

export type DrawdownContributorPayload = {
  name: "market_driven" | "signal_failure" | "execution_lag" | "risk_overreach";
  value: number;
  basis: string;
};

export type RegimePerformancePayload = {
  regime: "trend_market" | "range_market" | "high_volatility" | "insufficient_data";
  ticker_count: number;
  observed_pnl: number;
  average_return: number;
  average_volatility: number;
  sample_count: number;
  sharpe_proxy: number;
  tickers: string[];
  basis: string;
};

export type RegimeBreakdownPayload = {
  primary_regime: "trend_market" | "range_market" | "high_volatility" | "insufficient_data";
  items: RegimePerformancePayload[];
  basis: string;
};

export type StrategyAttributionPayload = {
  strategy_id: string;
  strategy_name: string;
  signal_quality: {
    market_event_count: number;
    trade_intent_count: number;
    actionable_signal_rate: number;
    average_confidence: number;
    false_positive_rate: number;
  };
  ticker_diagnostics: TickerSignalAttributionPayload[];
  signal_decay: SignalDecayAttributionPayload;
  expectancy_decomposition: {
    realized_pnl: number;
    unrealized_pnl: number;
    closed_trade_component: number;
    open_trade_component: number;
    total_observed_pnl: number;
    components: AttributionComponentPayload[];
  };
  regime: {
    regime: "insufficient_data" | "drawdown_pressure" | "uptrend_capture" | "range_bound";
    basis: string;
    review_count: number;
    equity_change: number;
  };
  regime_breakdown: RegimeBreakdownPayload;
  drawdown: {
    source: "insufficient_data" | "open_position_pressure" | "closed_trade_losses" | "equity_curve_pressure";
    max_drawdown: number;
    basis: string;
    contributors: DrawdownContributorPayload[];
  };
  data_quality_warnings: string[];
  summary: string;
};

export type StrategyRegistryEntryPayload = {
  strategy_id: string;
  name: string;
  version: string;
  source: "paper_core" | "lean_catalog";
  execution_mode: "paper" | "backtest";
  status: "active" | "available" | "blocked";
  rank: number;
  ranking_score: number;
  readiness: string;
  promotion_gate: string;
  sample_size: number;
  filled_order_count: number;
  observed_pnl: number;
  primary_regime: string;
  signal_quality_score: number;
  backtest_status: string | null;
  supports_live: boolean;
  supports_hot_swap: boolean;
  notes: string;
};

export type StrategyRegistryPayload = {
  active_strategy_id: string;
  entries: StrategyRegistryEntryPayload[];
  missing_capabilities: string[];
  summary: string;
};

export type StrategyCompetitionEntryPayload = {
  strategy_id: string;
  name: string;
  version: string;
  source: "paper_core" | "lean_catalog" | string;
  execution_mode: "paper" | "backtest" | string;
  status: string;
  rank: number;
  ranking_score: number;
  allocation_weight: number;
  eligible_for_allocation: boolean;
  recommended_action: string;
  blockers: string[];
  readiness: string;
  promotion_gate: string;
  sample_size: number;
  filled_order_count: number;
  filled_order_remaining: number;
  observed_pnl: number;
  primary_regime: string;
  signal_quality_score: number;
  supports_live: boolean;
  supports_hot_swap: boolean;
};

export type StrategyCompetitionPayload = {
  trading_day: string;
  status: string;
  active_strategy_id: string;
  selected_strategy_id: string | null;
  strategy_count: number;
  allocatable_strategy_count: number;
  competition_ready: boolean;
  entries: StrategyCompetitionEntryPayload[];
  summary: string;
};

export type StrategyCompetitionSnapshotPayload = StrategyCompetitionPayload & {
  id: string;
  team_id: string;
  created_at: string;
  updated_at: string;
};

export type StrategyCompetitionSnapshotHistoryPayload = {
  snapshot_count: number;
  latest: StrategyCompetitionSnapshotPayload | null;
  items: StrategyCompetitionSnapshotPayload[];
  summary: string;
};

export type StrategyAlphaIsolationPayload = {
  strategy_id: string;
  isolated: boolean;
  strategy_order_count: number;
  manual_override_order_count: number;
  manual_override_event_chain_count: number;
  filtered_event_chain_count: number;
  summary: string;
};

export type StrategyLifecycleRulePayload = {
  name: string;
  passed: boolean;
  severity: "blocker" | "warning" | "info";
  actual: string;
  required: string;
  message: string;
};

export type StrategyLifecyclePayload = {
  strategy_id: string;
  strategy_name: string;
  current_stage: "paper" | "shadow_candidate" | "shadow" | "live_small" | "live" | "killed";
  recommended_stage: "paper" | "shadow_candidate" | "shadow" | "live_small" | "live" | "killed";
  recommended_action:
    | "continue_collecting_samples"
    | "keep_paper_running"
    | "eligible_for_shadow_review"
    | "repair_event_ledger"
    | "kill_review"
    | "auto_promoted_to_shadow"
    | "auto_promoted_to_live_small"
    | "auto_promoted_to_live"
    | "auto_killed_negative_expectancy"
    | "hold_current_stage";
  gate_status: "blocked" | "watch" | "eligible";
  promotion_gate: string;
  can_promote: boolean;
  can_kill: boolean;
  auto_actions_enabled: boolean;
  rules: StrategyLifecycleRulePayload[];
  missing_capabilities: string[];
  summary: string;
};

export type StrategyLifecycleAuditItemPayload = {
  id: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  approved_by: string | null;
  reason: string | null;
  previous_stage: string | null;
  current_stage: string | null;
  auto_promotion_enabled: boolean | null;
  execution_enabled?: boolean | null;
  created_at: string;
};

export type StrategyLifecycleAuditPayload = {
  strategy_id: string;
  items: StrategyLifecycleAuditItemPayload[];
  summary: string;
};

export type TradingSystemReadinessPayload = {
  status: "operational" | "attention" | "blocked" | string;
  scheduler_running: boolean;
  scheduler_next_run_at: string | null;
  lifecycle_stage: string;
  alpha_ready: boolean;
  event_bus_mode: string;
  event_bus_ready: boolean;
  event_bus_stream_length: number | null;
  event_ledger_replay_ready: boolean;
  event_ledger_traceable_chain_count: number;
  event_ledger_complete_order_chain_count: number;
  event_ledger_broken_chain_count: number;
  event_ledger_traceability_ratio: number;
  shadow_can_record: boolean;
  shadow_remaining_observations: number;
  live_small_review_ready: boolean;
  live_or_broker_execution_enabled: boolean;
  manual_override_isolated: boolean;
  manual_override_order_count: number;
  manual_override_event_chain_count: number;
  alpha_filtered_event_chain_count: number;
  blockers: string[];
  pending_gates: string[];
  summary: string;
};

export type StrategyAlphaValidationPayload = {
  strategy_id: string;
  alpha_ready: boolean;
  validation_level: "collecting" | "paper_validated" | "failed";
  blockers: string[];
  has_real_market_backtest: boolean;
  review_day_count: number;
  consecutive_positive_expectancy_days: number;
  filled_order_count: number;
  closed_trade_count: number;
  event_chain_count: number;
  latest_expectancy: number;
  average_expectancy: number;
  max_drawdown: number;
  score_pnl_inversion_count?: number;
  summary: string;
};

export type AlphaGateProgressItemPayload = {
  gate: string;
  label: string;
  current: number;
  required: number;
  remaining: number;
  unit: string;
  comparison: "at_least" | "greater_than" | "at_most" | string;
  passed: boolean;
};

export type AlphaGateProgressPayload = {
  alpha_ready: boolean;
  validation_level: string;
  passed_gates: number;
  total_gates: number;
  items: AlphaGateProgressItemPayload[];
  summary: string;
};

export type AlphaValidationSnapshotPayload = {
  id: string;
  team_id: string;
  strategy_id: string;
  trading_day: string;
  alpha_ready: boolean;
  validation_level: string;
  blockers: string[];
  has_real_market_backtest: boolean;
  review_day_count: number;
  consecutive_positive_expectancy_days: number;
  filled_order_count: number;
  closed_trade_count: number;
  event_chain_count: number;
  latest_expectancy: number;
  average_expectancy: number;
  max_drawdown: number;
  created_at: string;
  updated_at: string;
};

export type AlphaValidationSnapshotBlockerCountPayload = {
  blocker: string;
  count: number;
};

export type AlphaValidationSnapshotHistoryPayload = {
  strategy_id: string;
  snapshot_count: number;
  ready_snapshot_count: number;
  positive_expectancy_snapshot_count: number;
  positive_expectancy_streak: number;
  ready_streak: number;
  latest_blockers: string[];
  blocker_counts: AlphaValidationSnapshotBlockerCountPayload[];
  latest: AlphaValidationSnapshotPayload | null;
  items: AlphaValidationSnapshotPayload[];
  summary: string;
};

export type AlphaValidationForecastItemPayload = {
  gate: string;
  label: string;
  current: number;
  required: number;
  remaining: number;
  unit: string;
  passed: boolean;
  estimated_per_session: number | null;
  estimated_sessions: number | null;
  reason: string;
};

export type AlphaValidationForecastPayload = {
  alpha_ready: boolean;
  status: "ready" | "forecastable" | "blocked" | string;
  estimated_sessions_to_alpha_ready: number | null;
  limiting_gate: string | null;
  items: AlphaValidationForecastItemPayload[];
  summary: string;
};

export type ShadowReviewChecklistItemPayload = {
  code: string;
  label: string;
  passed: boolean;
  evidence: string[];
};

export type ShadowReviewResidualRiskPayload = {
  code: string;
  severity: "info" | "medium" | "high" | string;
  detail: string;
  evidence: string[];
};

export type ShadowReviewPayload = {
  status: "blocked" | "ready_for_manual_review" | string;
  strategy_id: string;
  can_request_shadow_review: boolean;
  recommended_stage: string;
  auto_promotion_enabled: boolean;
  checklist: ShadowReviewChecklistItemPayload[];
  residual_risks: ShadowReviewResidualRiskPayload[];
  summary: string;
};

export type ShadowObservationPayload = {
  id: string;
  team_id: string;
  strategy_id: string;
  trading_day: string;
  status: string;
  can_request_shadow_review: boolean;
  observed_intent_count: number;
  would_route_order_count: number;
  event_chain_count: number;
  residual_risk_count: number;
  blocked_reason: string | null;
  created_at: string;
};

export type ShadowObservationSummaryPayload = {
  can_record_shadow_observation: boolean;
  latest: ShadowObservationPayload | null;
  items: ShadowObservationPayload[];
  summary: string;
};

export type ShadowObservationHealthPayload = {
  strategy_id: string;
  status: "collecting" | "stable" | "attention" | "blocked" | string;
  sample_ready: boolean;
  observation_count: number;
  observing_count: number;
  blocked_count: number;
  consecutive_observing_count: number;
  latest_trading_day: string | null;
  average_would_route_order_count: number;
  average_event_chain_count: number;
  average_residual_risk_count: number;
  warnings: string[];
  summary: string;
};

export type ShadowValidationPayload = {
  strategy_id: string;
  shadow_ready: boolean;
  status: "collecting" | "shadow_validated" | "blocked" | string;
  observation_count: number;
  observing_count: number;
  blocked_count: number;
  latest_trading_day: string | null;
  min_observations_required: number;
  remaining_observations: number;
  residual_risk_count: number;
  blockers: string[];
  summary: string;
};

export type ShadowDailyReportActionPayload = {
  priority: number;
  action_code: string;
  title: string;
  detail: string;
  evidence: string[];
};

export type ShadowDailyReportPayload = {
  strategy_id: string;
  trading_day: string | null;
  status: "collecting" | "ready_for_manual_review" | "attention" | "blocked" | string;
  observation_status: string;
  health_status: string;
  validation_status: string;
  live_small_status: string;
  observed_intent_count: number;
  would_route_order_count: number;
  event_chain_count: number;
  residual_risk_count: number;
  remaining_observations: number;
  warnings: string[];
  blockers: string[];
  next_actions: ShadowDailyReportActionPayload[];
  live_or_broker_execution_enabled: boolean;
  summary: string;
};

export type LiveSmallReviewChecklistItemPayload = {
  code: string;
  label: string;
  passed: boolean;
  evidence: string[];
};

export type LiveSmallReviewResidualRiskPayload = {
  code: string;
  severity: "info" | "medium" | "high" | string;
  detail: string;
  evidence: string[];
};

export type LiveSmallReviewPayload = {
  status: "blocked" | "ready_for_manual_review" | string;
  strategy_id: string;
  can_request_live_small_review: boolean;
  recommended_stage: string;
  auto_promotion_enabled: boolean;
  checklist: LiveSmallReviewChecklistItemPayload[];
  residual_risks: LiveSmallReviewResidualRiskPayload[];
  summary: string;
};

export type StrategyShadowApprovalRequestPayload = {
  approved_by: string;
  reason: string;
};

export type StrategyShadowApprovalPayload = {
  strategy_id: string;
  previous_stage: string;
  current_stage: string;
  approved_by: string;
  reason: string;
  auto_promotion_enabled: boolean;
  summary: string;
};

export type StrategyLiveSmallApprovalRequestPayload = {
  approved_by: string;
  reason: string;
};

export type StrategyLiveSmallApprovalPayload = {
  strategy_id: string;
  previous_stage: string;
  current_stage: string;
  approved_by: string;
  reason: string;
  auto_promotion_enabled: boolean;
  live_or_broker_execution_enabled: boolean;
  summary: string;
};

export type StrategyKillApprovalRequestPayload = {
  approved_by: string;
  reason: string;
};

export type StrategyKillApprovalPayload = {
  strategy_id: string;
  previous_stage: string;
  current_stage: string;
  approved_by: string;
  reason: string;
  auto_promotion_enabled: boolean;
  execution_enabled: boolean;
  summary: string;
};

export type StrategyLifecycleReconcilePayload = {
  strategy_id: string;
  previous_stage: string;
  current_stage: string;
  reconciled: boolean;
  reconciled_by: string;
  reason: string;
  alpha_ready: boolean;
  auto_promotion_enabled: boolean;
  execution_enabled: boolean;
  summary: string;
};

export type StrategyVersionPayload = {
  strategy_id: string;
  version: string;
  parameters_json: string;
  status: string;
  is_active: boolean;
};

export type StrategyVersionControlPayload = {
  active_strategy_id: string;
  active_version: string;
  previous_version: string | null;
  versions: StrategyVersionPayload[];
};

export type StrategyRuntimeEntryPayload = {
  strategy_id: string;
  version: string;
  ranking_score: number;
  eligible: boolean;
  rank: number;
  block_reason: string | null;
};

export type StrategyRuntimePayload = {
  winner: StrategyRuntimeEntryPayload | null;
  entries: StrategyRuntimeEntryPayload[];
  summary: string;
};

export type StrategyExecutionAccountPayload = {
  id: string;
  team_id: string;
  strategy_id: string;
  name: string;
  mode: "paper" | "shadow" | "live_small" | string;
  starting_cash: number;
  cash: number;
  realized_pnl: number;
};

export type StrategyExecutionAccountsPayload = {
  accounts: StrategyExecutionAccountPayload[];
};

export type PaperAccountPayload = {
  id: string;
  name: string;
  mode: string;
  starting_cash: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  equity: number;
  updated_at: string;
};

export type PaperCandidatePayload = {
  id: string;
  strategy_id: string;
  ticker: string;
  action: string;
  rank: number;
  confidence: number;
  thesis: string;
  risk_notes: string;
  evidence_summary: string;
  proposed_quantity: number;
  status: string;
  created_at: string;
};

export type PaperOrderPayload = {
  id: string;
  strategy_id: string;
  candidate_id: string | null;
  ticker: string;
  side: string;
  order_type: string;
  quantity: number;
  status: string;
  fill_price: number | null;
  realized_pnl: number;
  rejection_reason: string | null;
  core_order_id: string | null;
  core_intent_id: string | null;
  risk_status: string | null;
  risk_code: string | null;
  risk_reason: string | null;
  state_history: Array<{ state: string; recorded_at: string; reason: string }>;
  submitted_at: string;
  filled_at: string | null;
};

export type PaperPositionPayload = {
  id: string;
  ticker: string;
  quantity: number;
  average_cost: number;
  last_price: number | null;
  market_value: number;
  unrealized_pnl: number;
  realized_pnl: number;
  updated_at: string;
};

export type PaperReviewPayload = {
  id: string;
  trading_day: string;
  equity: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  trade_count: number;
  win_rate: number;
  average_win: number;
  average_loss: number;
  expectancy: number;
  readiness: string;
  notes: string;
  created_at: string;
};

export type PaperTradingSummaryPayload = {
  account: PaperAccountPayload;
  candidates: PaperCandidatePayload[];
  orders: PaperOrderPayload[];
  positions: PaperPositionPayload[];
  latest_review: PaperReviewPayload | null;
};

export type PaperExitWatchItemPayload = {
  ticker: string;
  quantity: number;
  return_pct: number;
  unrealized_pnl: number;
  trigger: "take_profit" | "stop_loss" | string;
  triggered: boolean;
  threshold_pct: number;
  distance_to_trigger_pct: number;
  next_exit_quantity: number;
};

export type PaperDailyReportPayload = {
  trading_day: string;
  run_state: string;
  health_status: string;
  recommended_action: string;
  scheduler_running: boolean;
  scheduler_next_run_at: string | null;
  scheduler_next_run_will_execute: boolean | null;
  scheduler_next_run_execution_gate: string | null;
  scheduler_next_actionable_run_at: string | null;
  scheduler_next_actionable_trading_day: string | null;
  scheduler_next_actionable_execution_gate: string | null;
  estimated_sessions_to_alpha_ready: number | null;
  limiting_alpha_gate: string | null;
  account_equity: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  daily_pnl: number;
  daily_return: number;
  candidate_count: number;
  actionable_candidate_count: number;
  ordered_candidate_count: number;
  dismissed_candidate_count: number;
  order_count: number;
  open_position_count: number;
  latest_expectancy: number;
  average_expectancy: number;
  consecutive_positive_expectancy_days: number;
  review_latest_expectancy: number;
  review_average_expectancy: number;
  review_consecutive_positive_expectancy_days: number;
  event_ledger_ready: boolean;
  alpha_ready: boolean;
  alpha_blockers: string[];
  open_alpha_gates: AlphaGateProgressItemPayload[];
  exit_watchlist: PaperExitWatchItemPayload[];
  data_quality_warnings: string[];
  summary: string;
};

export type PaperSchedulerStatusPayload = {
  enabled: boolean;
  running: boolean;
  job_count: number;
  job_id: string;
  cron: string;
  timezone: string;
  next_run_at: string | null;
  next_run_will_execute: boolean | null;
  next_run_execution_gate: string | null;
  next_run_trading_day: string | null;
  next_run_gate_reason: string | null;
  next_actionable_run_at: string | null;
  next_actionable_trading_day: string | null;
  next_actionable_execution_gate: string | null;
  next_actionable_gate_reason: string | null;
  last_checked_at: string;
  can_run_now: boolean;
  execution_gate: string;
  market_date: string;
  trading_day: string;
  is_market_session: boolean;
  session_closed: boolean;
  calendar_provider: string;
  gate_reason: string;
};

export type PaperMarketSessionPayload = {
  market_date: string;
  trading_day: string;
  is_market_session: boolean;
  session_closed: boolean;
  calendar_provider: string;
  reason: string;
};

export type PaperOperationsStatusPayload = {
  trading_day: string;
  run_state: "not_started" | "running" | "completed" | "skipped" | "failed";
  health_status: "ready" | "warning" | "blocked";
  latest_run_id: string | null;
  latest_run_trading_day: string | null;
  latest_run_status: string | null;
  today_run_id: string | null;
  review_id: string | null;
  latest_error: string | null;
  can_retry_today: boolean;
  event_ledger_ready: boolean;
  latest_run_event_count: number;
  legacy_manual_future_run_count: number;
  latest_legacy_manual_future_trading_day: string | null;
  data_quality_warnings: string[];
  latest_scheduler_decision: "executed" | "skipped" | "failed" | null;
  latest_scheduler_decision_at: string | null;
  latest_scheduler_decision_trading_day: string | null;
  latest_scheduler_decision_reason: string | null;
  latest_scheduler_decision_summary: string | null;
  blockers: string[];
  recommended_action:
    | "run_daily_paper_trading"
    | "retry_daily_paper_trading"
    | "hold_until_next_session"
    | "repair_event_ledger"
    | "wait_for_running_job";
  summary: string;
};

export type PaperOperationsHistoryItemPayload = {
  trading_day: string;
  run_id: string;
  status: string;
  health_status: "ready" | "warning" | "blocked";
  event_count: number;
  has_review: boolean;
  candidates_count: number;
  orders_count: number;
  positions_count: number;
  blockers: string[];
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
};

export type PaperOperationsHistoryPayload = {
  window_size: number;
  completed_days: number;
  failed_days: number;
  blocked_days: number;
  replayable_days: number;
  review_days: number;
  completion_rate: number;
  replay_rate: number;
  latest_health_status: "ready" | "warning" | "blocked";
  items: PaperOperationsHistoryItemPayload[];
  summary: string;
};

export type PaperOperationsRepairItemPayload = {
  run_id: string;
  trading_day: string;
  status: string;
  event_created: boolean;
  topic: string | null;
  reason: string;
};

export type PaperOperationsRepairPayload = {
  scanned_runs: number;
  repaired_runs: number;
  skipped_runs: number;
  items: PaperOperationsRepairItemPayload[];
  summary: string;
};

export type PaperOperationsQuarantineItemPayload = {
  run_id: string;
  trading_day: string;
  status: string;
  previous_trigger: string;
  new_trigger: string;
  audit_event_created: boolean;
  reason: string;
};

export type PaperOperationsQuarantinePayload = {
  scanned_runs: number;
  quarantined_runs: number;
  skipped_runs: number;
  items: PaperOperationsQuarantineItemPayload[];
  summary: string;
};

export type PaperReviewTrendItemPayload = {
  trading_day: string;
  equity: number;
  daily_pnl: number;
  daily_return: number;
  cash: number;
  realized_pnl: number;
  unrealized_pnl: number;
  trade_count: number;
  win_rate: number;
  expectancy: number;
  readiness: string;
};

export type PaperReviewTrendPayload = {
  sample_size: number;
  positive_expectancy_days: number;
  consecutive_positive_expectancy_days: number;
  average_expectancy: number;
  latest_expectancy: number;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  latest_readiness: string;
  items: PaperReviewTrendItemPayload[];
  summary: string;
};

export type PaperSimulationScenario = "baseline" | "bullish" | "bearish" | "volatile";

export type PaperSimulationRequestPayload = {
  days: number;
  scenario: PaperSimulationScenario;
  start_date?: string | null;
};

export type PaperSimulationItemPayload = {
  trading_day: string;
  run_status: string;
  orders_count: number;
  candidates_count: number;
  positions_count: number;
  review_id: string | null;
};

export type PaperSimulationPayload = {
  scenario: PaperSimulationScenario;
  start_date: string;
  days_requested: number;
  days_completed: number;
  days_skipped: number;
  review_day_count: number;
  consecutive_positive_expectancy_days: number;
  latest_expectancy: number;
  average_expectancy: number;
  event_chain_count: number;
  alpha_ready: boolean;
  blockers: string[];
  items: PaperSimulationItemPayload[];
  summary: string;
};

export type PaperExecutionRejectionReasonPayload = {
  risk_code: string;
  count: number;
  latest_reason: string | null;
};

export type PaperExecutionDiagnosticsPayload = {
  order_count: number;
  filled_order_count: number;
  rejected_order_count: number;
  buy_order_count: number;
  sell_order_count: number;
  closed_trade_count: number;
  fill_rate: number;
  rejection_rate: number;
  realized_pnl: number;
  average_realized_pnl: number;
  latest_rejection_code: string | null;
  max_daily_order_rejections: number;
  max_daily_order_buy_rejections: number;
  max_daily_order_sell_rejections: number;
  rejection_reasons: PaperExecutionRejectionReasonPayload[];
  summary: string;
};

export type PaperRiskProfilePayload = {
  risk_engine: string;
  max_order_notional: number;
  max_position_weight: number;
  max_daily_orders: number;
  exit_take_profit_pct: number;
  exit_stop_loss_pct: number;
  summary: string;
};

export type PaperRiskLimitReviewPayload = {
  status: "hold" | "review_required";
  current_max_daily_orders: number;
  recommended_paper_max_daily_orders: number;
  live_change_allowed: boolean;
  max_daily_order_rejections: number;
  max_daily_order_buy_rejections: number;
  max_daily_order_sell_rejections: number;
  filled_order_count: number;
  closed_trade_count: number;
  sample_collection_blocked: boolean;
  blockers: string[];
  summary: string;
};

export type PaperRiskLimitApplyPayload = {
  applied: boolean;
  previous_max_daily_orders: number;
  applied_max_daily_orders: number;
  live_change_allowed: boolean;
  audit_event_created: boolean;
  summary: string;
};

export type PaperActionPlanItemPayload = {
  priority: number;
  action_code: string;
  title: string;
  detail: string;
  evidence: string[];
  projected_gate_impacts?: {
    gate: string;
    label: string;
    projected_increment: number;
    current_remaining: number;
    projected_remaining: number;
    unit: string;
  }[];
};

export type PaperActionPlanPayload = {
  readiness: string;
  primary_action: string;
  items: PaperActionPlanItemPayload[];
  summary: string;
};

export type PaperActionExecutionPayload = {
  executed: boolean;
  queued?: boolean;
  status?: string;
  action_code: string;
  next_primary_action: string;
  result: Record<string, unknown> | null;
  summary: string;
};

export type PaperStrategyReviewItemPayload = {
  event_id: string;
  action_code: string;
  title: string;
  detail: string;
  evidence: string[];
  inverted_tickers: string[];
  review_status: string;
  created_at: string;
};

export type PaperStrategyReviewsPayload = {
  review_count: number;
  items: PaperStrategyReviewItemPayload[];
  summary: string;
};

export type PaperRunPayload = {
  id: string;
  trading_day: string;
  trigger: string;
  status: string;
  candidates_count: number;
  orders_count: number;
  positions_count: number;
  review_id: string | null;
  error_message: string | null;
  started_at: string;
  finished_at: string | null;
};

export type PaperRunsPayload = {
  runs: PaperRunPayload[];
};

export type EventLedgerTopicCountPayload = {
  topic: string;
  count: number;
};

export type EventLedgerTradeExplanationPayload = {
  ticker: string | null;
  strategy_id: string | null;
  candidate_id: string | null;
  decision: string | null;
  explanation: string | null;
  evidence: string[];
  evidence_items?: {
    ticker: string;
    title: string;
    summary: string;
    source: string;
    source_url: string;
    observed_at: string;
    form: string | null;
    filing_date: string | null;
    accession_number: string | null;
  }[];
  backtest: Record<string, string | number | boolean | null>;
};

export type EventLedgerReplayChainPayload = {
  correlation_id: string;
  ticker: string | null;
  topics: string[];
  order_states: string[];
  terminal_state: string | null;
  event_count: number;
  integrity_warnings?: string[];
  trade_explanation?: EventLedgerTradeExplanationPayload | null;
};

export type EventLedgerReplayPayload = {
  run_id: string;
  event_count: number;
  chain_count: number;
  chains: EventLedgerReplayChainPayload[];
};

export type PaperEventLedgerPayload = {
  total_event_count: number;
  latest_run_id: string | null;
  latest_run_status: string | null;
  latest_run_event_count: number;
  latest_topic_counts: EventLedgerTopicCountPayload[];
  latest_correlation_count: number;
  integrity_ready?: boolean;
  integrity_warnings?: string[];
  traceable_chain_count?: number;
  complete_order_chain_count?: number;
  broken_chain_count?: number;
  traceability_ratio?: number;
  replay_ready: boolean;
  warnings: string[];
  summary: string;
  latest_replay: EventLedgerReplayPayload | null;
};

export type MarketEventTracePayload = {
  chain_events: {
    event_id: string;
    topic: string;
    sequence: number;
    causation_id: string | null;
    payload: Record<string, unknown>;
  }[];
  event_id: string;
  run_id: string | null;
  trading_day: string | null;
  published_at: string;
  correlation_id: string;
  ticker: string | null;
  strategy_id: string | null;
  event_type: string | null;
  summary: string | null;
  confidence: number | null;
  impact_score: number | null;
  source: string | null;
  evidence_quality: "unknown" | "real_market_data" | "mock_data" | "deterministic_research_series" | "mixed";
  uses_real_market_evidence: boolean;
  topics: string[];
  trade_intent_side: string | null;
  trade_intent_reason: string | null;
  risk_decision: string | null;
  risk_reason: string | null;
  order_state: string | null;
  explanation: string | null;
  evidence: string[];
  evidence_items: {
    ticker: string | null;
    title: string | null;
    summary: string | null;
    source: string | null;
    source_url: string | null;
    observed_at: string | null;
    form: string | null;
    filing_date: string | null;
    accession_number: string | null;
  }[];
};

export type PaperMarketEventsPayload = {
  total_event_count: number;
  filtered_event_count: number;
  events: MarketEventTracePayload[];
  summary: string;
};

export type PaperOrderInputPayload = {
  ticker: string;
  side: "buy" | "sell";
  quantity: number;
  order_type: "market";
  strategy_id: string;
  candidate_id?: string | null;
};

function getPublicApiBaseUrl(): string {
  return process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
}

function fallbackResearchResult(ticker: string, question: string): ResearchResultPayload {
  return {
    ticker,
    status: "offline_fallback",
    summary: `${ticker}: 本地 API 暂不可用，已生成离线占位分析。问题：${question}`,
    bull_case: "组合仍有可跟踪的基本面和事件线索，但需要接入实时数据后复核。",
    bear_case: "离线模式不能确认最新价格、新闻和公告，不能作为交易依据。",
    watch_items: ["启动后端 API", "接入真实数据源", "由人工复核结论"],
    evidence_count: 0,
    trade_plan_draft: {
      entry_condition: "仅在 API 和数据源恢复后，由人工确认研究结论。",
      invalidation_condition: "任何新公告、价格波动或数据缺口都应使该草稿失效。",
      risk_notes: ["这不是可直接执行的订单建议。", "必须经过人工审批。"]
    }
  };
}

const fallbackDataSourcesStatus: DataSourcesStatusPayload = {
  provider_mode: "hybrid",
  data_sources: [
    {
      name: "Mock",
      mode: "mock",
      available: true,
      message: "本地 Mock 数据可用。",
      checked_at: "local",
      version: "local"
    },
    {
      name: "SEC EDGAR",
      mode: "sec_edgar",
      available: false,
      message: "后端 API 暂不可用，无法确认 SEC EDGAR 状态。",
      checked_at: "local",
      version: null
    },
    {
      name: "OpenBB",
      mode: "openbb_optional",
      available: false,
      message: "OpenBB 为可选数据层，当前未确认。",
      checked_at: "local",
      version: null
    }
  ]
};

const fallbackAIStatus: AIStatusPayload = {
  langgraph: {
    available: true,
    mode: "research_workflow",
    message: "LangGraph 编排投研 workflow；后端 API 暂不可用，无法确认实时状态。"
  },
  research_llm: {
    provider: "openai_responses_or_chat_completions",
    mode: "research_only",
    configured: false,
    available: false,
    model: "gpt-5.5",
    base_url: "https://api.openai.com/v1",
    message: "后端 API 暂不可用，无法确认 OpenAI-compatible LLM 状态。"
  },
  execution_path: {
    ai_generates_trade_intent: false,
    ai_influences_risk: false,
    ai_calls_execution: false
  }
};

const fallbackRuntimeSettings: RuntimeSettingsPayload = {
  source: "fallback",
  data_mode: "hybrid",
  sec_user_agent: "VelaQuant research app contact@example.com",
  lean_backtest_timeout_seconds: 600,
  paper_scheduler_enabled: false,
  paper_scheduler_cron: "30 6 * * *",
  paper_scheduler_timezone: "Asia/Shanghai",
  event_bus_mode: "memory",
  redis_stream_name: "trading:events",
  redis_configured: false,
  openai_research_enabled: true,
  openai_research_model: "gpt-5.5",
  openai_base_url: "https://api.openai.com/v1",
  openai_timeout_seconds: 20,
  openai_api_key_configured: false,
  openai_api_key_source: null
};

const fallbackStrategyLabStatus: StrategyLabStatusPayload = {
  can_run_backtests: false,
  summary: "后端 API 暂不可用，无法确认 Docker / LEAN 状态。",
  tools: [
    {
      name: "Docker CLI",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "Docker Compose",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "Docker engine",
      available: false,
      version: null,
      message: "状态未确认。"
    },
    {
      name: "LEAN CLI",
      available: false,
      version: null,
      message: "状态未确认。"
    }
  ]
};

const fallbackStrategyEvaluation: StrategyEvaluationPayload = {
  strategy_id: "deterministic_watchlist_v1",
  strategy_name: "Deterministic Watchlist Strategy",
  sample_size: 0,
  filled_order_count: 0,
  rejected_order_count: 0,
  closed_trade_count: 0,
  signal_precision: 0,
  expectancy: 0,
  max_drawdown: 0,
  stability_score: 0,
  readiness: "insufficient_sample",
  promotion_gate: "blocked",
  event_chain_count: 0,
  notes: "后端 API 暂不可用，无法确认策略评价。"
};

const fallbackStrategyAttribution: StrategyAttributionPayload = {
  strategy_id: "deterministic_watchlist_v1",
  strategy_name: "Deterministic Watchlist Strategy",
  signal_quality: {
    market_event_count: 0,
    trade_intent_count: 0,
    actionable_signal_rate: 0,
    average_confidence: 0,
    false_positive_rate: 0
  },
  expectancy_decomposition: {
    realized_pnl: 0,
    unrealized_pnl: 0,
    closed_trade_component: 0,
    open_trade_component: 0,
    total_observed_pnl: 0,
    components: [
      { name: "trend_component", value: 0, basis: "离线模式不能确认趋势组件。" },
      { name: "volatility_component", value: 0, basis: "离线模式不能确认波动组件。" },
      { name: "timing_component", value: 0, basis: "离线模式不能确认时点组件。" },
      { name: "risk_component", value: 0, basis: "离线模式不能确认风险摩擦。" },
      { name: "noise_component", value: 0, basis: "离线模式不能确认噪声组件。" }
    ]
  },
  ticker_diagnostics: [],
  signal_decay: {
    threshold_days: 5,
    open_position_count: 0,
    stale_open_position_count: 0,
    stale_tickers: [],
    average_holding_days: 0,
    basis: "后端 API 暂不可用，无法确认信号衰减。"
  },
  regime: {
    regime: "insufficient_data",
    basis: "后端 API 暂不可用，无法确认市场环境代理。",
    review_count: 0,
    equity_change: 0
  },
  regime_breakdown: {
    primary_regime: "insufficient_data",
    items: [
      {
        regime: "trend_market",
        ticker_count: 0,
        observed_pnl: 0,
        average_return: 0,
        average_volatility: 0,
        sample_count: 0,
        sharpe_proxy: 0,
        tickers: [],
        basis: "离线模式不能确认趋势市场表现。"
      },
      {
        regime: "range_market",
        ticker_count: 0,
        observed_pnl: 0,
        average_return: 0,
        average_volatility: 0,
        sample_count: 0,
        sharpe_proxy: 0,
        tickers: [],
        basis: "离线模式不能确认震荡市场表现。"
      },
      {
        regime: "high_volatility",
        ticker_count: 0,
        observed_pnl: 0,
        average_return: 0,
        average_volatility: 0,
        sample_count: 0,
        sharpe_proxy: 0,
        tickers: [],
        basis: "离线模式不能确认高波动市场表现。"
      },
      {
        regime: "insufficient_data",
        ticker_count: 0,
        observed_pnl: 0,
        average_return: 0,
        average_volatility: 0,
        sample_count: 0,
        sharpe_proxy: 0,
        tickers: [],
        basis: "行情历史不足。"
      }
    ],
    basis: "后端 API 暂不可用，无法确认市场环境 breakdown。"
  },
  drawdown: {
    source: "insufficient_data",
    max_drawdown: 0,
    basis: "后端 API 暂不可用，无法确认回撤来源。",
    contributors: [
      { name: "market_driven", value: 0, basis: "离线模式不能确认市场贡献。" },
      { name: "signal_failure", value: 0, basis: "离线模式不能确认信号失效。" },
      { name: "execution_lag", value: 0, basis: "离线模式不能确认执行延迟。" },
      { name: "risk_overreach", value: 0, basis: "离线模式不能确认风险越界。" }
    ]
  },
  data_quality_warnings: ["offline_fallback"],
  summary: "后端 API 暂不可用，无法确认策略归因。"
};

const fallbackStrategyRegistry: StrategyRegistryPayload = {
  active_strategy_id: "deterministic_watchlist_v1",
  entries: [
    {
      strategy_id: "deterministic_watchlist_v1",
      name: "Deterministic Watchlist Strategy",
      version: "v1",
      source: "paper_core",
      execution_mode: "paper",
      status: "active",
      rank: 1,
      ranking_score: 0,
      readiness: "insufficient_sample",
      promotion_gate: "blocked",
      sample_size: 0,
      filled_order_count: 0,
      observed_pnl: 0,
      primary_regime: "insufficient_data",
      signal_quality_score: 0,
      backtest_status: null,
      supports_live: false,
      supports_hot_swap: true,
      notes: "后端 API 暂不可用，无法确认策略注册表。"
    }
  ],
  missing_capabilities: [],
  summary: "后端 API 暂不可用，Registry 使用离线占位。"
};

const fallbackStrategyCompetition: StrategyCompetitionPayload = {
  trading_day: "offline",
  status: "blocked",
  active_strategy_id: "deterministic_watchlist_v1",
  selected_strategy_id: null,
  strategy_count: 1,
  allocatable_strategy_count: 0,
  competition_ready: false,
  entries: [
    {
      strategy_id: "deterministic_watchlist_v1",
      name: "Deterministic Watchlist Strategy",
      version: "v1",
      source: "paper_core",
      execution_mode: "paper",
      status: "active",
      rank: 1,
      ranking_score: 0,
      allocation_weight: 0,
      eligible_for_allocation: false,
      recommended_action: "collect_more_evidence",
      blockers: ["api_unavailable"],
      readiness: "insufficient_sample",
      promotion_gate: "blocked",
      sample_size: 0,
      filled_order_count: 0,
      filled_order_remaining: 30,
      observed_pnl: 0,
      primary_regime: "insufficient_data",
      signal_quality_score: 0,
      supports_live: false,
      supports_hot_swap: false
    }
  ],
  summary: "后端 API 暂不可用，无法确认策略竞争层。"
};

const fallbackStrategyCompetitionSnapshots: StrategyCompetitionSnapshotHistoryPayload = {
  snapshot_count: 0,
  latest: null,
  items: [],
  summary: "后端 API 暂不可用，无法读取策略竞争快照历史。"
};

const fallbackStrategyAlphaIsolation: StrategyAlphaIsolationPayload = {
  strategy_id: "deterministic_watchlist_v1",
  isolated: false,
  strategy_order_count: 0,
  manual_override_order_count: 0,
  manual_override_event_chain_count: 0,
  filtered_event_chain_count: 0,
  summary: "后端 API 暂不可用，无法确认手工覆盖是否隔离。"
};

const fallbackStrategyLifecycle: StrategyLifecyclePayload = {
  strategy_id: "deterministic_watchlist_v1",
  strategy_name: "Deterministic Watchlist Strategy",
  current_stage: "paper",
  recommended_stage: "paper",
  recommended_action: "continue_collecting_samples",
  gate_status: "watch",
  promotion_gate: "blocked",
  can_promote: false,
  can_kill: false,
  auto_actions_enabled: false,
  rules: [
    {
      name: "minimum_filled_orders",
      passed: false,
      severity: "blocker",
      actual: "0 filled orders",
      required: ">= 30 filled orders",
      message: "后端 API 暂不可用，无法确认生命周期门禁。"
    }
  ],
  missing_capabilities: [],
  summary: "后端 API 暂不可用，Lifecycle 使用离线占位。"
};

const fallbackStrategyLifecycleAudit: StrategyLifecycleAuditPayload = {
  strategy_id: "deterministic_watchlist_v1",
  items: [],
  summary: "后端 API 暂不可用，无法读取生命周期审计。"
};

const fallbackTradingSystemReadiness: TradingSystemReadinessPayload = {
  status: "blocked",
  scheduler_running: false,
  scheduler_next_run_at: null,
  lifecycle_stage: "unknown",
  alpha_ready: false,
  event_bus_mode: "unknown",
  event_bus_ready: false,
  event_bus_stream_length: null,
  event_ledger_replay_ready: false,
  event_ledger_traceable_chain_count: 0,
  event_ledger_complete_order_chain_count: 0,
  event_ledger_broken_chain_count: 0,
  event_ledger_traceability_ratio: 0,
  shadow_can_record: false,
  shadow_remaining_observations: 5,
  live_small_review_ready: false,
  live_or_broker_execution_enabled: false,
  manual_override_isolated: false,
  manual_override_order_count: 0,
  manual_override_event_chain_count: 0,
  alpha_filtered_event_chain_count: 0,
  blockers: ["api_unavailable"],
  pending_gates: [],
  summary: "后端 API 暂不可用，无法确认交易系统运行态。"
};

const fallbackStrategyAlphaValidation: StrategyAlphaValidationPayload = {
  strategy_id: "deterministic_watchlist_v1",
  alpha_ready: false,
  validation_level: "collecting",
  blockers: ["api_unavailable"],
  has_real_market_backtest: false,
  review_day_count: 0,
  consecutive_positive_expectancy_days: 0,
  filled_order_count: 0,
  closed_trade_count: 0,
  event_chain_count: 0,
  latest_expectancy: 0,
  average_expectancy: 0,
  max_drawdown: 0,
  score_pnl_inversion_count: 0,
  summary: "后端 API 暂不可用，Alpha 验证使用离线占位。"
};

const fallbackStrategyVersionControl: StrategyVersionControlPayload = {
  active_strategy_id: "deterministic_watchlist_v1",
  active_version: "v1",
  previous_version: null,
  versions: [
    {
      strategy_id: "deterministic_watchlist_v1",
      version: "v1",
      parameters_json: "{\"notional\": 2000}",
      status: "offline_fallback",
      is_active: true
    }
  ]
};

const fallbackStrategyRuntime: StrategyRuntimePayload = {
  winner: {
    strategy_id: "deterministic_watchlist_v1",
    version: "v1",
    ranking_score: 0,
    eligible: true,
    rank: 1,
    block_reason: null
  },
  entries: [
    {
      strategy_id: "deterministic_watchlist_v1",
      version: "v1",
      ranking_score: 0,
      eligible: true,
      rank: 1,
      block_reason: null
    }
  ],
  summary: "后端 API 暂不可用，Runtime 使用离线占位。"
};

const fallbackAlphaGateProgress: AlphaGateProgressPayload = {
  alpha_ready: false,
  validation_level: "collecting",
  passed_gates: 0,
  total_gates: 0,
  items: [],
  summary: "后端 API 暂不可用，无法确认 Alpha 门禁进度。"
};

const fallbackAlphaValidationSnapshots: AlphaValidationSnapshotHistoryPayload = {
  strategy_id: "deterministic_watchlist_v1",
  snapshot_count: 0,
  ready_snapshot_count: 0,
  positive_expectancy_snapshot_count: 0,
  positive_expectancy_streak: 0,
  ready_streak: 0,
  latest_blockers: [],
  blocker_counts: [],
  latest: null,
  items: [],
  summary: "后端 API 暂不可用，无法读取 Alpha 验证快照。"
};

const fallbackAlphaValidationForecast: AlphaValidationForecastPayload = {
  alpha_ready: false,
  status: "blocked",
  estimated_sessions_to_alpha_ready: null,
  limiting_gate: null,
  items: [],
  summary: "后端 API 暂不可用，无法预测 Alpha 验证进度。"
};

const fallbackShadowReview: ShadowReviewPayload = {
  status: "blocked",
  strategy_id: "deterministic_watchlist_v1",
  can_request_shadow_review: false,
  recommended_stage: "paper",
  auto_promotion_enabled: false,
  checklist: [],
  residual_risks: [],
  summary: "后端 API 暂不可用，无法生成 Shadow 评审包。"
};

const fallbackShadowObservationSummary: ShadowObservationSummaryPayload = {
  can_record_shadow_observation: false,
  latest: null,
  items: [],
  summary: "后端 API 暂不可用，无法读取 Shadow 观察记录。"
};

const fallbackShadowObservationHealth: ShadowObservationHealthPayload = {
  strategy_id: "deterministic_watchlist_v1",
  status: "collecting",
  sample_ready: false,
  observation_count: 0,
  observing_count: 0,
  blocked_count: 0,
  consecutive_observing_count: 0,
  latest_trading_day: null,
  average_would_route_order_count: 0,
  average_event_chain_count: 0,
  average_residual_risk_count: 0,
  warnings: ["api_unavailable"],
  summary: "后端 API 暂不可用，无法确认 Shadow 观察健康度。"
};

const fallbackShadowValidation: ShadowValidationPayload = {
  strategy_id: "deterministic_watchlist_v1",
  shadow_ready: false,
  status: "collecting",
  observation_count: 0,
  observing_count: 0,
  blocked_count: 0,
  latest_trading_day: null,
  min_observations_required: 5,
  remaining_observations: 5,
  residual_risk_count: 0,
  blockers: ["shadow_observation_sample"],
  summary: "后端 API 暂不可用，无法确认 Shadow 验证门禁。"
};

const fallbackShadowDailyReport: ShadowDailyReportPayload = {
  strategy_id: "deterministic_watchlist_v1",
  trading_day: null,
  status: "collecting",
  observation_status: "not_recorded",
  health_status: "collecting",
  validation_status: "collecting",
  live_small_status: "blocked",
  observed_intent_count: 0,
  would_route_order_count: 0,
  event_chain_count: 0,
  residual_risk_count: 0,
  remaining_observations: 5,
  warnings: ["api_unavailable"],
  blockers: ["shadow_observation_sample"],
  next_actions: [
    {
      priority: 1,
      action_code: "record_shadow_observation",
      title: "记录 Shadow 观察",
      detail: "后端 API 暂不可用，暂不能确认 Shadow 日报。",
      evidence: ["api_unavailable"]
    }
  ],
  live_or_broker_execution_enabled: false,
  summary: "后端 API 暂不可用，无法生成 Shadow 日报。"
};

const fallbackLiveSmallReview: LiveSmallReviewPayload = {
  status: "blocked",
  strategy_id: "deterministic_watchlist_v1",
  can_request_live_small_review: false,
  recommended_stage: "shadow",
  auto_promotion_enabled: false,
  checklist: [],
  residual_risks: [],
  summary: "后端 API 暂不可用，无法生成 live-small 人工评审包。"
};

const fallbackStrategyExecutionAccounts: StrategyExecutionAccountsPayload = {
  accounts: [
    {
      id: "offline-paper",
      team_id: "offline",
      strategy_id: "deterministic_watchlist_v1",
      name: "paper",
      mode: "paper",
      starting_cash: 100000,
      cash: 100000,
      realized_pnl: 0
    },
    {
      id: "offline-shadow",
      team_id: "offline",
      strategy_id: "deterministic_watchlist_v1",
      name: "shadow",
      mode: "shadow",
      starting_cash: 100000,
      cash: 100000,
      realized_pnl: 0
    },
    {
      id: "offline-live-small",
      team_id: "offline",
      strategy_id: "deterministic_watchlist_v1",
      name: "live-small",
      mode: "live_small",
      starting_cash: 5000,
      cash: 5000,
      realized_pnl: 0
    }
  ]
};

const fallbackPaperTradingSummary: PaperTradingSummaryPayload = {
  account: {
    id: "offline-paper-account",
    name: "默认模拟盘",
    mode: "paper",
    starting_cash: 100000,
    cash: 100000,
    realized_pnl: 0,
    unrealized_pnl: 0,
    equity: 100000,
    updated_at: "local"
  },
  candidates: [],
  orders: [],
  positions: [],
  latest_review: null
};

const fallbackPaperDailyReport: PaperDailyReportPayload = {
  trading_day: "offline",
  run_state: "not_started",
  health_status: "blocked",
  recommended_action: "run_daily_paper_trading",
  scheduler_running: false,
  scheduler_next_run_at: null,
  scheduler_next_run_will_execute: null,
  scheduler_next_run_execution_gate: null,
  scheduler_next_actionable_run_at: null,
  scheduler_next_actionable_trading_day: null,
  scheduler_next_actionable_execution_gate: null,
  estimated_sessions_to_alpha_ready: null,
  limiting_alpha_gate: null,
  account_equity: 0,
  cash: 0,
  realized_pnl: 0,
  unrealized_pnl: 0,
  daily_pnl: 0,
  daily_return: 0,
  candidate_count: 0,
  actionable_candidate_count: 0,
  ordered_candidate_count: 0,
  dismissed_candidate_count: 0,
  order_count: 0,
  open_position_count: 0,
  latest_expectancy: 0,
  average_expectancy: 0,
  consecutive_positive_expectancy_days: 0,
  review_latest_expectancy: 0,
  review_average_expectancy: 0,
  review_consecutive_positive_expectancy_days: 0,
  event_ledger_ready: false,
  alpha_ready: false,
  alpha_blockers: ["api_unavailable"],
  open_alpha_gates: [],
  exit_watchlist: [],
  data_quality_warnings: ["api_unavailable"],
  summary: "后端 API 暂不可用，无法生成今日简报。"
};

const fallbackPaperSchedulerStatus: PaperSchedulerStatusPayload = {
  calendar_provider: "offline",
  can_run_now: false,
  cron: "30 6 * * *",
  enabled: false,
  execution_gate: "api_unavailable",
  gate_reason: "api_unavailable",
  job_count: 0,
  job_id: "paper_trading_daily_run",
  last_checked_at: "local",
  market_date: "offline",
  next_run_at: null,
  next_run_will_execute: null,
  next_run_execution_gate: null,
  next_run_trading_day: null,
  next_run_gate_reason: null,
  next_actionable_run_at: null,
  next_actionable_trading_day: null,
  next_actionable_execution_gate: null,
  next_actionable_gate_reason: null,
  running: false,
  session_closed: false,
  is_market_session: false,
  trading_day: "offline",
  timezone: "Asia/Shanghai"
};

const fallbackPaperMarketSession: PaperMarketSessionPayload = {
  market_date: "offline",
  trading_day: "offline",
  is_market_session: false,
  session_closed: false,
  calendar_provider: "offline",
  reason: "api_unavailable"
};

const fallbackPaperOperationsStatus: PaperOperationsStatusPayload = {
  trading_day: "offline",
  run_state: "not_started",
  health_status: "blocked",
  latest_run_id: null,
  latest_run_trading_day: null,
  latest_run_status: null,
  today_run_id: null,
  review_id: null,
  latest_error: null,
  can_retry_today: true,
  event_ledger_ready: false,
  latest_run_event_count: 0,
  legacy_manual_future_run_count: 0,
  latest_legacy_manual_future_trading_day: null,
  data_quality_warnings: [],
  latest_scheduler_decision: null,
  latest_scheduler_decision_at: null,
  latest_scheduler_decision_trading_day: null,
  latest_scheduler_decision_reason: null,
  latest_scheduler_decision_summary: null,
  blockers: ["api_unavailable"],
  recommended_action: "run_daily_paper_trading",
  summary: "后端 API 暂不可用，无法确认每日运行健康。"
};

const fallbackPaperOperationsHistory: PaperOperationsHistoryPayload = {
  window_size: 0,
  completed_days: 0,
  failed_days: 0,
  blocked_days: 0,
  replayable_days: 0,
  review_days: 0,
  completion_rate: 0,
  replay_rate: 0,
  latest_health_status: "blocked",
  items: [],
  summary: "后端 API 暂不可用，无法确认运行稳定趋势。"
};

const fallbackPaperOperationsRepair: PaperOperationsRepairPayload = {
  scanned_runs: 0,
  repaired_runs: 0,
  skipped_runs: 0,
  items: [],
  summary: "后端 API 暂不可用，无法修复事件账本。"
};

const fallbackPaperOperationsQuarantine: PaperOperationsQuarantinePayload = {
  scanned_runs: 0,
  quarantined_runs: 0,
  skipped_runs: 0,
  items: [],
  summary: "后端 API 暂不可用，无法标记旧运行。"
};

const fallbackPaperReviewTrend: PaperReviewTrendPayload = {
  sample_size: 0,
  positive_expectancy_days: 0,
  consecutive_positive_expectancy_days: 0,
  average_expectancy: 0,
  latest_expectancy: 0,
  total_realized_pnl: 0,
  total_unrealized_pnl: 0,
  latest_readiness: "collecting",
  items: [],
  summary: "后端 API 暂不可用，无法确认净期望趋势。"
};

const fallbackPaperSimulation: PaperSimulationPayload = {
  scenario: "bullish",
  start_date: "offline",
  days_requested: 0,
  days_completed: 0,
  days_skipped: 0,
  review_day_count: 0,
  consecutive_positive_expectancy_days: 0,
  latest_expectancy: 0,
  average_expectancy: 0,
  event_chain_count: 0,
  alpha_ready: false,
  blockers: ["api_unavailable"],
  items: [],
  summary: "后端 API 暂不可用，无法运行多日模拟。"
};

const fallbackPaperExecutionDiagnostics: PaperExecutionDiagnosticsPayload = {
  order_count: 0,
  filled_order_count: 0,
  rejected_order_count: 0,
  buy_order_count: 0,
  sell_order_count: 0,
  closed_trade_count: 0,
  fill_rate: 0,
  rejection_rate: 0,
  realized_pnl: 0,
  average_realized_pnl: 0,
  latest_rejection_code: null,
  max_daily_order_rejections: 0,
  max_daily_order_buy_rejections: 0,
  max_daily_order_sell_rejections: 0,
  rejection_reasons: [],
  summary: "后端 API 暂不可用，无法确认执行诊断。"
};

const fallbackPaperRiskProfile: PaperRiskProfilePayload = {
  risk_engine: "Trading Core RiskEngine",
  max_order_notional: 2000,
  max_position_weight: 0.1,
  max_daily_orders: 5,
  exit_take_profit_pct: 0.1,
  exit_stop_loss_pct: -0.05,
  summary: "后端 API 暂不可用，显示默认纸面风控配置。"
};

const fallbackPaperRiskLimitReview: PaperRiskLimitReviewPayload = {
  status: "hold",
  current_max_daily_orders: 5,
  recommended_paper_max_daily_orders: 5,
  live_change_allowed: false,
  max_daily_order_rejections: 0,
  max_daily_order_buy_rejections: 0,
  max_daily_order_sell_rejections: 0,
  filled_order_count: 0,
  closed_trade_count: 0,
  sample_collection_blocked: false,
  blockers: ["api_unavailable"],
  summary: "后端 API 暂不可用，无法生成风险限额评审。"
};

const fallbackPaperRiskLimitApply: PaperRiskLimitApplyPayload = {
  applied: false,
  previous_max_daily_orders: 5,
  applied_max_daily_orders: 5,
  live_change_allowed: false,
  audit_event_created: false,
  summary: "后端 API 暂不可用，无法应用 Paper 风险限额建议。"
};

const fallbackPaperActionPlan: PaperActionPlanPayload = {
  readiness: "blocked",
  primary_action: "api_unavailable",
  items: [
    {
      priority: 1,
      action_code: "api_unavailable",
      title: "等待 API 恢复",
      detail: "后端 API 暂不可用，无法生成行动计划。",
      evidence: []
    }
  ],
  summary: "后端 API 暂不可用，无法生成行动计划。"
};

const fallbackPaperActionExecution: PaperActionExecutionPayload = {
  executed: false,
  queued: false,
  status: "skipped",
  action_code: "api_unavailable",
  next_primary_action: "api_unavailable",
  result: null,
  summary: "后端 API 暂不可用，无法执行行动计划。"
};

const fallbackPaperStrategyReviews: PaperStrategyReviewsPayload = {
  review_count: 0,
  items: [],
  summary: "后端 API 暂不可用，无法读取策略复盘记录。"
};

const fallbackPaperRuns: PaperRunsPayload = {
  runs: []
};

const fallbackPaperEventLedger: PaperEventLedgerPayload = {
  total_event_count: 0,
  latest_run_id: null,
  latest_run_status: null,
  latest_run_event_count: 0,
  latest_topic_counts: [],
  latest_correlation_count: 0,
  integrity_ready: false,
  integrity_warnings: ["missing_core_events"],
  traceable_chain_count: 0,
  complete_order_chain_count: 0,
  broken_chain_count: 0,
  traceability_ratio: 0,
  replay_ready: false,
  warnings: ["missing_core_events"],
  summary: "后端 API 暂不可用，无法确认事件账本。",
  latest_replay: null
};

const fallbackPaperMarketEvents: PaperMarketEventsPayload = {
  total_event_count: 0,
  filtered_event_count: 0,
  events: [],
  summary: "后端 API 暂不可用，无法读取市场事件。"
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function isResearchResultPayload(value: unknown): value is ResearchResultPayload {
  if (!isRecord(value) || !isRecord(value.trade_plan_draft)) {
    return false;
  }

  return (
    typeof value.ticker === "string" &&
    typeof value.status === "string" &&
    typeof value.summary === "string" &&
    typeof value.bull_case === "string" &&
    typeof value.bear_case === "string" &&
    Array.isArray(value.watch_items) &&
    value.watch_items.every((item) => typeof item === "string") &&
    typeof value.evidence_count === "number" &&
    typeof value.trade_plan_draft.entry_condition === "string" &&
    typeof value.trade_plan_draft.invalidation_condition === "string" &&
    Array.isArray(value.trade_plan_draft.risk_notes) &&
    value.trade_plan_draft.risk_notes.every((item) => typeof item === "string")
  );
}

function isProviderStatus(value: unknown): value is ProviderStatusPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.mode === "string" &&
    typeof value.available === "boolean" &&
    typeof value.message === "string" &&
    typeof value.checked_at === "string" &&
    (typeof value.version === "string" || value.version === null)
  );
}

function isDataSourcesStatusPayload(value: unknown): value is DataSourcesStatusPayload {
  return (
    isRecord(value) &&
    typeof value.provider_mode === "string" &&
    Array.isArray(value.data_sources) &&
    value.data_sources.every(isProviderStatus)
  );
}

function isAIStatusPayload(value: unknown): value is AIStatusPayload {
  return (
    isRecord(value) &&
    isRecord(value.langgraph) &&
    typeof value.langgraph.available === "boolean" &&
    typeof value.langgraph.mode === "string" &&
    typeof value.langgraph.message === "string" &&
    isRecord(value.research_llm) &&
    typeof value.research_llm.provider === "string" &&
    typeof value.research_llm.mode === "string" &&
    typeof value.research_llm.configured === "boolean" &&
    typeof value.research_llm.available === "boolean" &&
    typeof value.research_llm.model === "string" &&
    typeof value.research_llm.base_url === "string" &&
    typeof value.research_llm.message === "string" &&
    isRecord(value.execution_path) &&
    typeof value.execution_path.ai_generates_trade_intent === "boolean" &&
    typeof value.execution_path.ai_influences_risk === "boolean" &&
    typeof value.execution_path.ai_calls_execution === "boolean"
  );
}

function isRuntimeSettingsPayload(value: unknown): value is RuntimeSettingsPayload {
  return (
    isRecord(value) &&
    typeof value.source === "string" &&
    typeof value.data_mode === "string" &&
    typeof value.sec_user_agent === "string" &&
    typeof value.lean_backtest_timeout_seconds === "number" &&
    typeof value.paper_scheduler_enabled === "boolean" &&
    typeof value.paper_scheduler_cron === "string" &&
    typeof value.paper_scheduler_timezone === "string" &&
    typeof value.event_bus_mode === "string" &&
    typeof value.redis_stream_name === "string" &&
    typeof value.redis_configured === "boolean" &&
    typeof value.openai_research_enabled === "boolean" &&
    typeof value.openai_research_model === "string" &&
    typeof value.openai_base_url === "string" &&
    typeof value.openai_timeout_seconds === "number" &&
    typeof value.openai_api_key_configured === "boolean" &&
    (typeof value.openai_api_key_source === "string" || value.openai_api_key_source === null)
  );
}

function isStrategyToolStatus(value: unknown): value is StrategyToolStatusPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.available === "boolean" &&
    (typeof value.version === "string" || value.version === null) &&
    typeof value.message === "string"
  );
}

function isStrategyLabStatusPayload(value: unknown): value is StrategyLabStatusPayload {
  return (
    isRecord(value) &&
    typeof value.can_run_backtests === "boolean" &&
    typeof value.summary === "string" &&
    Array.isArray(value.tools) &&
    value.tools.every(isStrategyToolStatus)
  );
}

function isStrategyEvaluationPayload(value: unknown): value is StrategyEvaluationPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.strategy_name === "string" &&
    typeof value.sample_size === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.rejected_order_count === "number" &&
    typeof value.closed_trade_count === "number" &&
    typeof value.signal_precision === "number" &&
    typeof value.expectancy === "number" &&
    typeof value.max_drawdown === "number" &&
    typeof value.stability_score === "number" &&
    typeof value.readiness === "string" &&
    typeof value.promotion_gate === "string" &&
    typeof value.event_chain_count === "number" &&
    typeof value.notes === "string"
  );
}

function isTickerSignalAttributionPayload(value: unknown): value is TickerSignalAttributionPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.market_event_count === "number" &&
    typeof value.trade_intent_count === "number" &&
    typeof value.candidate_score_count === "number" &&
    typeof value.average_candidate_score === "number" &&
    (typeof value.latest_candidate_score === "number" || value.latest_candidate_score === null) &&
    (value.score_pnl_alignment === "aligned" ||
      value.score_pnl_alignment === "inverted" ||
      value.score_pnl_alignment === "unresolved") &&
    typeof value.filled_order_count === "number" &&
    typeof value.false_positive_count === "number" &&
    typeof value.false_positive_rate === "number" &&
    typeof value.average_confidence === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.observed_pnl === "number"
  );
}

function isSignalDecayAttributionPayload(value: unknown): value is SignalDecayAttributionPayload {
  return (
    isRecord(value) &&
    typeof value.threshold_days === "number" &&
    typeof value.open_position_count === "number" &&
    typeof value.stale_open_position_count === "number" &&
    Array.isArray(value.stale_tickers) &&
    value.stale_tickers.every((item) => typeof item === "string") &&
    typeof value.average_holding_days === "number" &&
    typeof value.basis === "string"
  );
}

function isAttributionComponentPayload(value: unknown): value is AttributionComponentPayload {
  return isRecord(value) && typeof value.name === "string" && typeof value.value === "number" && typeof value.basis === "string";
}

function isDrawdownContributorPayload(value: unknown): value is DrawdownContributorPayload {
  return isRecord(value) && typeof value.name === "string" && typeof value.value === "number" && typeof value.basis === "string";
}

function isRegimePerformancePayload(value: unknown): value is RegimePerformancePayload {
  return (
    isRecord(value) &&
    typeof value.regime === "string" &&
    typeof value.ticker_count === "number" &&
    typeof value.observed_pnl === "number" &&
    typeof value.average_return === "number" &&
    typeof value.average_volatility === "number" &&
    typeof value.sample_count === "number" &&
    typeof value.sharpe_proxy === "number" &&
    Array.isArray(value.tickers) &&
    value.tickers.every((item) => typeof item === "string") &&
    typeof value.basis === "string"
  );
}

function isRegimeBreakdownPayload(value: unknown): value is RegimeBreakdownPayload {
  return (
    isRecord(value) &&
    typeof value.primary_regime === "string" &&
    Array.isArray(value.items) &&
    value.items.every(isRegimePerformancePayload) &&
    typeof value.basis === "string"
  );
}

function isStrategyAttributionPayload(value: unknown): value is StrategyAttributionPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.strategy_name === "string" &&
    isRecord(value.signal_quality) &&
    typeof value.signal_quality.market_event_count === "number" &&
    typeof value.signal_quality.trade_intent_count === "number" &&
    typeof value.signal_quality.actionable_signal_rate === "number" &&
    typeof value.signal_quality.average_confidence === "number" &&
    typeof value.signal_quality.false_positive_rate === "number" &&
    Array.isArray(value.ticker_diagnostics) &&
    value.ticker_diagnostics.every(isTickerSignalAttributionPayload) &&
    isSignalDecayAttributionPayload(value.signal_decay) &&
    isRecord(value.expectancy_decomposition) &&
    typeof value.expectancy_decomposition.realized_pnl === "number" &&
    typeof value.expectancy_decomposition.unrealized_pnl === "number" &&
    typeof value.expectancy_decomposition.closed_trade_component === "number" &&
    typeof value.expectancy_decomposition.open_trade_component === "number" &&
    typeof value.expectancy_decomposition.total_observed_pnl === "number" &&
    Array.isArray(value.expectancy_decomposition.components) &&
    value.expectancy_decomposition.components.every(isAttributionComponentPayload) &&
    isRecord(value.regime) &&
    typeof value.regime.regime === "string" &&
    typeof value.regime.basis === "string" &&
    typeof value.regime.review_count === "number" &&
    typeof value.regime.equity_change === "number" &&
    isRegimeBreakdownPayload(value.regime_breakdown) &&
    isRecord(value.drawdown) &&
    typeof value.drawdown.source === "string" &&
    typeof value.drawdown.max_drawdown === "number" &&
    typeof value.drawdown.basis === "string" &&
    Array.isArray(value.drawdown.contributors) &&
    value.drawdown.contributors.every(isDrawdownContributorPayload) &&
    Array.isArray(value.data_quality_warnings) &&
    value.data_quality_warnings.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isAlphaGateProgressItemPayload(value: unknown): value is AlphaGateProgressItemPayload {
  return (
    isRecord(value) &&
    typeof value.gate === "string" &&
    typeof value.label === "string" &&
    typeof value.current === "number" &&
    typeof value.required === "number" &&
    typeof value.remaining === "number" &&
    typeof value.unit === "string" &&
    typeof value.comparison === "string" &&
    typeof value.passed === "boolean"
  );
}

function isAlphaGateProgressPayload(value: unknown): value is AlphaGateProgressPayload {
  return (
    isRecord(value) &&
    typeof value.alpha_ready === "boolean" &&
    typeof value.validation_level === "string" &&
    typeof value.passed_gates === "number" &&
    typeof value.total_gates === "number" &&
    Array.isArray(value.items) &&
    value.items.every(isAlphaGateProgressItemPayload) &&
    typeof value.summary === "string"
  );
}

function isAlphaValidationSnapshotPayload(value: unknown): value is AlphaValidationSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.team_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.alpha_ready === "boolean" &&
    typeof value.validation_level === "string" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    typeof value.has_real_market_backtest === "boolean" &&
    typeof value.review_day_count === "number" &&
    typeof value.consecutive_positive_expectancy_days === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.closed_trade_count === "number" &&
    typeof value.event_chain_count === "number" &&
    typeof value.latest_expectancy === "number" &&
    typeof value.average_expectancy === "number" &&
    typeof value.max_drawdown === "number" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

function isAlphaValidationSnapshotBlockerCountPayload(
  value: unknown
): value is AlphaValidationSnapshotBlockerCountPayload {
  return isRecord(value) && typeof value.blocker === "string" && typeof value.count === "number";
}

function isAlphaValidationSnapshotHistoryPayload(value: unknown): value is AlphaValidationSnapshotHistoryPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.snapshot_count === "number" &&
    typeof value.ready_snapshot_count === "number" &&
    typeof value.positive_expectancy_snapshot_count === "number" &&
    typeof value.positive_expectancy_streak === "number" &&
    typeof value.ready_streak === "number" &&
    Array.isArray(value.latest_blockers) &&
    value.latest_blockers.every((item) => typeof item === "string") &&
    Array.isArray(value.blocker_counts) &&
    value.blocker_counts.every(isAlphaValidationSnapshotBlockerCountPayload) &&
    (value.latest === null || isAlphaValidationSnapshotPayload(value.latest)) &&
    Array.isArray(value.items) &&
    value.items.every(isAlphaValidationSnapshotPayload) &&
    typeof value.summary === "string"
  );
}

function isAlphaValidationForecastItemPayload(value: unknown): value is AlphaValidationForecastItemPayload {
  return (
    isRecord(value) &&
    typeof value.gate === "string" &&
    typeof value.label === "string" &&
    typeof value.current === "number" &&
    typeof value.required === "number" &&
    typeof value.remaining === "number" &&
    typeof value.unit === "string" &&
    typeof value.passed === "boolean" &&
    (typeof value.estimated_per_session === "number" || value.estimated_per_session === null) &&
    (typeof value.estimated_sessions === "number" || value.estimated_sessions === null) &&
    typeof value.reason === "string"
  );
}

function isAlphaValidationForecastPayload(value: unknown): value is AlphaValidationForecastPayload {
  return (
    isRecord(value) &&
    typeof value.alpha_ready === "boolean" &&
    typeof value.status === "string" &&
    (typeof value.estimated_sessions_to_alpha_ready === "number" ||
      value.estimated_sessions_to_alpha_ready === null) &&
    (typeof value.limiting_gate === "string" || value.limiting_gate === null) &&
    Array.isArray(value.items) &&
    value.items.every(isAlphaValidationForecastItemPayload) &&
    typeof value.summary === "string"
  );
}

function isShadowReviewChecklistItemPayload(value: unknown): value is ShadowReviewChecklistItemPayload {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    typeof value.label === "string" &&
    typeof value.passed === "boolean" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string")
  );
}

function isShadowReviewResidualRiskPayload(value: unknown): value is ShadowReviewResidualRiskPayload {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    typeof value.severity === "string" &&
    typeof value.detail === "string" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string")
  );
}

function isShadowReviewPayload(value: unknown): value is ShadowReviewPayload {
  return (
    isRecord(value) &&
    typeof value.status === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.can_request_shadow_review === "boolean" &&
    typeof value.recommended_stage === "string" &&
    typeof value.auto_promotion_enabled === "boolean" &&
    Array.isArray(value.checklist) &&
    value.checklist.every(isShadowReviewChecklistItemPayload) &&
    Array.isArray(value.residual_risks) &&
    value.residual_risks.every(isShadowReviewResidualRiskPayload) &&
    typeof value.summary === "string"
  );
}

function isShadowObservationPayload(value: unknown): value is ShadowObservationPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.team_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.status === "string" &&
    typeof value.can_request_shadow_review === "boolean" &&
    typeof value.observed_intent_count === "number" &&
    typeof value.would_route_order_count === "number" &&
    typeof value.event_chain_count === "number" &&
    typeof value.residual_risk_count === "number" &&
    (typeof value.blocked_reason === "string" || value.blocked_reason === null) &&
    typeof value.created_at === "string"
  );
}

function isShadowObservationSummaryPayload(value: unknown): value is ShadowObservationSummaryPayload {
  return (
    isRecord(value) &&
    typeof value.can_record_shadow_observation === "boolean" &&
    (isShadowObservationPayload(value.latest) || value.latest === null) &&
    Array.isArray(value.items) &&
    value.items.every(isShadowObservationPayload) &&
    typeof value.summary === "string"
  );
}

function isShadowObservationHealthPayload(value: unknown): value is ShadowObservationHealthPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.status === "string" &&
    typeof value.sample_ready === "boolean" &&
    typeof value.observation_count === "number" &&
    typeof value.observing_count === "number" &&
    typeof value.blocked_count === "number" &&
    typeof value.consecutive_observing_count === "number" &&
    (typeof value.latest_trading_day === "string" || value.latest_trading_day === null) &&
    typeof value.average_would_route_order_count === "number" &&
    typeof value.average_event_chain_count === "number" &&
    typeof value.average_residual_risk_count === "number" &&
    Array.isArray(value.warnings) &&
    value.warnings.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isShadowValidationPayload(value: unknown): value is ShadowValidationPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.shadow_ready === "boolean" &&
    typeof value.status === "string" &&
    typeof value.observation_count === "number" &&
    typeof value.observing_count === "number" &&
    typeof value.blocked_count === "number" &&
    (typeof value.latest_trading_day === "string" || value.latest_trading_day === null) &&
    typeof value.min_observations_required === "number" &&
    typeof value.remaining_observations === "number" &&
    typeof value.residual_risk_count === "number" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isShadowDailyReportActionPayload(value: unknown): value is ShadowDailyReportActionPayload {
  return (
    isRecord(value) &&
    typeof value.priority === "number" &&
    typeof value.action_code === "string" &&
    typeof value.title === "string" &&
    typeof value.detail === "string" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string")
  );
}

function isShadowDailyReportPayload(value: unknown): value is ShadowDailyReportPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    (typeof value.trading_day === "string" || value.trading_day === null) &&
    typeof value.status === "string" &&
    typeof value.observation_status === "string" &&
    typeof value.health_status === "string" &&
    typeof value.validation_status === "string" &&
    typeof value.live_small_status === "string" &&
    typeof value.observed_intent_count === "number" &&
    typeof value.would_route_order_count === "number" &&
    typeof value.event_chain_count === "number" &&
    typeof value.residual_risk_count === "number" &&
    typeof value.remaining_observations === "number" &&
    Array.isArray(value.warnings) &&
    value.warnings.every((item) => typeof item === "string") &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    Array.isArray(value.next_actions) &&
    value.next_actions.every(isShadowDailyReportActionPayload) &&
    typeof value.live_or_broker_execution_enabled === "boolean" &&
    typeof value.summary === "string"
  );
}

function isLiveSmallReviewChecklistItemPayload(value: unknown): value is LiveSmallReviewChecklistItemPayload {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    typeof value.label === "string" &&
    typeof value.passed === "boolean" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string")
  );
}

function isLiveSmallReviewResidualRiskPayload(value: unknown): value is LiveSmallReviewResidualRiskPayload {
  return (
    isRecord(value) &&
    typeof value.code === "string" &&
    typeof value.severity === "string" &&
    typeof value.detail === "string" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string")
  );
}

function isLiveSmallReviewPayload(value: unknown): value is LiveSmallReviewPayload {
  return (
    isRecord(value) &&
    typeof value.status === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.can_request_live_small_review === "boolean" &&
    typeof value.recommended_stage === "string" &&
    typeof value.auto_promotion_enabled === "boolean" &&
    Array.isArray(value.checklist) &&
    value.checklist.every(isLiveSmallReviewChecklistItemPayload) &&
    Array.isArray(value.residual_risks) &&
    value.residual_risks.every(isLiveSmallReviewResidualRiskPayload) &&
    typeof value.summary === "string"
  );
}

function isStrategyShadowApprovalPayload(value: unknown): value is StrategyShadowApprovalPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.previous_stage === "string" &&
    typeof value.current_stage === "string" &&
    typeof value.approved_by === "string" &&
    typeof value.reason === "string" &&
    typeof value.auto_promotion_enabled === "boolean" &&
    typeof value.summary === "string"
  );
}

function isStrategyRegistryEntryPayload(value: unknown): value is StrategyRegistryEntryPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.name === "string" &&
    typeof value.version === "string" &&
    typeof value.source === "string" &&
    typeof value.execution_mode === "string" &&
    typeof value.status === "string" &&
    typeof value.rank === "number" &&
    typeof value.ranking_score === "number" &&
    typeof value.readiness === "string" &&
    typeof value.promotion_gate === "string" &&
    typeof value.sample_size === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.observed_pnl === "number" &&
    typeof value.primary_regime === "string" &&
    typeof value.signal_quality_score === "number" &&
    (typeof value.backtest_status === "string" || value.backtest_status === null) &&
    typeof value.supports_live === "boolean" &&
    typeof value.supports_hot_swap === "boolean" &&
    typeof value.notes === "string"
  );
}

function isStrategyRegistryPayload(value: unknown): value is StrategyRegistryPayload {
  return (
    isRecord(value) &&
    typeof value.active_strategy_id === "string" &&
    Array.isArray(value.entries) &&
    value.entries.every(isStrategyRegistryEntryPayload) &&
    Array.isArray(value.missing_capabilities) &&
    value.missing_capabilities.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isStrategyCompetitionEntryPayload(value: unknown): value is StrategyCompetitionEntryPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.name === "string" &&
    typeof value.version === "string" &&
    typeof value.source === "string" &&
    typeof value.execution_mode === "string" &&
    typeof value.status === "string" &&
    typeof value.rank === "number" &&
    typeof value.ranking_score === "number" &&
    typeof value.allocation_weight === "number" &&
    typeof value.eligible_for_allocation === "boolean" &&
    typeof value.recommended_action === "string" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    typeof value.readiness === "string" &&
    typeof value.promotion_gate === "string" &&
    typeof value.sample_size === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.filled_order_remaining === "number" &&
    typeof value.observed_pnl === "number" &&
    typeof value.primary_regime === "string" &&
    typeof value.signal_quality_score === "number" &&
    typeof value.supports_live === "boolean" &&
    typeof value.supports_hot_swap === "boolean"
  );
}

function isStrategyCompetitionPayload(value: unknown): value is StrategyCompetitionPayload {
  return (
    isRecord(value) &&
    typeof value.trading_day === "string" &&
    typeof value.status === "string" &&
    typeof value.active_strategy_id === "string" &&
    (typeof value.selected_strategy_id === "string" || value.selected_strategy_id === null) &&
    typeof value.strategy_count === "number" &&
    typeof value.allocatable_strategy_count === "number" &&
    typeof value.competition_ready === "boolean" &&
    Array.isArray(value.entries) &&
    value.entries.every(isStrategyCompetitionEntryPayload) &&
    typeof value.summary === "string"
  );
}

function isStrategyCompetitionSnapshotPayload(value: unknown): value is StrategyCompetitionSnapshotPayload {
  const snapshot = value as Record<string, unknown>;
  return (
    isStrategyCompetitionPayload(value) &&
    typeof snapshot.id === "string" &&
    typeof snapshot.team_id === "string" &&
    typeof snapshot.created_at === "string" &&
    typeof snapshot.updated_at === "string"
  );
}

function isStrategyCompetitionSnapshotHistoryPayload(value: unknown): value is StrategyCompetitionSnapshotHistoryPayload {
  return (
    isRecord(value) &&
    typeof value.snapshot_count === "number" &&
    (value.latest === null || isStrategyCompetitionSnapshotPayload(value.latest)) &&
    Array.isArray(value.items) &&
    value.items.every(isStrategyCompetitionSnapshotPayload) &&
    typeof value.summary === "string"
  );
}

function isStrategyAlphaIsolationPayload(value: unknown): value is StrategyAlphaIsolationPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.isolated === "boolean" &&
    typeof value.strategy_order_count === "number" &&
    typeof value.manual_override_order_count === "number" &&
    typeof value.manual_override_event_chain_count === "number" &&
    typeof value.filtered_event_chain_count === "number" &&
    typeof value.summary === "string"
  );
}

function isStrategyLifecycleRulePayload(value: unknown): value is StrategyLifecycleRulePayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.passed === "boolean" &&
    typeof value.severity === "string" &&
    typeof value.actual === "string" &&
    typeof value.required === "string" &&
    typeof value.message === "string"
  );
}

function isStrategyLifecyclePayload(value: unknown): value is StrategyLifecyclePayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.strategy_name === "string" &&
    typeof value.current_stage === "string" &&
    typeof value.recommended_stage === "string" &&
    typeof value.recommended_action === "string" &&
    typeof value.gate_status === "string" &&
    typeof value.promotion_gate === "string" &&
    typeof value.can_promote === "boolean" &&
    typeof value.can_kill === "boolean" &&
    typeof value.auto_actions_enabled === "boolean" &&
    Array.isArray(value.rules) &&
    value.rules.every(isStrategyLifecycleRulePayload) &&
    Array.isArray(value.missing_capabilities) &&
    value.missing_capabilities.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isStrategyLifecycleAuditItemPayload(value: unknown): value is StrategyLifecycleAuditItemPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.action === "string" &&
    typeof value.entity_type === "string" &&
    (typeof value.entity_id === "string" || value.entity_id === null) &&
    (typeof value.approved_by === "string" || value.approved_by === null) &&
    (typeof value.reason === "string" || value.reason === null) &&
    (typeof value.previous_stage === "string" || value.previous_stage === null) &&
    (typeof value.current_stage === "string" || value.current_stage === null) &&
    (typeof value.auto_promotion_enabled === "boolean" || value.auto_promotion_enabled === null) &&
    (typeof value.execution_enabled === "boolean" ||
      value.execution_enabled === null ||
      value.execution_enabled === undefined) &&
    typeof value.created_at === "string"
  );
}

function isStrategyLifecycleAuditPayload(value: unknown): value is StrategyLifecycleAuditPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    Array.isArray(value.items) &&
    value.items.every(isStrategyLifecycleAuditItemPayload) &&
    typeof value.summary === "string"
  );
}

function isTradingSystemReadinessPayload(value: unknown): value is TradingSystemReadinessPayload {
  return (
    isRecord(value) &&
    typeof value.status === "string" &&
    typeof value.scheduler_running === "boolean" &&
    (typeof value.scheduler_next_run_at === "string" || value.scheduler_next_run_at === null) &&
    typeof value.lifecycle_stage === "string" &&
    typeof value.alpha_ready === "boolean" &&
    typeof value.event_bus_mode === "string" &&
    typeof value.event_bus_ready === "boolean" &&
    (typeof value.event_bus_stream_length === "number" || value.event_bus_stream_length === null) &&
    typeof value.event_ledger_replay_ready === "boolean" &&
    typeof value.event_ledger_traceable_chain_count === "number" &&
    typeof value.event_ledger_complete_order_chain_count === "number" &&
    typeof value.event_ledger_broken_chain_count === "number" &&
    typeof value.event_ledger_traceability_ratio === "number" &&
    typeof value.shadow_can_record === "boolean" &&
    typeof value.shadow_remaining_observations === "number" &&
    typeof value.live_small_review_ready === "boolean" &&
    typeof value.live_or_broker_execution_enabled === "boolean" &&
    typeof value.manual_override_isolated === "boolean" &&
    typeof value.manual_override_order_count === "number" &&
    typeof value.manual_override_event_chain_count === "number" &&
    typeof value.alpha_filtered_event_chain_count === "number" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    Array.isArray(value.pending_gates) &&
    value.pending_gates.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isStrategyAlphaValidationPayload(value: unknown): value is StrategyAlphaValidationPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.alpha_ready === "boolean" &&
    typeof value.validation_level === "string" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    typeof value.review_day_count === "number" &&
    typeof value.consecutive_positive_expectancy_days === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.closed_trade_count === "number" &&
    typeof value.event_chain_count === "number" &&
    typeof value.latest_expectancy === "number" &&
    typeof value.average_expectancy === "number" &&
    typeof value.max_drawdown === "number" &&
    (value.score_pnl_inversion_count === undefined || typeof value.score_pnl_inversion_count === "number") &&
    typeof value.summary === "string"
  );
}

function isStrategyLiveSmallApprovalPayload(value: unknown): value is StrategyLiveSmallApprovalPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.previous_stage === "string" &&
    typeof value.current_stage === "string" &&
    typeof value.approved_by === "string" &&
    typeof value.reason === "string" &&
    typeof value.auto_promotion_enabled === "boolean" &&
    typeof value.live_or_broker_execution_enabled === "boolean" &&
    typeof value.summary === "string"
  );
}

function isStrategyKillApprovalPayload(value: unknown): value is StrategyKillApprovalPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.previous_stage === "string" &&
    typeof value.current_stage === "string" &&
    typeof value.approved_by === "string" &&
    typeof value.reason === "string" &&
    typeof value.auto_promotion_enabled === "boolean" &&
    typeof value.execution_enabled === "boolean" &&
    typeof value.summary === "string"
  );
}

function isStrategyLifecycleReconcilePayload(value: unknown): value is StrategyLifecycleReconcilePayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.previous_stage === "string" &&
    typeof value.current_stage === "string" &&
    typeof value.reconciled === "boolean" &&
    typeof value.reconciled_by === "string" &&
    typeof value.reason === "string" &&
    typeof value.alpha_ready === "boolean" &&
    typeof value.auto_promotion_enabled === "boolean" &&
    typeof value.execution_enabled === "boolean" &&
    typeof value.summary === "string"
  );
}

function isStrategyVersionPayload(value: unknown): value is StrategyVersionPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.version === "string" &&
    typeof value.parameters_json === "string" &&
    typeof value.status === "string" &&
    typeof value.is_active === "boolean"
  );
}

function isStrategyVersionControlPayload(value: unknown): value is StrategyVersionControlPayload {
  return (
    isRecord(value) &&
    typeof value.active_strategy_id === "string" &&
    typeof value.active_version === "string" &&
    (typeof value.previous_version === "string" || value.previous_version === null) &&
    Array.isArray(value.versions) &&
    value.versions.every(isStrategyVersionPayload)
  );
}

function isStrategyRuntimeEntryPayload(value: unknown): value is StrategyRuntimeEntryPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.version === "string" &&
    typeof value.ranking_score === "number" &&
    typeof value.eligible === "boolean" &&
    typeof value.rank === "number" &&
    (typeof value.block_reason === "string" || value.block_reason === null)
  );
}

function isStrategyRuntimePayload(value: unknown): value is StrategyRuntimePayload {
  return (
    isRecord(value) &&
    (isStrategyRuntimeEntryPayload(value.winner) || value.winner === null) &&
    Array.isArray(value.entries) &&
    value.entries.every(isStrategyRuntimeEntryPayload) &&
    typeof value.summary === "string"
  );
}

function isStrategyExecutionAccountPayload(value: unknown): value is StrategyExecutionAccountPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.team_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.name === "string" &&
    typeof value.mode === "string" &&
    typeof value.starting_cash === "number" &&
    typeof value.cash === "number" &&
    typeof value.realized_pnl === "number"
  );
}

function isStrategyExecutionAccountsPayload(value: unknown): value is StrategyExecutionAccountsPayload {
  return (
    isRecord(value) &&
    Array.isArray(value.accounts) &&
    value.accounts.every(isStrategyExecutionAccountPayload)
  );
}

export async function runResearchPrompt(question: string, ticker = "AAPL"): Promise<ResearchResultPayload> {
  const normalizedTicker = ticker.trim().toUpperCase() || "AAPL";
  const normalizedQuestion = question.trim() || "解释当前页面";
  const controller = new AbortController();
  const timeoutId = globalThis.setTimeout(() => controller.abort(), 60_000);

  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/research`, {
      body: JSON.stringify({
        question: normalizedQuestion,
        ticker: normalizedTicker
      }),
      headers: {
        "Content-Type": "application/json"
      },
      method: "POST",
      signal: controller.signal
    });

    if (!response.ok) {
      return fallbackResearchResult(normalizedTicker, normalizedQuestion);
    }

    const payload: unknown = await response.json();
    return isResearchResultPayload(payload)
      ? payload
      : fallbackResearchResult(normalizedTicker, normalizedQuestion);
  } catch {
    return fallbackResearchResult(normalizedTicker, normalizedQuestion);
  } finally {
    globalThis.clearTimeout(timeoutId);
  }
}

export async function getDataSourcesStatus(): Promise<DataSourcesStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/data-sources/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackDataSourcesStatus;
    }
    const payload: unknown = await response.json();
    return isDataSourcesStatusPayload(payload) ? payload : fallbackDataSourcesStatus;
  } catch {
    return fallbackDataSourcesStatus;
  }
}

export async function getAIStatus(): Promise<AIStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/ai/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackAIStatus;
    }
    const payload: unknown = await response.json();
    return isAIStatusPayload(payload) ? payload : fallbackAIStatus;
  } catch {
    return fallbackAIStatus;
  }
}

export async function getRuntimeSettings(): Promise<RuntimeSettingsPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/runtime-settings`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackRuntimeSettings;
    }
    const payload: unknown = await response.json();
    return isRuntimeSettingsPayload(payload) ? payload : fallbackRuntimeSettings;
  } catch {
    return fallbackRuntimeSettings;
  }
}

export async function updateRuntimeSettings(input: RuntimeSettingsUpdatePayload): Promise<RuntimeSettingsPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/runtime-settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    if (!response.ok) {
      return fallbackRuntimeSettings;
    }
    const payload: unknown = await response.json();
    return isRuntimeSettingsPayload(payload) ? payload : fallbackRuntimeSettings;
  } catch {
    return fallbackRuntimeSettings;
  }
}

export async function getStrategyLabStatus(): Promise<StrategyLabStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/status`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyLabStatus;
    }
    const payload: unknown = await response.json();
    return isStrategyLabStatusPayload(payload) ? payload : fallbackStrategyLabStatus;
  } catch {
    return fallbackStrategyLabStatus;
  }
}

export async function getStrategyEvaluation(): Promise<StrategyEvaluationPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/evaluation`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyEvaluation;
    }
    const payload: unknown = await response.json();
    return isStrategyEvaluationPayload(payload) ? payload : fallbackStrategyEvaluation;
  } catch {
    return fallbackStrategyEvaluation;
  }
}

export async function getStrategyAttribution(): Promise<StrategyAttributionPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/attribution`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyAttribution;
    }
    const payload: unknown = await response.json();
    return isStrategyAttributionPayload(payload) ? payload : fallbackStrategyAttribution;
  } catch {
    return fallbackStrategyAttribution;
  }
}

export async function getStrategyRegistry(): Promise<StrategyRegistryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/registry`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyRegistry;
    }
    const payload: unknown = await response.json();
    return isStrategyRegistryPayload(payload) ? payload : fallbackStrategyRegistry;
  } catch {
    return fallbackStrategyRegistry;
  }
}

export async function getStrategyCompetition(): Promise<StrategyCompetitionPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/competition`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyCompetition;
    }
    const payload: unknown = await response.json();
    return isStrategyCompetitionPayload(payload) ? payload : fallbackStrategyCompetition;
  } catch {
    return fallbackStrategyCompetition;
  }
}

export async function recordStrategyCompetitionSnapshot(): Promise<StrategyCompetitionSnapshotPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/competition/snapshot`, {
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isStrategyCompetitionSnapshotPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function getStrategyCompetitionSnapshots(): Promise<StrategyCompetitionSnapshotHistoryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/competition/snapshots`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyCompetitionSnapshots;
    }
    const payload: unknown = await response.json();
    return isStrategyCompetitionSnapshotHistoryPayload(payload) ? payload : fallbackStrategyCompetitionSnapshots;
  } catch {
    return fallbackStrategyCompetitionSnapshots;
  }
}

export async function getStrategyLifecycle(): Promise<StrategyLifecyclePayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/lifecycle`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyLifecycle;
    }
    const payload: unknown = await response.json();
    return isStrategyLifecyclePayload(payload) ? payload : fallbackStrategyLifecycle;
  } catch {
    return fallbackStrategyLifecycle;
  }
}

export async function getStrategyLifecycleAudit(): Promise<StrategyLifecycleAuditPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/lifecycle/audit`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyLifecycleAudit;
    }
    const payload: unknown = await response.json();
    return isStrategyLifecycleAuditPayload(payload) ? payload : fallbackStrategyLifecycleAudit;
  } catch {
    return fallbackStrategyLifecycleAudit;
  }
}

export async function getTradingSystemReadiness(): Promise<TradingSystemReadinessPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/system-readiness`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackTradingSystemReadiness;
    }
    const payload: unknown = await response.json();
    return isTradingSystemReadinessPayload(payload) ? payload : fallbackTradingSystemReadiness;
  } catch {
    return fallbackTradingSystemReadiness;
  }
}

export async function getStrategyAlphaIsolation(): Promise<StrategyAlphaIsolationPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/alpha-isolation`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyAlphaIsolation;
    }
    const payload: unknown = await response.json();
    return isStrategyAlphaIsolationPayload(payload) ? payload : fallbackStrategyAlphaIsolation;
  } catch {
    return fallbackStrategyAlphaIsolation;
  }
}

export async function getStrategyAlphaValidation(): Promise<StrategyAlphaValidationPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/alpha-validation`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyAlphaValidation;
    }
    const payload: unknown = await response.json();
    return isStrategyAlphaValidationPayload(payload) ? payload : fallbackStrategyAlphaValidation;
  } catch {
    return fallbackStrategyAlphaValidation;
  }
}

export async function getAlphaGateProgress(): Promise<AlphaGateProgressPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/alpha-gates`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackAlphaGateProgress;
    }
    const payload: unknown = await response.json();
    return isAlphaGateProgressPayload(payload) ? payload : fallbackAlphaGateProgress;
  } catch {
    return fallbackAlphaGateProgress;
  }
}

export async function getAlphaValidationSnapshots(): Promise<AlphaValidationSnapshotHistoryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/alpha-snapshots`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackAlphaValidationSnapshots;
    }
    const payload: unknown = await response.json();
    return isAlphaValidationSnapshotHistoryPayload(payload) ? payload : fallbackAlphaValidationSnapshots;
  } catch {
    return fallbackAlphaValidationSnapshots;
  }
}

export async function recordAlphaValidationSnapshot(): Promise<AlphaValidationSnapshotPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/alpha-snapshots/record`, {
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isAlphaValidationSnapshotPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function getAlphaValidationForecast(): Promise<AlphaValidationForecastPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/alpha-forecast`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackAlphaValidationForecast;
    }
    const payload: unknown = await response.json();
    return isAlphaValidationForecastPayload(payload) ? payload : fallbackAlphaValidationForecast;
  } catch {
    return fallbackAlphaValidationForecast;
  }
}

export async function getShadowReviewPacket(): Promise<ShadowReviewPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/shadow-review`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackShadowReview;
    }
    const payload: unknown = await response.json();
    return isShadowReviewPayload(payload) ? payload : fallbackShadowReview;
  } catch {
    return fallbackShadowReview;
  }
}

export async function getShadowObservations(): Promise<ShadowObservationSummaryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/shadow-observations`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackShadowObservationSummary;
    }
    const payload: unknown = await response.json();
    return isShadowObservationSummaryPayload(payload) ? payload : fallbackShadowObservationSummary;
  } catch {
    return fallbackShadowObservationSummary;
  }
}

export async function getShadowObservationHealth(): Promise<ShadowObservationHealthPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/shadow-observation-health`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackShadowObservationHealth;
    }
    const payload: unknown = await response.json();
    return isShadowObservationHealthPayload(payload) ? payload : fallbackShadowObservationHealth;
  } catch {
    return fallbackShadowObservationHealth;
  }
}

export async function getShadowValidation(): Promise<ShadowValidationPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/shadow-validation`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackShadowValidation;
    }
    const payload: unknown = await response.json();
    return isShadowValidationPayload(payload) ? payload : fallbackShadowValidation;
  } catch {
    return fallbackShadowValidation;
  }
}

export async function getShadowDailyReport(): Promise<ShadowDailyReportPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/shadow-daily-report`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackShadowDailyReport;
    }
    const payload: unknown = await response.json();
    return isShadowDailyReportPayload(payload) ? payload : fallbackShadowDailyReport;
  } catch {
    return fallbackShadowDailyReport;
  }
}

export async function getLiveSmallReviewPacket(): Promise<LiveSmallReviewPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/live-small-review`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackLiveSmallReview;
    }
    const payload: unknown = await response.json();
    return isLiveSmallReviewPayload(payload) ? payload : fallbackLiveSmallReview;
  } catch {
    return fallbackLiveSmallReview;
  }
}

export async function recordShadowObservation(): Promise<ShadowObservationPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/shadow-observations/record`, {
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isShadowObservationPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function approveShadowPromotion(
  input: StrategyShadowApprovalRequestPayload
): Promise<StrategyShadowApprovalPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/lifecycle/approve-shadow`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isStrategyShadowApprovalPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function approveLiveSmallPromotion(
  input: StrategyLiveSmallApprovalRequestPayload
): Promise<StrategyLiveSmallApprovalPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/lifecycle/approve-live-small`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isStrategyLiveSmallApprovalPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function approveStrategyKill(
  input: StrategyKillApprovalRequestPayload
): Promise<StrategyKillApprovalPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/lifecycle/approve-kill`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isStrategyKillApprovalPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function reconcileLifecycleWithAlphaValidation(): Promise<StrategyLifecycleReconcilePayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/lifecycle/reconcile`, {
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isStrategyLifecycleReconcilePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function getStrategyVersionControl(): Promise<StrategyVersionControlPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/version-control`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyVersionControl;
    }
    const payload: unknown = await response.json();
    return isStrategyVersionControlPayload(payload) ? payload : fallbackStrategyVersionControl;
  } catch {
    return fallbackStrategyVersionControl;
  }
}

export async function getStrategyRuntime(): Promise<StrategyRuntimePayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/runtime`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyRuntime;
    }
    const payload: unknown = await response.json();
    return isStrategyRuntimePayload(payload) ? payload : fallbackStrategyRuntime;
  } catch {
    return fallbackStrategyRuntime;
  }
}

export async function getStrategyExecutionAccounts(): Promise<StrategyExecutionAccountsPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/execution-accounts`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategyExecutionAccounts;
    }
    const payload: unknown = await response.json();
    return isStrategyExecutionAccountsPayload(payload) ? payload : fallbackStrategyExecutionAccounts;
  } catch {
    return fallbackStrategyExecutionAccounts;
  }
}

export type MarketQuotePayload = {
  ticker: string;
  price: number | null;
  currency: string;
  source: string;
  updated_at: string;
  change: number | null;
  change_percent: number | null;
  volume: number | null;
  is_fallback: boolean;
  message: string;
};

export type PriceHistoryBarPayload = {
  ticker: string;
  date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  volume: number | null;
  source: string;
};

export type FundamentalSnapshotPayload = {
  ticker: string;
  market_cap: number | null;
  pe_ratio: number | null;
  eps: number | null;
  price_to_sales: number | null;
  price_to_book: number | null;
  gross_margin: number | null;
  profit_margin: number | null;
  operating_margin: number | null;
  debt_to_equity: number | null;
  source: string;
  period_ending: string | null;
  updated_at: string;
  is_fallback: boolean;
  message: string;
};

export type MarketSnapshotPayload = {
  ticker: string;
  quote: MarketQuotePayload;
  fundamentals: FundamentalSnapshotPayload;
  history: PriceHistoryBarPayload[];
  provider_mode: string;
  data_sources: ProviderStatusPayload[];
};

export type MarketHistoryInterval = "1d" | "1W" | "1M";

function fallbackMarketSnapshot(ticker: string): MarketSnapshotPayload {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  return {
    ticker: normalizedTicker,
    quote: {
      ticker: normalizedTicker,
      price: null,
      currency: "USD",
      source: "offline",
      updated_at: "local",
      change: null,
      change_percent: null,
      volume: null,
      is_fallback: true,
      message: "后端 API 暂不可用，无法确认真实行情。"
    },
    fundamentals: {
      ticker: normalizedTicker,
      market_cap: null,
      pe_ratio: null,
      eps: null,
      price_to_sales: null,
      price_to_book: null,
      gross_margin: null,
      profit_margin: null,
      operating_margin: null,
      debt_to_equity: null,
      source: "offline",
      period_ending: null,
      updated_at: "local",
      is_fallback: true,
      message: "后端 API 暂不可用，无法确认基本面。"
    },
    history: [],
    provider_mode: "hybrid",
    data_sources: fallbackDataSourcesStatus.data_sources
  };
}

function isNullableNumber(value: unknown): value is number | null {
  return typeof value === "number" || value === null;
}

function isMarketQuotePayload(value: unknown): value is MarketQuotePayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isNullableNumber(value.price) &&
    typeof value.currency === "string" &&
    typeof value.source === "string" &&
    typeof value.updated_at === "string" &&
    isNullableNumber(value.change) &&
    isNullableNumber(value.change_percent) &&
    isNullableNumber(value.volume) &&
    typeof value.is_fallback === "boolean" &&
    typeof value.message === "string"
  );
}

function isPriceHistoryBarPayload(value: unknown): value is PriceHistoryBarPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.date === "string" &&
    isNullableNumber(value.open) &&
    isNullableNumber(value.high) &&
    isNullableNumber(value.low) &&
    isNullableNumber(value.close) &&
    isNullableNumber(value.volume) &&
    typeof value.source === "string"
  );
}

function isFundamentalSnapshotPayload(value: unknown): value is FundamentalSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isNullableNumber(value.market_cap) &&
    isNullableNumber(value.pe_ratio) &&
    isNullableNumber(value.eps) &&
    isNullableNumber(value.price_to_sales) &&
    isNullableNumber(value.price_to_book) &&
    isNullableNumber(value.gross_margin) &&
    isNullableNumber(value.profit_margin) &&
    isNullableNumber(value.operating_margin) &&
    isNullableNumber(value.debt_to_equity) &&
    typeof value.source === "string" &&
    (typeof value.period_ending === "string" || value.period_ending === null) &&
    typeof value.updated_at === "string" &&
    typeof value.is_fallback === "boolean" &&
    typeof value.message === "string"
  );
}

function isMarketSnapshotPayload(value: unknown): value is MarketSnapshotPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    isMarketQuotePayload(value.quote) &&
    isFundamentalSnapshotPayload(value.fundamentals) &&
    Array.isArray(value.history) &&
    value.history.every(isPriceHistoryBarPayload) &&
    typeof value.provider_mode === "string" &&
    Array.isArray(value.data_sources) &&
    value.data_sources.every(isProviderStatus)
  );
}

export async function getMarketHistory(
  ticker: string,
  interval: MarketHistoryInterval = "1d"
): Promise<PriceHistoryBarPayload[]> {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  try {
    const response = await fetch(
      `${getPublicApiBaseUrl()}/api/mvp/market/history/${normalizedTicker}?interval=${interval}`,
      {
        cache: "no-store"
      }
    );
    if (!response.ok) {
      return [];
    }
    const payload: unknown = await response.json();
    return Array.isArray(payload) && payload.every(isPriceHistoryBarPayload) ? payload : [];
  } catch {
    return [];
  }
}

export async function getMarketSnapshot(ticker: string): Promise<MarketSnapshotPayload> {
  const normalizedTicker = ticker.trim().toUpperCase() || "NVDA";
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/market/snapshot/${normalizedTicker}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackMarketSnapshot(normalizedTicker);
    }
    const payload: unknown = await response.json();
    return isMarketSnapshotPayload(payload) ? payload : fallbackMarketSnapshot(normalizedTicker);
  } catch {
    return fallbackMarketSnapshot(normalizedTicker);
  }
}

export type StrategyDefinitionPayload = {
  id: string;
  name: string;
  description: string;
  language: string;
  asset_class: string;
  default_symbol: string;
  resolution: string;
  enabled: boolean;
  parameters: StrategyParameterDefinitionPayload[];
};

export type StrategyParameterDefinitionPayload = {
  name: string;
  label: string;
  kind: "ticker" | "date" | "integer" | "number";
  default: string;
  min?: number | null;
  max?: number | null;
  required: boolean;
};

export type StrategyListPayload = {
  strategies: StrategyDefinitionPayload[];
};

export type BacktestStatisticsPayload = {
  total_net_profit: string | null;
  compounding_annual_return: string | null;
  sharpe_ratio: string | null;
  drawdown: string | null;
  win_rate: string | null;
  total_trades: string | null;
};

export type EquityPointPayload = {
  time: string;
  value: number;
};

export type BacktestResultPayload = {
  run_id: string;
  strategy_id: string;
  status: "success" | "unavailable" | "failed" | "timeout" | "malformed_result";
  engine: "lean" | "vectorbt";
  data_source: string | null;
  data_quality: "unknown" | "real_market_data" | "mock_data" | "deterministic_research_series";
  uses_real_market_data: boolean;
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  message: string;
  parameters: BacktestParametersPayload;
  statistics: BacktestStatisticsPayload;
  equity: EquityPointPayload[];
  logs: string[];
  output_directory: string;
};

export type LatestBacktestPayload = {
  latest: BacktestResultPayload | null;
};

export type BacktestParametersPayload = Record<string, string>;

export type BacktestHistoryItemPayload = {
  run_id: string;
  strategy_id: string;
  status: BacktestResultPayload["status"];
  engine: BacktestResultPayload["engine"];
  data_source: string | null;
  data_quality: BacktestResultPayload["data_quality"];
  uses_real_market_data: boolean;
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  parameters: BacktestParametersPayload;
  statistics: BacktestStatisticsPayload;
};

export type BacktestHistoryPayload = {
  history: BacktestHistoryItemPayload[];
};

export type CandidateBacktestRecommendation = "candidate" | "watch" | "reject";

export type CandidateBacktestItemPayload = {
  rank: number;
  ticker: string;
  recommendation: CandidateBacktestRecommendation;
  score: number;
  reason: string;
  run_id: string;
  status: string;
  engine: string;
  data_source: string | null;
  uses_real_market_data: boolean;
  total_net_profit: string | null;
  sharpe_ratio: string | null;
  drawdown: string | null;
  total_trades: string | null;
};

export type CandidateBacktestPayload = {
  strategy_id: string;
  candidate_count: number;
  real_market_candidate_count: number;
  best_ticker: string | null;
  items: CandidateBacktestItemPayload[];
  summary: string;
};

const backtestResultStatuses: BacktestResultPayload["status"][] = [
  "success",
  "unavailable",
  "failed",
  "timeout",
  "malformed_result"
];
const backtestEngines: BacktestResultPayload["engine"][] = ["lean", "vectorbt"];
const backtestDataQualities: BacktestResultPayload["data_quality"][] = [
  "unknown",
  "real_market_data",
  "mock_data",
  "deterministic_research_series"
];

const fallbackStrategies: StrategyListPayload = {
  strategies: [
    {
      id: "moving_average_cross",
      name: "MovingAverageCross",
      description: "AAPL 日线均线交叉示例策略，用于本地 LEAN 回测验证。",
      language: "Python",
      asset_class: "US Equity",
      default_symbol: "AAPL",
      resolution: "Daily",
      enabled: true,
      parameters: [
        { name: "symbol", label: "Ticker", kind: "ticker", default: "AAPL", required: true },
        { name: "start_date", label: "Start Date", kind: "date", default: "2020-01-01", required: true },
        { name: "end_date", label: "End Date", kind: "date", default: "2021-01-01", required: true },
        { name: "cash", label: "Initial Cash", kind: "number", default: "100000", min: 1000, max: 1000000000, required: true },
        { name: "fast_period", label: "Fast SMA", kind: "integer", default: "20", min: 2, max: 400, required: true },
        { name: "slow_period", label: "Slow SMA", kind: "integer", default: "50", min: 3, max: 600, required: true }
      ]
    }
  ]
};

function fallbackBacktestResult(
  strategyId: string,
  parameters: BacktestParametersPayload = {}
): BacktestResultPayload {
  const now = new Date().toISOString();
  return {
    run_id: `offline-${strategyId}`,
    strategy_id: strategyId,
    status: "unavailable",
    engine: "lean",
    data_source: null,
    data_quality: "unknown",
    uses_real_market_data: false,
    started_at: now,
    completed_at: now,
    duration_seconds: 0,
    message: "后端 API 暂不可用，无法运行 LEAN 回测。",
    parameters,
    statistics: {
      total_net_profit: null,
      compounding_annual_return: null,
      sharpe_ratio: null,
      drawdown: null,
      win_rate: null,
      total_trades: null
    },
    equity: [],
    logs: ["请确认后端 API、Docker 和 LEAN CLI 状态。"],
    output_directory: "local"
  };
}

function failedBacktestResult(
  strategyId: string,
  message: string,
  parameters: BacktestParametersPayload = {}
): BacktestResultPayload {
  const now = new Date().toISOString();
  return {
    run_id: `failed-${strategyId || "strategy"}`,
    strategy_id: strategyId,
    status: "failed",
    engine: "lean",
    data_source: null,
    data_quality: "unknown",
    uses_real_market_data: false,
    started_at: now,
    completed_at: now,
    duration_seconds: 0,
    message,
    parameters,
    statistics: {
      total_net_profit: null,
      compounding_annual_return: null,
      sharpe_ratio: null,
      drawdown: null,
      win_rate: null,
      total_trades: null
    },
    equity: [],
    logs: [message],
    output_directory: "local"
  };
}

function stringifyErrorDetail(value: unknown): string {
  if (typeof value === "string") {
    return value;
  }
  if (value === null || value === undefined) {
    return "后端未返回错误详情。";
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

async function readResponseErrorDetail(response: Response): Promise<string> {
  try {
    const payload: unknown = await response.clone().json();
    if (isRecord(payload) && "detail" in payload) {
      return stringifyErrorDetail(payload.detail);
    }
    return stringifyErrorDetail(payload);
  } catch {
    try {
      const text = await response.text();
      return text.trim() || response.statusText || "后端未返回错误详情。";
    } catch {
      return response.statusText || "后端未返回错误详情。";
    }
  }
}

function isStrategyDefinition(value: unknown): value is StrategyDefinitionPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.description === "string" &&
    typeof value.language === "string" &&
    typeof value.asset_class === "string" &&
    typeof value.default_symbol === "string" &&
    typeof value.resolution === "string" &&
    typeof value.enabled === "boolean" &&
    Array.isArray(value.parameters) &&
    value.parameters.every(isStrategyParameterDefinition)
  );
}

function isStrategyParameterDefinition(value: unknown): value is StrategyParameterDefinitionPayload {
  return (
    isRecord(value) &&
    typeof value.name === "string" &&
    typeof value.label === "string" &&
    ["ticker", "date", "integer", "number"].includes(String(value.kind)) &&
    typeof value.default === "string" &&
    (typeof value.min === "number" || value.min === null || value.min === undefined) &&
    (typeof value.max === "number" || value.max === null || value.max === undefined) &&
    typeof value.required === "boolean"
  );
}

function isStrategyListPayload(value: unknown): value is StrategyListPayload {
  return isRecord(value) && Array.isArray(value.strategies) && value.strategies.every(isStrategyDefinition);
}

function isBacktestStatistics(value: unknown): value is BacktestStatisticsPayload {
  return (
    isRecord(value) &&
    (typeof value.total_net_profit === "string" || value.total_net_profit === null) &&
    (typeof value.compounding_annual_return === "string" || value.compounding_annual_return === null) &&
    (typeof value.sharpe_ratio === "string" || value.sharpe_ratio === null) &&
    (typeof value.drawdown === "string" || value.drawdown === null) &&
    (typeof value.win_rate === "string" || value.win_rate === null) &&
    (typeof value.total_trades === "string" || value.total_trades === null)
  );
}

function isEquityPoint(value: unknown): value is EquityPointPayload {
  return isRecord(value) && typeof value.time === "string" && typeof value.value === "number";
}

function isBacktestParameters(value: unknown): value is BacktestParametersPayload {
  return isRecord(value) && Object.values(value).every((item) => typeof item === "string");
}

function isBacktestResultPayload(value: unknown): value is BacktestResultPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.status === "string" &&
    backtestResultStatuses.includes(value.status as BacktestResultPayload["status"]) &&
    typeof value.engine === "string" &&
    backtestEngines.includes(value.engine as BacktestResultPayload["engine"]) &&
    (typeof value.data_source === "string" || value.data_source === null) &&
    typeof value.data_quality === "string" &&
    backtestDataQualities.includes(value.data_quality as BacktestResultPayload["data_quality"]) &&
    typeof value.uses_real_market_data === "boolean" &&
    typeof value.started_at === "string" &&
    typeof value.completed_at === "string" &&
    typeof value.duration_seconds === "number" &&
    typeof value.message === "string" &&
    isBacktestParameters(value.parameters) &&
    isBacktestStatistics(value.statistics) &&
    Array.isArray(value.equity) &&
    value.equity.every(isEquityPoint) &&
    Array.isArray(value.logs) &&
    value.logs.every((item) => typeof item === "string") &&
    typeof value.output_directory === "string"
  );
}

function isLatestBacktestPayload(value: unknown): value is LatestBacktestPayload {
  return isRecord(value) && (value.latest === null || isBacktestResultPayload(value.latest));
}

function isBacktestHistoryItem(value: unknown): value is BacktestHistoryItemPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.status === "string" &&
    backtestResultStatuses.includes(value.status as BacktestResultPayload["status"]) &&
    typeof value.engine === "string" &&
    backtestEngines.includes(value.engine as BacktestResultPayload["engine"]) &&
    (typeof value.data_source === "string" || value.data_source === null) &&
    typeof value.data_quality === "string" &&
    backtestDataQualities.includes(value.data_quality as BacktestResultPayload["data_quality"]) &&
    typeof value.uses_real_market_data === "boolean" &&
    typeof value.started_at === "string" &&
    typeof value.completed_at === "string" &&
    typeof value.duration_seconds === "number" &&
    isBacktestParameters(value.parameters) &&
    isBacktestStatistics(value.statistics)
  );
}

function isBacktestHistoryPayload(value: unknown): value is BacktestHistoryPayload {
  return isRecord(value) && Array.isArray(value.history) && value.history.every(isBacktestHistoryItem);
}

function isCandidateBacktestItem(value: unknown): value is CandidateBacktestItemPayload {
  return (
    isRecord(value) &&
    typeof value.rank === "number" &&
    typeof value.ticker === "string" &&
    ["candidate", "watch", "reject"].includes(String(value.recommendation)) &&
    typeof value.score === "number" &&
    typeof value.reason === "string" &&
    typeof value.run_id === "string" &&
    typeof value.status === "string" &&
    typeof value.engine === "string" &&
    (typeof value.data_source === "string" || value.data_source === null) &&
    typeof value.uses_real_market_data === "boolean" &&
    (typeof value.total_net_profit === "string" || value.total_net_profit === null) &&
    (typeof value.sharpe_ratio === "string" || value.sharpe_ratio === null) &&
    (typeof value.drawdown === "string" || value.drawdown === null) &&
    (typeof value.total_trades === "string" || value.total_trades === null)
  );
}

function isCandidateBacktestPayload(value: unknown): value is CandidateBacktestPayload {
  return (
    isRecord(value) &&
    typeof value.strategy_id === "string" &&
    typeof value.candidate_count === "number" &&
    typeof value.real_market_candidate_count === "number" &&
    (typeof value.best_ticker === "string" || value.best_ticker === null) &&
    Array.isArray(value.items) &&
    value.items.every(isCandidateBacktestItem) &&
    typeof value.summary === "string"
  );
}

export async function getStrategyCatalog(): Promise<StrategyListPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/strategies`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackStrategies;
    }
    const payload: unknown = await response.json();
    return isStrategyListPayload(payload) ? payload : fallbackStrategies;
  } catch {
    return fallbackStrategies;
  }
}

export async function getLatestBacktest(): Promise<LatestBacktestPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests/latest`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return { latest: null };
    }
    const payload: unknown = await response.json();
    return isLatestBacktestPayload(payload) ? payload : { latest: null };
  } catch {
    return { latest: null };
  }
}

export async function getBacktestHistory(limit = 10): Promise<BacktestHistoryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests/history?limit=${limit}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return { history: [] };
    }
    const payload: unknown = await response.json();
    return isBacktestHistoryPayload(payload) ? payload : { history: [] };
  } catch {
    return { history: [] };
  }
}

export async function runStrategyBacktest(
  strategyId: string,
  parameters: BacktestParametersPayload = {}
): Promise<BacktestResultPayload> {
  const normalizedStrategyId = strategyId.trim();
  if (!normalizedStrategyId) {
    return failedBacktestResult("", "请选择策略后再运行回测。", parameters);
  }

  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/backtests`, {
      body: JSON.stringify({ strategy_id: normalizedStrategyId, parameters }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      const detail = await readResponseErrorDetail(response);
      const message = `请求失败（${response.status}）：${detail}`;
      return failedBacktestResult(normalizedStrategyId, message, parameters);
    }
    const payload: unknown = await response.json();
    return isBacktestResultPayload(payload) ? payload : fallbackBacktestResult(normalizedStrategyId, parameters);
  } catch {
    return fallbackBacktestResult(normalizedStrategyId, parameters);
  }
}

export async function runCandidateBacktests(
  strategyId: string,
  tickers: string[],
  parameters: BacktestParametersPayload = {}
): Promise<CandidateBacktestPayload> {
  const normalizedStrategyId = strategyId.trim();
  const normalizedTickers = tickers.map((ticker) => ticker.trim().toUpperCase()).filter(Boolean);
  if (!normalizedStrategyId || normalizedTickers.length < 2) {
    return {
      strategy_id: normalizedStrategyId,
      candidate_count: 0,
      real_market_candidate_count: 0,
      best_ticker: null,
      items: [],
      summary: "请选择策略并至少输入两个候选标的。"
    };
  }

  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/strategy-lab/candidate-backtests`, {
      body: JSON.stringify({ strategy_id: normalizedStrategyId, tickers: normalizedTickers, parameters }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      const detail = await readResponseErrorDetail(response);
      return {
        strategy_id: normalizedStrategyId,
        candidate_count: 0,
        real_market_candidate_count: 0,
        best_ticker: null,
        items: [],
        summary: `请求失败（${response.status}）：${detail}`
      };
    }
    const payload: unknown = await response.json();
    return isCandidateBacktestPayload(payload)
      ? payload
      : {
          strategy_id: normalizedStrategyId,
          candidate_count: 0,
          real_market_candidate_count: 0,
          best_ticker: null,
          items: [],
          summary: "候选池回测返回格式不可识别。"
        };
  } catch {
    return {
      strategy_id: normalizedStrategyId,
      candidate_count: 0,
      real_market_candidate_count: 0,
      best_ticker: null,
      items: [],
      summary: "后端 API 暂不可用，无法运行候选池回测。"
    };
  }
}

export type WorkspaceSummaryPayload = {
  team_id: string;
  team_name: string;
  portfolio_id: string;
  portfolio_name: string;
  position_count: number;
  watchlist_count: number;
  note_count: number;
};

export type PositionPayload = {
  id: string;
  ticker: string;
  quantity: number;
  average_cost: number;
  currency: string;
  price: number | null;
  market_value: number;
  weight: number;
  updated_at: string;
};

export type PortfolioPayload = {
  id: string;
  name: string;
  base_currency: string;
  total_market_value: number;
  positions: PositionPayload[];
};

export type PositionInputPayload = {
  ticker: string;
  quantity: number;
  average_cost: number;
  currency?: string;
};

export type PositionImportPayload = {
  imported_count: number;
  errors: Array<{ field: string; message: string; row: number }>;
  portfolio: PortfolioPayload | null;
};

export type WatchlistItemPayload = {
  id: string;
  ticker: string;
  thesis: string;
  created_at: string;
};

export type WatchlistPayload = {
  items: WatchlistItemPayload[];
};

export type WatchlistInputPayload = {
  ticker: string;
  thesis: string;
};

export type NotePayload = {
  id: string;
  ticker: string | null;
  title: string;
  body: string;
  created_at: string;
};

export type NotesPayload = {
  notes: NotePayload[];
};

export type NoteInputPayload = {
  ticker?: string | null;
  title: string;
  body: string;
};

export type ResearchNotePayload = {
  ai_run_id: string;
  note: NotePayload;
};

const fallbackPortfolio: PortfolioPayload = {
  id: "offline-portfolio",
  name: "主组合",
  base_currency: "USD",
  total_market_value: 0,
  positions: []
};

function isPositionPayload(value: unknown): value is PositionPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.ticker === "string" &&
    typeof value.quantity === "number" &&
    typeof value.average_cost === "number" &&
    typeof value.currency === "string" &&
    isNullableNumber(value.price) &&
    typeof value.market_value === "number" &&
    typeof value.weight === "number" &&
    typeof value.updated_at === "string"
  );
}

function isPortfolioPayload(value: unknown): value is PortfolioPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.base_currency === "string" &&
    typeof value.total_market_value === "number" &&
    Array.isArray(value.positions) &&
    value.positions.every(isPositionPayload)
  );
}

function isImportPayload(value: unknown): value is PositionImportPayload {
  return (
    isRecord(value) &&
    typeof value.imported_count === "number" &&
    Array.isArray(value.errors) &&
    value.errors.every(
      (item) =>
        isRecord(item) &&
        typeof item.row === "number" &&
        typeof item.field === "string" &&
        typeof item.message === "string"
    ) &&
    (value.portfolio === null || isPortfolioPayload(value.portfolio))
  );
}

function isWatchlistItem(value: unknown): value is WatchlistItemPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.ticker === "string" &&
    typeof value.thesis === "string" &&
    typeof value.created_at === "string"
  );
}

function isWatchlistPayload(value: unknown): value is WatchlistPayload {
  return isRecord(value) && Array.isArray(value.items) && value.items.every(isWatchlistItem);
}

function isNotePayload(value: unknown): value is NotePayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    (typeof value.ticker === "string" || value.ticker === null) &&
    typeof value.title === "string" &&
    typeof value.body === "string" &&
    typeof value.created_at === "string"
  );
}

function isNotesPayload(value: unknown): value is NotesPayload {
  return isRecord(value) && Array.isArray(value.notes) && value.notes.every(isNotePayload);
}

function isResearchNotePayload(value: unknown): value is ResearchNotePayload {
  return isRecord(value) && typeof value.ai_run_id === "string" && isNotePayload(value.note);
}

function isPaperAccountPayload(value: unknown): value is PaperAccountPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    typeof value.mode === "string" &&
    typeof value.starting_cash === "number" &&
    typeof value.cash === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.equity === "number" &&
    typeof value.updated_at === "string"
  );
}

function isPaperCandidatePayload(value: unknown): value is PaperCandidatePayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.strategy_id === "string" &&
    typeof value.ticker === "string" &&
    typeof value.action === "string" &&
    typeof value.rank === "number" &&
    typeof value.confidence === "number" &&
    typeof value.thesis === "string" &&
    typeof value.risk_notes === "string" &&
    typeof value.evidence_summary === "string" &&
    typeof value.proposed_quantity === "number" &&
    typeof value.status === "string" &&
    typeof value.created_at === "string"
  );
}

function isPaperOrderPayload(value: unknown): value is PaperOrderPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.strategy_id === "string" &&
    (typeof value.candidate_id === "string" || value.candidate_id === null) &&
    typeof value.ticker === "string" &&
    typeof value.side === "string" &&
    typeof value.order_type === "string" &&
    typeof value.quantity === "number" &&
    typeof value.status === "string" &&
    (typeof value.fill_price === "number" || value.fill_price === null) &&
    typeof value.realized_pnl === "number" &&
    (typeof value.rejection_reason === "string" || value.rejection_reason === null) &&
    (typeof value.core_order_id === "string" || value.core_order_id === null) &&
    (typeof value.core_intent_id === "string" || value.core_intent_id === null) &&
    (typeof value.risk_status === "string" || value.risk_status === null) &&
    (typeof value.risk_code === "string" || value.risk_code === null) &&
    (typeof value.risk_reason === "string" || value.risk_reason === null) &&
    Array.isArray(value.state_history) &&
    value.state_history.every(
      (item) =>
        isRecord(item) &&
        typeof item.state === "string" &&
        typeof item.recorded_at === "string" &&
        typeof item.reason === "string"
    ) &&
    typeof value.submitted_at === "string" &&
    (typeof value.filled_at === "string" || value.filled_at === null)
  );
}

function isPaperSchedulerStatusPayload(value: unknown): value is PaperSchedulerStatusPayload {
  return (
    isRecord(value) &&
    typeof value.enabled === "boolean" &&
    typeof value.running === "boolean" &&
    typeof value.job_count === "number" &&
    typeof value.job_id === "string" &&
    typeof value.cron === "string" &&
    typeof value.timezone === "string" &&
    (typeof value.next_run_at === "string" || value.next_run_at === null) &&
    (typeof value.next_run_will_execute === "boolean" || value.next_run_will_execute === null) &&
    (typeof value.next_run_execution_gate === "string" || value.next_run_execution_gate === null) &&
    (typeof value.next_run_trading_day === "string" || value.next_run_trading_day === null) &&
    (typeof value.next_run_gate_reason === "string" || value.next_run_gate_reason === null) &&
    (typeof value.next_actionable_run_at === "string" || value.next_actionable_run_at === null) &&
    (typeof value.next_actionable_trading_day === "string" || value.next_actionable_trading_day === null) &&
    (typeof value.next_actionable_execution_gate === "string" || value.next_actionable_execution_gate === null) &&
    (typeof value.next_actionable_gate_reason === "string" || value.next_actionable_gate_reason === null) &&
    typeof value.last_checked_at === "string" &&
    typeof value.can_run_now === "boolean" &&
    typeof value.execution_gate === "string" &&
    typeof value.market_date === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.is_market_session === "boolean" &&
    typeof value.session_closed === "boolean" &&
    typeof value.calendar_provider === "string" &&
    typeof value.gate_reason === "string"
  );
}

function isPaperMarketSessionPayload(value: unknown): value is PaperMarketSessionPayload {
  return (
    isRecord(value) &&
    typeof value.market_date === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.is_market_session === "boolean" &&
    typeof value.session_closed === "boolean" &&
    typeof value.calendar_provider === "string" &&
    typeof value.reason === "string"
  );
}

function isPaperOperationsStatusPayload(value: unknown): value is PaperOperationsStatusPayload {
  return (
    isRecord(value) &&
    typeof value.trading_day === "string" &&
    typeof value.run_state === "string" &&
    typeof value.health_status === "string" &&
    (typeof value.latest_run_id === "string" || value.latest_run_id === null) &&
    (typeof value.latest_run_trading_day === "string" || value.latest_run_trading_day === null) &&
    (typeof value.latest_run_status === "string" || value.latest_run_status === null) &&
    (typeof value.today_run_id === "string" || value.today_run_id === null) &&
    (typeof value.review_id === "string" || value.review_id === null) &&
    (typeof value.latest_error === "string" || value.latest_error === null) &&
    typeof value.can_retry_today === "boolean" &&
    typeof value.event_ledger_ready === "boolean" &&
    typeof value.latest_run_event_count === "number" &&
    typeof value.legacy_manual_future_run_count === "number" &&
    (typeof value.latest_legacy_manual_future_trading_day === "string" ||
      value.latest_legacy_manual_future_trading_day === null) &&
    Array.isArray(value.data_quality_warnings) &&
    value.data_quality_warnings.every((item) => typeof item === "string") &&
    (value.latest_scheduler_decision === "executed" ||
      value.latest_scheduler_decision === "skipped" ||
      value.latest_scheduler_decision === "failed" ||
      value.latest_scheduler_decision === null) &&
    (typeof value.latest_scheduler_decision_at === "string" || value.latest_scheduler_decision_at === null) &&
    (typeof value.latest_scheduler_decision_trading_day === "string" ||
      value.latest_scheduler_decision_trading_day === null) &&
    (typeof value.latest_scheduler_decision_reason === "string" ||
      value.latest_scheduler_decision_reason === null) &&
    (typeof value.latest_scheduler_decision_summary === "string" ||
      value.latest_scheduler_decision_summary === null) &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    typeof value.recommended_action === "string" &&
    typeof value.summary === "string"
  );
}

function isPaperOperationsHistoryItemPayload(value: unknown): value is PaperOperationsHistoryItemPayload {
  return (
    isRecord(value) &&
    typeof value.trading_day === "string" &&
    typeof value.run_id === "string" &&
    typeof value.status === "string" &&
    typeof value.health_status === "string" &&
    typeof value.event_count === "number" &&
    typeof value.has_review === "boolean" &&
    typeof value.candidates_count === "number" &&
    typeof value.orders_count === "number" &&
    typeof value.positions_count === "number" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    (typeof value.error_message === "string" || value.error_message === null) &&
    typeof value.started_at === "string" &&
    (typeof value.finished_at === "string" || value.finished_at === null)
  );
}

function isPaperOperationsHistoryPayload(value: unknown): value is PaperOperationsHistoryPayload {
  return (
    isRecord(value) &&
    typeof value.window_size === "number" &&
    typeof value.completed_days === "number" &&
    typeof value.failed_days === "number" &&
    typeof value.blocked_days === "number" &&
    typeof value.replayable_days === "number" &&
    typeof value.review_days === "number" &&
    typeof value.completion_rate === "number" &&
    typeof value.replay_rate === "number" &&
    typeof value.latest_health_status === "string" &&
    Array.isArray(value.items) &&
    value.items.every(isPaperOperationsHistoryItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperOperationsRepairItemPayload(value: unknown): value is PaperOperationsRepairItemPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.status === "string" &&
    typeof value.event_created === "boolean" &&
    (typeof value.topic === "string" || value.topic === null) &&
    typeof value.reason === "string"
  );
}

function isPaperOperationsRepairPayload(value: unknown): value is PaperOperationsRepairPayload {
  return (
    isRecord(value) &&
    typeof value.scanned_runs === "number" &&
    typeof value.repaired_runs === "number" &&
    typeof value.skipped_runs === "number" &&
    Array.isArray(value.items) &&
    value.items.every(isPaperOperationsRepairItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperOperationsQuarantineItemPayload(value: unknown): value is PaperOperationsQuarantineItemPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.status === "string" &&
    typeof value.previous_trigger === "string" &&
    typeof value.new_trigger === "string" &&
    typeof value.audit_event_created === "boolean" &&
    typeof value.reason === "string"
  );
}

function isPaperOperationsQuarantinePayload(value: unknown): value is PaperOperationsQuarantinePayload {
  return (
    isRecord(value) &&
    typeof value.scanned_runs === "number" &&
    typeof value.quarantined_runs === "number" &&
    typeof value.skipped_runs === "number" &&
    Array.isArray(value.items) &&
    value.items.every(isPaperOperationsQuarantineItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperReviewTrendItemPayload(value: unknown): value is PaperReviewTrendItemPayload {
  return (
    isRecord(value) &&
    typeof value.trading_day === "string" &&
    typeof value.equity === "number" &&
    typeof value.daily_pnl === "number" &&
    typeof value.daily_return === "number" &&
    typeof value.cash === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.trade_count === "number" &&
    typeof value.win_rate === "number" &&
    typeof value.expectancy === "number" &&
    typeof value.readiness === "string"
  );
}

function isPaperReviewTrendPayload(value: unknown): value is PaperReviewTrendPayload {
  return (
    isRecord(value) &&
    typeof value.sample_size === "number" &&
    typeof value.positive_expectancy_days === "number" &&
    typeof value.consecutive_positive_expectancy_days === "number" &&
    typeof value.average_expectancy === "number" &&
    typeof value.latest_expectancy === "number" &&
    typeof value.total_realized_pnl === "number" &&
    typeof value.total_unrealized_pnl === "number" &&
    typeof value.latest_readiness === "string" &&
    Array.isArray(value.items) &&
    value.items.every(isPaperReviewTrendItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperSimulationItemPayload(value: unknown): value is PaperSimulationItemPayload {
  return (
    isRecord(value) &&
    typeof value.trading_day === "string" &&
    typeof value.run_status === "string" &&
    typeof value.orders_count === "number" &&
    typeof value.candidates_count === "number" &&
    typeof value.positions_count === "number" &&
    (typeof value.review_id === "string" || value.review_id === null)
  );
}

function isPaperSimulationPayload(value: unknown): value is PaperSimulationPayload {
  return (
    isRecord(value) &&
    typeof value.scenario === "string" &&
    typeof value.start_date === "string" &&
    typeof value.days_requested === "number" &&
    typeof value.days_completed === "number" &&
    typeof value.days_skipped === "number" &&
    typeof value.review_day_count === "number" &&
    typeof value.consecutive_positive_expectancy_days === "number" &&
    typeof value.latest_expectancy === "number" &&
    typeof value.average_expectancy === "number" &&
    typeof value.event_chain_count === "number" &&
    typeof value.alpha_ready === "boolean" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    Array.isArray(value.items) &&
    value.items.every(isPaperSimulationItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperExecutionRejectionReasonPayload(value: unknown): value is PaperExecutionRejectionReasonPayload {
  return (
    isRecord(value) &&
    typeof value.risk_code === "string" &&
    typeof value.count === "number" &&
    (typeof value.latest_reason === "string" || value.latest_reason === null)
  );
}

function isPaperExecutionDiagnosticsPayload(value: unknown): value is PaperExecutionDiagnosticsPayload {
  return (
    isRecord(value) &&
    typeof value.order_count === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.rejected_order_count === "number" &&
    typeof value.buy_order_count === "number" &&
    typeof value.sell_order_count === "number" &&
    typeof value.closed_trade_count === "number" &&
    typeof value.fill_rate === "number" &&
    typeof value.rejection_rate === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.average_realized_pnl === "number" &&
    (typeof value.latest_rejection_code === "string" || value.latest_rejection_code === null) &&
    typeof value.max_daily_order_rejections === "number" &&
    typeof value.max_daily_order_buy_rejections === "number" &&
    typeof value.max_daily_order_sell_rejections === "number" &&
    Array.isArray(value.rejection_reasons) &&
    value.rejection_reasons.every(isPaperExecutionRejectionReasonPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperRiskProfilePayload(value: unknown): value is PaperRiskProfilePayload {
  return (
    isRecord(value) &&
    typeof value.risk_engine === "string" &&
    typeof value.max_order_notional === "number" &&
    typeof value.max_position_weight === "number" &&
    typeof value.max_daily_orders === "number" &&
    typeof value.exit_take_profit_pct === "number" &&
    typeof value.exit_stop_loss_pct === "number" &&
    typeof value.summary === "string"
  );
}

function isPaperRiskLimitReviewPayload(value: unknown): value is PaperRiskLimitReviewPayload {
  return (
    isRecord(value) &&
    typeof value.status === "string" &&
    typeof value.current_max_daily_orders === "number" &&
    typeof value.recommended_paper_max_daily_orders === "number" &&
    typeof value.live_change_allowed === "boolean" &&
    typeof value.max_daily_order_rejections === "number" &&
    typeof value.max_daily_order_buy_rejections === "number" &&
    typeof value.max_daily_order_sell_rejections === "number" &&
    typeof value.filled_order_count === "number" &&
    typeof value.closed_trade_count === "number" &&
    typeof value.sample_collection_blocked === "boolean" &&
    Array.isArray(value.blockers) &&
    value.blockers.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

function isPaperRiskLimitApplyPayload(value: unknown): value is PaperRiskLimitApplyPayload {
  return (
    isRecord(value) &&
    typeof value.applied === "boolean" &&
    typeof value.previous_max_daily_orders === "number" &&
    typeof value.applied_max_daily_orders === "number" &&
    typeof value.live_change_allowed === "boolean" &&
    typeof value.audit_event_created === "boolean" &&
    typeof value.summary === "string"
  );
}

function isPaperActionPlanItemPayload(value: unknown): value is PaperActionPlanItemPayload {
  return (
    isRecord(value) &&
    typeof value.priority === "number" &&
    typeof value.action_code === "string" &&
    typeof value.title === "string" &&
    typeof value.detail === "string" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string") &&
    (value.projected_gate_impacts === undefined ||
      (Array.isArray(value.projected_gate_impacts) &&
        value.projected_gate_impacts.every(
          (item) =>
            isRecord(item) &&
            typeof item.gate === "string" &&
            typeof item.label === "string" &&
            typeof item.projected_increment === "number" &&
            typeof item.current_remaining === "number" &&
            typeof item.projected_remaining === "number" &&
            typeof item.unit === "string"
        )))
  );
}

function isPaperActionPlanPayload(value: unknown): value is PaperActionPlanPayload {
  return (
    isRecord(value) &&
    typeof value.readiness === "string" &&
    typeof value.primary_action === "string" &&
    Array.isArray(value.items) &&
    value.items.every(isPaperActionPlanItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperActionExecutionPayload(value: unknown): value is PaperActionExecutionPayload {
  return (
    isRecord(value) &&
    typeof value.executed === "boolean" &&
    (value.queued === undefined || typeof value.queued === "boolean") &&
    (value.status === undefined || typeof value.status === "string") &&
    typeof value.action_code === "string" &&
    typeof value.next_primary_action === "string" &&
    (value.result === null || isRecord(value.result)) &&
    typeof value.summary === "string"
  );
}

function isPaperStrategyReviewItemPayload(value: unknown): value is PaperStrategyReviewItemPayload {
  return (
    isRecord(value) &&
    typeof value.event_id === "string" &&
    typeof value.action_code === "string" &&
    typeof value.title === "string" &&
    typeof value.detail === "string" &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string") &&
    Array.isArray(value.inverted_tickers) &&
    value.inverted_tickers.every((item) => typeof item === "string") &&
    typeof value.review_status === "string" &&
    typeof value.created_at === "string"
  );
}

function isPaperStrategyReviewsPayload(value: unknown): value is PaperStrategyReviewsPayload {
  return (
    isRecord(value) &&
    typeof value.review_count === "number" &&
    Array.isArray(value.items) &&
    value.items.every(isPaperStrategyReviewItemPayload) &&
    typeof value.summary === "string"
  );
}

function isPaperRunPayload(value: unknown): value is PaperRunPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.trigger === "string" &&
    typeof value.status === "string" &&
    typeof value.candidates_count === "number" &&
    typeof value.orders_count === "number" &&
    typeof value.positions_count === "number" &&
    (typeof value.review_id === "string" || value.review_id === null) &&
    (typeof value.error_message === "string" || value.error_message === null) &&
    typeof value.started_at === "string" &&
    (typeof value.finished_at === "string" || value.finished_at === null)
  );
}

function isPaperRunsPayload(value: unknown): value is PaperRunsPayload {
  return isRecord(value) && Array.isArray(value.runs) && value.runs.every(isPaperRunPayload);
}

function isEventLedgerTopicCount(value: unknown): value is EventLedgerTopicCountPayload {
  return isRecord(value) && typeof value.topic === "string" && typeof value.count === "number";
}

function isEventLedgerTradeExplanation(value: unknown): value is EventLedgerTradeExplanationPayload {
  return (
    isRecord(value) &&
    (typeof value.ticker === "string" || value.ticker === null) &&
    (typeof value.strategy_id === "string" || value.strategy_id === null) &&
    (typeof value.candidate_id === "string" || value.candidate_id === null) &&
    (typeof value.decision === "string" || value.decision === null) &&
    (typeof value.explanation === "string" || value.explanation === null) &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string") &&
    (value.evidence_items === undefined ||
      (Array.isArray(value.evidence_items) &&
        value.evidence_items.every(
          (item) =>
            isRecord(item) &&
            typeof item.ticker === "string" &&
            typeof item.title === "string" &&
            typeof item.summary === "string" &&
            typeof item.source === "string" &&
            typeof item.source_url === "string" &&
            typeof item.observed_at === "string" &&
            (typeof item.form === "string" || item.form === null) &&
            (typeof item.filing_date === "string" || item.filing_date === null) &&
            (typeof item.accession_number === "string" || item.accession_number === null)
        ))) &&
    isRecord(value.backtest) &&
    Object.values(value.backtest).every(
      (item) => typeof item === "string" || typeof item === "number" || typeof item === "boolean" || item === null
    )
  );
}

function isEventLedgerReplayChain(value: unknown): value is EventLedgerReplayChainPayload {
  return (
    isRecord(value) &&
    typeof value.correlation_id === "string" &&
    (typeof value.ticker === "string" || value.ticker === null) &&
    Array.isArray(value.topics) &&
    value.topics.every((item) => typeof item === "string") &&
    Array.isArray(value.order_states) &&
    value.order_states.every((item) => typeof item === "string") &&
    (typeof value.terminal_state === "string" || value.terminal_state === null) &&
    (value.integrity_warnings === undefined ||
      (Array.isArray(value.integrity_warnings) &&
        value.integrity_warnings.every((item) => typeof item === "string"))) &&
    (value.trade_explanation === undefined ||
      value.trade_explanation === null ||
      isEventLedgerTradeExplanation(value.trade_explanation)) &&
    typeof value.event_count === "number"
  );
}

function isEventLedgerReplay(value: unknown): value is EventLedgerReplayPayload {
  return (
    isRecord(value) &&
    typeof value.run_id === "string" &&
    typeof value.event_count === "number" &&
    typeof value.chain_count === "number" &&
    Array.isArray(value.chains) &&
    value.chains.every(isEventLedgerReplayChain)
  );
}

function isPaperEventLedgerPayload(value: unknown): value is PaperEventLedgerPayload {
  return (
    isRecord(value) &&
    typeof value.total_event_count === "number" &&
    (typeof value.latest_run_id === "string" || value.latest_run_id === null) &&
    (typeof value.latest_run_status === "string" || value.latest_run_status === null) &&
    typeof value.latest_run_event_count === "number" &&
    Array.isArray(value.latest_topic_counts) &&
    value.latest_topic_counts.every(isEventLedgerTopicCount) &&
    typeof value.latest_correlation_count === "number" &&
    (value.integrity_ready === undefined || typeof value.integrity_ready === "boolean") &&
    (value.integrity_warnings === undefined ||
      (Array.isArray(value.integrity_warnings) &&
        value.integrity_warnings.every((item) => typeof item === "string"))) &&
    (value.traceable_chain_count === undefined || typeof value.traceable_chain_count === "number") &&
    (value.complete_order_chain_count === undefined || typeof value.complete_order_chain_count === "number") &&
    (value.broken_chain_count === undefined || typeof value.broken_chain_count === "number") &&
    (value.traceability_ratio === undefined || typeof value.traceability_ratio === "number") &&
    typeof value.replay_ready === "boolean" &&
    Array.isArray(value.warnings) &&
    value.warnings.every((item) => typeof item === "string") &&
    typeof value.summary === "string" &&
    (value.latest_replay === null || isEventLedgerReplay(value.latest_replay))
  );
}

function isPaperPositionPayload(value: unknown): value is PaperPositionPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.ticker === "string" &&
    typeof value.quantity === "number" &&
    typeof value.average_cost === "number" &&
    (typeof value.last_price === "number" || value.last_price === null) &&
    typeof value.market_value === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.updated_at === "string"
  );
}

function isPaperReviewPayload(value: unknown): value is PaperReviewPayload {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.trading_day === "string" &&
    typeof value.equity === "number" &&
    typeof value.cash === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.trade_count === "number" &&
    typeof value.win_rate === "number" &&
    typeof value.average_win === "number" &&
    typeof value.average_loss === "number" &&
    typeof value.expectancy === "number" &&
    typeof value.readiness === "string" &&
    typeof value.notes === "string" &&
    typeof value.created_at === "string"
  );
}

function isMarketEventTracePayload(value: unknown): value is MarketEventTracePayload {
  return (
    isRecord(value) &&
    Array.isArray(value.chain_events) &&
    value.chain_events.every(
      (item) =>
        isRecord(item) &&
        typeof item.event_id === "string" &&
        typeof item.topic === "string" &&
        typeof item.sequence === "number" &&
        (typeof item.causation_id === "string" || item.causation_id === null) &&
        isRecord(item.payload)
    ) &&
    typeof value.event_id === "string" &&
    (typeof value.run_id === "string" || value.run_id === null) &&
    (typeof value.trading_day === "string" || value.trading_day === null) &&
    typeof value.published_at === "string" &&
    typeof value.correlation_id === "string" &&
    (typeof value.ticker === "string" || value.ticker === null) &&
    (typeof value.strategy_id === "string" || value.strategy_id === null) &&
    (typeof value.event_type === "string" || value.event_type === null) &&
    (typeof value.summary === "string" || value.summary === null) &&
    (typeof value.confidence === "number" || value.confidence === null) &&
    (typeof value.impact_score === "number" || value.impact_score === null) &&
    (typeof value.source === "string" || value.source === null) &&
    typeof value.evidence_quality === "string" &&
    ["unknown", "real_market_data", "mock_data", "deterministic_research_series", "mixed"].includes(
      value.evidence_quality
    ) &&
    typeof value.uses_real_market_evidence === "boolean" &&
    Array.isArray(value.topics) &&
    value.topics.every((item) => typeof item === "string") &&
    (typeof value.trade_intent_side === "string" || value.trade_intent_side === null) &&
    (typeof value.trade_intent_reason === "string" || value.trade_intent_reason === null) &&
    (typeof value.risk_decision === "string" || value.risk_decision === null) &&
    (typeof value.risk_reason === "string" || value.risk_reason === null) &&
    (typeof value.order_state === "string" || value.order_state === null) &&
    (typeof value.explanation === "string" || value.explanation === null) &&
    Array.isArray(value.evidence) &&
    value.evidence.every((item) => typeof item === "string") &&
    Array.isArray(value.evidence_items) &&
    value.evidence_items.every(
      (item) =>
        isRecord(item) &&
        (typeof item.ticker === "string" || item.ticker === null) &&
        (typeof item.title === "string" || item.title === null) &&
        (typeof item.summary === "string" || item.summary === null) &&
        (typeof item.source === "string" || item.source === null) &&
        (typeof item.source_url === "string" || item.source_url === null) &&
        (typeof item.observed_at === "string" || item.observed_at === null) &&
        (typeof item.form === "string" || item.form === null) &&
        (typeof item.filing_date === "string" || item.filing_date === null) &&
        (typeof item.accession_number === "string" || item.accession_number === null)
    )
  );
}

function isPaperMarketEventsPayload(value: unknown): value is PaperMarketEventsPayload {
  return (
    isRecord(value) &&
    typeof value.total_event_count === "number" &&
    typeof value.filtered_event_count === "number" &&
    Array.isArray(value.events) &&
    value.events.every(isMarketEventTracePayload) &&
    typeof value.summary === "string"
  );
}

function isPaperExitWatchItemPayload(value: unknown): value is PaperExitWatchItemPayload {
  return (
    isRecord(value) &&
    typeof value.ticker === "string" &&
    typeof value.quantity === "number" &&
    typeof value.return_pct === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.trigger === "string" &&
    typeof value.triggered === "boolean" &&
    typeof value.threshold_pct === "number" &&
    typeof value.distance_to_trigger_pct === "number" &&
    typeof value.next_exit_quantity === "number"
  );
}

function isPaperTradingSummaryPayload(value: unknown): value is PaperTradingSummaryPayload {
  return (
    isRecord(value) &&
    isPaperAccountPayload(value.account) &&
    Array.isArray(value.candidates) &&
    value.candidates.every(isPaperCandidatePayload) &&
    Array.isArray(value.orders) &&
    value.orders.every(isPaperOrderPayload) &&
    Array.isArray(value.positions) &&
    value.positions.every(isPaperPositionPayload) &&
    (value.latest_review === null || isPaperReviewPayload(value.latest_review))
  );
}

function isPaperDailyReportPayload(value: unknown): value is PaperDailyReportPayload {
  return (
    isRecord(value) &&
    typeof value.trading_day === "string" &&
    typeof value.run_state === "string" &&
    typeof value.health_status === "string" &&
    typeof value.recommended_action === "string" &&
    typeof value.scheduler_running === "boolean" &&
    (typeof value.scheduler_next_run_at === "string" || value.scheduler_next_run_at === null) &&
    (typeof value.scheduler_next_run_will_execute === "boolean" || value.scheduler_next_run_will_execute === null) &&
    (typeof value.scheduler_next_run_execution_gate === "string" ||
      value.scheduler_next_run_execution_gate === null) &&
    (typeof value.scheduler_next_actionable_run_at === "string" ||
      value.scheduler_next_actionable_run_at === null) &&
    (typeof value.scheduler_next_actionable_trading_day === "string" ||
      value.scheduler_next_actionable_trading_day === null) &&
    (typeof value.scheduler_next_actionable_execution_gate === "string" ||
      value.scheduler_next_actionable_execution_gate === null) &&
    (typeof value.estimated_sessions_to_alpha_ready === "number" ||
      value.estimated_sessions_to_alpha_ready === null) &&
    (typeof value.limiting_alpha_gate === "string" || value.limiting_alpha_gate === null) &&
    typeof value.account_equity === "number" &&
    typeof value.cash === "number" &&
    typeof value.realized_pnl === "number" &&
    typeof value.unrealized_pnl === "number" &&
    typeof value.daily_pnl === "number" &&
    typeof value.daily_return === "number" &&
    typeof value.candidate_count === "number" &&
    typeof value.actionable_candidate_count === "number" &&
    typeof value.ordered_candidate_count === "number" &&
    typeof value.dismissed_candidate_count === "number" &&
    typeof value.order_count === "number" &&
    typeof value.open_position_count === "number" &&
    typeof value.latest_expectancy === "number" &&
    typeof value.average_expectancy === "number" &&
    typeof value.consecutive_positive_expectancy_days === "number" &&
    typeof value.review_latest_expectancy === "number" &&
    typeof value.review_average_expectancy === "number" &&
    typeof value.review_consecutive_positive_expectancy_days === "number" &&
    typeof value.event_ledger_ready === "boolean" &&
    typeof value.alpha_ready === "boolean" &&
    Array.isArray(value.alpha_blockers) &&
    value.alpha_blockers.every((item) => typeof item === "string") &&
    Array.isArray(value.open_alpha_gates) &&
    value.open_alpha_gates.every(isAlphaGateProgressItemPayload) &&
    Array.isArray(value.exit_watchlist) &&
    value.exit_watchlist.every(isPaperExitWatchItemPayload) &&
    Array.isArray(value.data_quality_warnings) &&
    value.data_quality_warnings.every((item) => typeof item === "string") &&
    typeof value.summary === "string"
  );
}

export async function getPortfolio(): Promise<PortfolioPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPortfolio;
    }
    const payload: unknown = await response.json();
    return isPortfolioPayload(payload) ? payload : fallbackPortfolio;
  } catch {
    return fallbackPortfolio;
  }
}

export async function upsertPosition(input: PositionInputPayload): Promise<PositionPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio/positions`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "PUT"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isPositionPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function deletePosition(ticker: string): Promise<boolean> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio/positions/${ticker.trim().toUpperCase()}`, {
      method: "DELETE"
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function importPositionsCsv(content: string): Promise<PositionImportPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/portfolio/import`, {
      body: JSON.stringify({ content }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      const detail = await readResponseErrorDetail(response);
      return { imported_count: 0, errors: [{ row: 0, field: "request", message: detail }], portfolio: null };
    }
    const payload: unknown = await response.json();
    return isImportPayload(payload) ? payload : { imported_count: 0, errors: [], portfolio: null };
  } catch {
    return { imported_count: 0, errors: [{ row: 0, field: "network", message: "后端 API 暂不可用。" }], portfolio: null };
  }
}

export async function getWatchlist(): Promise<WatchlistPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/watchlist`, { cache: "no-store" });
    if (!response.ok) {
      return { items: [] };
    }
    const payload: unknown = await response.json();
    return isWatchlistPayload(payload) ? payload : { items: [] };
  } catch {
    return { items: [] };
  }
}

export async function upsertWatchlistItem(input: WatchlistInputPayload): Promise<WatchlistItemPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/watchlist`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isWatchlistItem(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function deleteWatchlistItem(ticker: string): Promise<boolean> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/watchlist/${ticker.trim().toUpperCase()}`, {
      method: "DELETE"
    });
    return response.ok;
  } catch {
    return false;
  }
}

export async function getNotes(): Promise<NotesPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/notes`, { cache: "no-store" });
    if (!response.ok) {
      return { notes: [] };
    }
    const payload: unknown = await response.json();
    return isNotesPayload(payload) ? payload : { notes: [] };
  } catch {
    return { notes: [] };
  }
}

export async function createNote(input: NoteInputPayload): Promise<NotePayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/notes`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isNotePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function saveResearchResultAsNote(
  prompt: string,
  result: ResearchResultPayload
): Promise<ResearchNotePayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/research/notes`, {
      body: JSON.stringify({ prompt, result }),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isResearchNotePayload(payload) ? payload : null;
  } catch {
    return null;
  }
}

export async function getPaperTradingSummary(): Promise<PaperTradingSummaryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/summary`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperTradingSummary;
    }
    const payload: unknown = await response.json();
    return isPaperTradingSummaryPayload(payload) ? payload : fallbackPaperTradingSummary;
  } catch {
    return fallbackPaperTradingSummary;
  }
}

export async function getPaperDailyReport(): Promise<PaperDailyReportPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/daily-report`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperDailyReport;
    }
    const payload: unknown = await response.json();
    return isPaperDailyReportPayload(payload) ? payload : fallbackPaperDailyReport;
  } catch {
    return fallbackPaperDailyReport;
  }
}

export async function getPaperSchedulerStatus(): Promise<PaperSchedulerStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/scheduler`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperSchedulerStatus;
    }
    const payload: unknown = await response.json();
    return isPaperSchedulerStatusPayload(payload) ? payload : fallbackPaperSchedulerStatus;
  } catch {
    return fallbackPaperSchedulerStatus;
  }
}

export async function getPaperMarketSession(): Promise<PaperMarketSessionPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/market-session`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperMarketSession;
    }
    const payload: unknown = await response.json();
    return isPaperMarketSessionPayload(payload) ? payload : fallbackPaperMarketSession;
  } catch {
    return fallbackPaperMarketSession;
  }
}

export async function getPaperOperationsStatus(): Promise<PaperOperationsStatusPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/operations`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperOperationsStatus;
    }
    const payload: unknown = await response.json();
    return isPaperOperationsStatusPayload(payload) ? payload : fallbackPaperOperationsStatus;
  } catch {
    return fallbackPaperOperationsStatus;
  }
}

export async function getPaperOperationsHistory(): Promise<PaperOperationsHistoryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/operations/history`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackPaperOperationsHistory;
    }
    const payload: unknown = await response.json();
    return isPaperOperationsHistoryPayload(payload) ? payload : fallbackPaperOperationsHistory;
  } catch {
    return fallbackPaperOperationsHistory;
  }
}

export async function repairPaperEventLedger(): Promise<PaperOperationsRepairPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/operations/repair-ledger`, {
      method: "POST"
    });
    if (!response.ok) {
      return fallbackPaperOperationsRepair;
    }
    const payload: unknown = await response.json();
    return isPaperOperationsRepairPayload(payload) ? payload : fallbackPaperOperationsRepair;
  } catch {
    return fallbackPaperOperationsRepair;
  }
}

export async function quarantineLegacyPaperRuns(): Promise<PaperOperationsQuarantinePayload> {
  try {
    const response = await fetch(
      `${getPublicApiBaseUrl()}/api/mvp/paper-trading/operations/quarantine-legacy-runs`,
      { method: "POST" }
    );
    if (!response.ok) {
      return fallbackPaperOperationsQuarantine;
    }
    const payload: unknown = await response.json();
    return isPaperOperationsQuarantinePayload(payload) ? payload : fallbackPaperOperationsQuarantine;
  } catch {
    return fallbackPaperOperationsQuarantine;
  }
}

export async function getPaperReviewTrend(): Promise<PaperReviewTrendPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/review-trend`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperReviewTrend;
    }
    const payload: unknown = await response.json();
    return isPaperReviewTrendPayload(payload) ? payload : fallbackPaperReviewTrend;
  } catch {
    return fallbackPaperReviewTrend;
  }
}

export async function runPaperSimulationLab(
  input: PaperSimulationRequestPayload = { days: 5, scenario: "bullish" }
): Promise<PaperSimulationPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/simulation/run`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return fallbackPaperSimulation;
    }
    const payload: unknown = await response.json();
    return isPaperSimulationPayload(payload) ? payload : fallbackPaperSimulation;
  } catch {
    return fallbackPaperSimulation;
  }
}

export async function getPaperExecutionDiagnostics(): Promise<PaperExecutionDiagnosticsPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/execution-diagnostics`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackPaperExecutionDiagnostics;
    }
    const payload: unknown = await response.json();
    return isPaperExecutionDiagnosticsPayload(payload) ? payload : fallbackPaperExecutionDiagnostics;
  } catch {
    return fallbackPaperExecutionDiagnostics;
  }
}

export async function getPaperRiskProfile(): Promise<PaperRiskProfilePayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/risk-profile`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperRiskProfile;
    }
    const payload: unknown = await response.json();
    return isPaperRiskProfilePayload(payload) ? payload : fallbackPaperRiskProfile;
  } catch {
    return fallbackPaperRiskProfile;
  }
}

export async function getPaperRiskLimitReview(): Promise<PaperRiskLimitReviewPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/risk-limit-review`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackPaperRiskLimitReview;
    }
    const payload: unknown = await response.json();
    return isPaperRiskLimitReviewPayload(payload) ? payload : fallbackPaperRiskLimitReview;
  } catch {
    return fallbackPaperRiskLimitReview;
  }
}

export async function applyPaperRiskLimitRecommendation(): Promise<PaperRiskLimitApplyPayload> {
  try {
    const response = await fetch(
      `${getPublicApiBaseUrl()}/api/mvp/paper-trading/risk-limit-review/apply-paper-recommendation`,
      { method: "POST" }
    );
    if (!response.ok) {
      return fallbackPaperRiskLimitApply;
    }
    const payload: unknown = await response.json();
    return isPaperRiskLimitApplyPayload(payload) ? payload : fallbackPaperRiskLimitApply;
  } catch {
    return fallbackPaperRiskLimitApply;
  }
}

export async function getPaperActionPlan(): Promise<PaperActionPlanPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/action-plan`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperActionPlan;
    }
    const payload: unknown = await response.json();
    return isPaperActionPlanPayload(payload) ? payload : fallbackPaperActionPlan;
  } catch {
    return fallbackPaperActionPlan;
  }
}

export async function executePaperPrimaryAction(): Promise<PaperActionExecutionPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/action-plan/execute-primary`, {
      method: "POST"
    });
    if (!response.ok) {
      return fallbackPaperActionExecution;
    }
    const payload: unknown = await response.json();
    return isPaperActionExecutionPayload(payload) ? payload : fallbackPaperActionExecution;
  } catch {
    return fallbackPaperActionExecution;
  }
}

export async function getPaperStrategyReviews(): Promise<PaperStrategyReviewsPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/strategy-reviews`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackPaperStrategyReviews;
    }
    const payload: unknown = await response.json();
    return isPaperStrategyReviewsPayload(payload) ? payload : fallbackPaperStrategyReviews;
  } catch {
    return fallbackPaperStrategyReviews;
  }
}

export async function getPaperRuns(): Promise<PaperRunsPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/runs`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperRuns;
    }
    const payload: unknown = await response.json();
    return isPaperRunsPayload(payload) ? payload : fallbackPaperRuns;
  } catch {
    return fallbackPaperRuns;
  }
}

export async function getPaperEventLedger(): Promise<PaperEventLedgerPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/event-ledger`, { cache: "no-store" });
    if (!response.ok) {
      return fallbackPaperEventLedger;
    }
    const payload: unknown = await response.json();
    return isPaperEventLedgerPayload(payload) ? payload : fallbackPaperEventLedger;
  } catch {
    return fallbackPaperEventLedger;
  }
}

export async function getPaperMarketEvents(ticker?: string): Promise<PaperMarketEventsPayload> {
  try {
    const params = new URLSearchParams({ limit: "80" });
    if (ticker?.trim()) {
      params.set("ticker", ticker.trim().toUpperCase());
    }
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/market-events?${params}`, {
      cache: "no-store"
    });
    if (!response.ok) {
      return fallbackPaperMarketEvents;
    }
    const payload: unknown = await response.json();
    return isPaperMarketEventsPayload(payload) ? payload : fallbackPaperMarketEvents;
  } catch {
    return fallbackPaperMarketEvents;
  }
}

export async function runPaperTradingDailyLoop(): Promise<PaperTradingSummaryPayload> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/daily-run`, {
      method: "POST"
    });
    if (!response.ok) {
      return fallbackPaperTradingSummary;
    }
    const payload: unknown = await response.json();
    return isPaperTradingSummaryPayload(payload) ? payload : fallbackPaperTradingSummary;
  } catch {
    return fallbackPaperTradingSummary;
  }
}

export async function submitPaperOrder(input: PaperOrderInputPayload): Promise<PaperOrderPayload | null> {
  try {
    const response = await fetch(`${getPublicApiBaseUrl()}/api/mvp/paper-trading/orders`, {
      body: JSON.stringify(input),
      headers: { "Content-Type": "application/json" },
      method: "POST"
    });
    if (!response.ok) {
      return null;
    }
    const payload: unknown = await response.json();
    return isPaperOrderPayload(payload) ? payload : null;
  } catch {
    return null;
  }
}
