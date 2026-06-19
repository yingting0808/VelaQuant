from datetime import timedelta

from sqlmodel import Session, SQLModel, create_engine

from app.domain.models import CoreEventLog, PaperRun, PaperRunStatus, PaperRunTrigger
from app.services.event_ledger import get_event_ledger_status, list_market_event_traces
from app.services.workspace import get_or_create_default_workspace


TRADING_DAY = "2026-06-12"


def test_event_ledger_marks_complete_order_chain_integrity_ready():
    with make_session() as session:
        team_id, run = _workspace_run(session)
        _add_event(session, team_id, run, event_id="market", topic="market_event", sequence=1)
        _add_event(session, team_id, run, event_id="input", topic="strategy_input", sequence=2, causation_id="market")
        _add_event(session, team_id, run, event_id="intent", topic="trade_intent", sequence=3, causation_id="input")
        _add_event(session, team_id, run, event_id="risk", topic="risk_decision", sequence=4, causation_id="intent")
        _add_event(
            session,
            team_id,
            run,
            event_id="filled",
            topic="order_state",
            sequence=5,
            causation_id="risk",
            payload_json='{"state":"filled","ticker":"NVDA"}',
        )
        session.commit()

        status = get_event_ledger_status(session)

        assert status.latest_run_trading_day == TRADING_DAY
        assert status.replay_ready is True
        assert status.integrity_ready is True
        assert status.integrity_warnings == []
        assert status.traceable_chain_count == 1
        assert status.complete_order_chain_count == 1
        assert status.broken_chain_count == 0
        assert status.traceability_ratio == 1.0
        assert status.latest_replay is not None
        assert status.latest_replay.chains[0].integrity_warnings == []


def test_event_ledger_blocks_replay_when_order_chain_is_missing_trade_intent():
    with make_session() as session:
        team_id, run = _workspace_run(session)
        _add_event(session, team_id, run, event_id="market", topic="market_event", sequence=1)
        _add_event(session, team_id, run, event_id="input", topic="strategy_input", sequence=2, causation_id="market")
        _add_event(
            session,
            team_id,
            run,
            event_id="filled",
            topic="order_state",
            sequence=3,
            causation_id="input",
            payload_json='{"state":"filled","ticker":"NVDA"}',
        )
        session.commit()

        status = get_event_ledger_status(session)

        assert status.replay_ready is False
        assert status.integrity_ready is False
        assert "chain_missing_trade_intent" in status.integrity_warnings
        assert status.traceable_chain_count == 1
        assert status.complete_order_chain_count == 0
        assert status.broken_chain_count == 1
        assert status.traceability_ratio == 0.0
        assert status.latest_replay is not None
        assert "chain_missing_trade_intent" in status.latest_replay.chains[0].integrity_warnings


def test_event_ledger_blocks_replay_when_causation_reference_is_broken():
    with make_session() as session:
        team_id, run = _workspace_run(session)
        _add_event(session, team_id, run, event_id="market", topic="market_event", sequence=1)
        _add_event(session, team_id, run, event_id="input", topic="strategy_input", sequence=2, causation_id="market")
        _add_event(session, team_id, run, event_id="intent", topic="trade_intent", sequence=3, causation_id="missing")
        session.commit()

        status = get_event_ledger_status(session)

        assert status.replay_ready is False
        assert status.integrity_ready is False
        assert "broken_causation_reference" in status.integrity_warnings
        assert status.latest_replay is not None
        assert "broken_causation_reference" in status.latest_replay.chains[0].integrity_warnings


def test_event_ledger_status_ignores_future_trading_day_runs_for_readiness_baseline():
    with make_session() as session:
        team_id, today_run = _workspace_run(session, trading_day="2026-06-13")
        _add_event(
            session,
            team_id,
            today_run,
            event_id="today-audit",
            topic="run_audit",
            sequence=1,
            correlation_id="today-run",
            payload_json='{"status":"skipped"}',
        )
        _team_id, future_run = _workspace_run(session, trading_day="2026-06-30")
        _add_event(session, team_id, future_run, event_id="future-market", topic="market_event", sequence=1)
        _add_event(session, team_id, future_run, event_id="future-input", topic="strategy_input", sequence=2, causation_id="future-market")
        _add_event(session, team_id, future_run, event_id="future-intent", topic="trade_intent", sequence=3, causation_id="future-input")
        session.commit()

        status = get_event_ledger_status(session, as_of_trading_day="2026-06-13")

        assert status.latest_run_id == today_run.id
        assert status.latest_run_trading_day == "2026-06-13"
        assert status.latest_run_status == "completed"
        assert status.latest_run_event_count == 1
        assert status.latest_topic_counts[0].topic == "run_audit"


def test_event_ledger_prefers_latest_substantive_trade_run_over_newer_skipped_audit_run():
    with make_session() as session:
        team_id, trade_run = _workspace_run(session)
        _add_event(session, team_id, trade_run, event_id="market", topic="market_event", sequence=1)
        _add_event(session, team_id, trade_run, event_id="input", topic="strategy_input", sequence=2, causation_id="market")
        _add_event(session, team_id, trade_run, event_id="intent", topic="trade_intent", sequence=3, causation_id="input")
        _add_event(session, team_id, trade_run, event_id="risk", topic="risk_decision", sequence=4, causation_id="intent")
        _add_event(
            session,
            team_id,
            trade_run,
            event_id="filled",
            topic="order_state",
            sequence=5,
            causation_id="risk",
            payload_json='{"state":"filled","ticker":"NVDA"}',
        )
        _team_id, skipped_run = _workspace_run(session)
        skipped_run.status = PaperRunStatus.skipped
        skipped_run.started_at = trade_run.started_at + timedelta(minutes=5)
        session.add(skipped_run)
        _add_event(
            session,
            team_id,
            skipped_run,
            event_id="skipped-audit",
            topic="run_audit",
            sequence=1,
            correlation_id="skipped-run",
            payload_json='{"status":"skipped"}',
        )
        session.commit()

        status = get_event_ledger_status(session, as_of_trading_day=TRADING_DAY)

        assert status.latest_run_id == trade_run.id
        assert status.latest_run_status == "completed"
        assert status.latest_run_event_count == 5
        assert [item.topic for item in status.latest_topic_counts] == [
            "market_event",
            "order_state",
            "risk_decision",
            "strategy_input",
            "trade_intent",
        ]
        assert status.latest_replay is not None
        assert status.latest_replay.chains[0].order_states == ["filled"]


def test_event_ledger_replay_exposes_trade_explanation_for_candidate_review():
    with make_session() as session:
        team_id, run = _workspace_run(session)
        _add_event(session, team_id, run, event_id="market", topic="market_event", sequence=1)
        _add_event(session, team_id, run, event_id="input", topic="strategy_input", sequence=2, causation_id="market")
        _add_event(session, team_id, run, event_id="intent", topic="trade_intent", sequence=3, causation_id="input")
        _add_event(
            session,
            team_id,
            run,
            event_id="explain",
            topic="trade_explanation",
            sequence=4,
            causation_id="intent",
            payload_json=(
                '{"ticker":"AAPL","strategy_id":"deterministic_watchlist_v1",'
                '"candidate_id":"candidate-aapl",'
                '"decision":"candidate","explanation":"AAPL promoted by real backtest evidence.",'
                '"evidence":["positive expectancy","source=openbb_yfinance"],'
                '"evidence_items":[{"ticker":"AAPL","title":"AAPL 10-Q filed",'
                '"summary":"AAPL filed 10-Q with SEC EDGAR.","source":"sec_edgar",'
                '"source_url":"https://www.sec.gov/aapl-10q","observed_at":"2026-06-12T00:00:00Z",'
                '"form":"10-Q","filing_date":"2026-06-01","accession_number":"0000320193-26-000001"}],'
                '"backtest":{"run_id":"bt-aapl","total_net_profit":"38.60%",'
                '"sharpe_ratio":"1.42","drawdown":"-4.10%","total_trades":"12"}}'
            ),
        )
        session.commit()

        status = get_event_ledger_status(session)

        assert status.latest_replay is not None
        chain = status.latest_replay.chains[0]
        assert chain.trade_explanation is not None
        assert chain.trade_explanation.ticker == "AAPL"
        assert chain.trade_explanation.strategy_id == "deterministic_watchlist_v1"
        assert chain.trade_explanation.candidate_id == "candidate-aapl"
        assert chain.trade_explanation.decision == "candidate"
        assert chain.trade_explanation.explanation == "AAPL promoted by real backtest evidence."
        assert chain.trade_explanation.evidence == ["positive expectancy", "source=openbb_yfinance"]
        assert chain.trade_explanation.evidence_items[0]["source"] == "sec_edgar"
        assert chain.trade_explanation.evidence_items[0]["summary"] == "AAPL filed 10-Q with SEC EDGAR."
        assert chain.trade_explanation.backtest["run_id"] == "bt-aapl"
        assert chain.trade_explanation.backtest["total_net_profit"] == "38.60%"


def test_market_event_traces_filter_by_ticker_and_expose_downstream_chain():
    with make_session() as session:
        team_id, run = _workspace_run(session)
        _add_event(
            session,
            team_id,
            run,
            event_id="market-intc",
            topic="market_event",
            sequence=1,
            correlation_id="corr-intc",
            payload_json=(
                '{"ticker":"INTC","event_type":"price_action","summary":"INTC fast SMA crossed above slow SMA.",'
                '"evidence_items":[{"ticker":"INTC","title":"INTC moving average snapshot",'
                '"summary":"Fast SMA 31.20 is above slow SMA 30.70.","source":"mock_market_data",'
                '"source_url":"mock://market-data/INTC","observed_at":"2026-06-12T20:30:00Z"}],'
                '"confidence":0.74,"impact_score":0.66,"metadata":{"strategy_id":"moving_average_cross",'
                '"fast_sma":31.2,"slow_sma":30.7,"source":"mock_market_data"}}'
            ),
        )
        _add_event(
            session,
            team_id,
            run,
            event_id="input-intc",
            topic="strategy_input",
            sequence=2,
            causation_id="market-intc",
            correlation_id="corr-intc",
            payload_json='{"market_event":{"ticker":"INTC"},"portfolio":{"cash":100000}}',
        )
        _add_event(
            session,
            team_id,
            run,
            event_id="intent-intc",
            topic="trade_intent",
            sequence=3,
            causation_id="input-intc",
            correlation_id="corr-intc",
            payload_json=(
                '{"ticker":"INTC","side":"buy","notional":2000,'
                '"reason":"INTC moving-average cross event: fast_sma=31.20 > slow_sma=30.70"}'
            ),
        )
        _add_event(
            session,
            team_id,
            run,
            event_id="risk-intc",
            topic="risk_decision",
            sequence=4,
            causation_id="intent-intc",
            correlation_id="corr-intc",
            payload_json='{"status":"approved","code":"approved","reason":"within paper risk limits"}',
        )
        _add_event(
            session,
            team_id,
            run,
            event_id="order-intc",
            topic="order_state",
            sequence=5,
            causation_id="risk-intc",
            correlation_id="corr-intc",
            payload_json='{"state":"filled","ticker":"INTC","quantity":64}',
        )
        _add_event(
            session,
            team_id,
            run,
            event_id="explain-intc",
            topic="trade_explanation",
            sequence=6,
            causation_id="intent-intc",
            correlation_id="corr-intc",
            payload_json=(
                '{"ticker":"INTC","strategy_id":"moving_average_cross","decision":"candidate",'
                '"explanation":"INTC entered because momentum evidence passed the strategy gate.",'
                '"evidence":["fast_sma_above_slow_sma","source=mock_market_data"]}'
            ),
        )
        _add_event(
            session,
            team_id,
            run,
            event_id="market-spcx",
            topic="market_event",
            sequence=7,
            correlation_id="corr-spcx",
            payload_json='{"ticker":"SPCX","summary":"SPCX evidence update.","confidence":0.6,"impact_score":0.5}',
        )
        session.commit()

        traces = list_market_event_traces(session, ticker="intc")

        assert traces.total_event_count == 2
        assert traces.filtered_event_count == 1
        assert len(traces.events) == 1
        trace = traces.events[0]
        assert trace.ticker == "INTC"
        assert trace.strategy_id == "moving_average_cross"
        assert trace.summary == "INTC fast SMA crossed above slow SMA."
        assert trace.confidence == 0.74
        assert trace.impact_score == 0.66
        assert trace.correlation_id == "corr-intc"
        assert trace.topics == [
            "market_event",
            "strategy_input",
            "trade_intent",
            "risk_decision",
            "order_state",
            "trade_explanation",
        ]
        assert trace.trade_intent_side == "buy"
        assert trace.trade_intent_reason.startswith("INTC moving-average cross")
        assert trace.risk_decision == "approved"
        assert trace.risk_reason == "within paper risk limits"
        assert trace.order_state == "filled"
        assert trace.evidence_items[0]["title"] == "INTC moving average snapshot"
        assert trace.evidence_items[0]["summary"] == "Fast SMA 31.20 is above slow SMA 30.70."
        assert trace.evidence_items[0]["source"] == "mock_market_data"
        assert trace.evidence_items[0]["source_url"] == "mock://market-data/INTC"
        assert trace.evidence_quality == "mock_data"
        assert trace.uses_real_market_evidence is False
        assert trace.explanation == "INTC entered because momentum evidence passed the strategy gate."
        assert trace.evidence == ["fast_sma_above_slow_sma", "source=mock_market_data"]
        assert [event.topic for event in trace.chain_events] == trace.topics
        assert trace.chain_events[0].payload["summary"] == "INTC fast SMA crossed above slow SMA."
        assert trace.chain_events[2].payload["reason"].startswith("INTC moving-average cross")
        assert trace.chain_events[3].payload["status"] == "approved"
        assert trace.chain_events[4].payload["state"] == "filled"


def make_session() -> Session:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return Session(engine)


def _workspace_run(session: Session, trading_day: str = TRADING_DAY) -> tuple[object, PaperRun]:
    workspace = get_or_create_default_workspace(session)
    run = PaperRun(
        team_id=workspace.team.id,
        trading_day=trading_day,
        trigger=PaperRunTrigger.manual,
        status=PaperRunStatus.completed,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return workspace.team.id, run


def _add_event(
    session: Session,
    team_id: object,
    run: PaperRun,
    *,
    event_id: str,
    topic: str,
    sequence: int,
    causation_id: str | None = None,
    payload_json: str = '{"ticker":"NVDA"}',
    correlation_id: str = "corr-1",
) -> None:
    session.add(
        CoreEventLog(
            team_id=team_id,
            run_id=run.id,
            event_id=event_id,
            topic=topic,
            sequence=sequence,
            correlation_id=correlation_id,
            causation_id=causation_id,
            payload_json=payload_json,
        )
    )
