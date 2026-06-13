import os
import subprocess
import sys
import textwrap

from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import (
    CoreEventLog,
    MemberRole,
    PaperRun,
    PaperRunStatus,
    PaperRunTrigger,
    Portfolio,
    Position,
    Team,
    User,
)


def test_create_db_and_tables_registers_models_on_cold_import(tmp_path):
    database_path = tmp_path / "cold_import.db"
    script = textwrap.dedent(
        f"""
        import sqlite3

        from app.db.session import create_db_and_tables

        create_db_and_tables()

        connection = sqlite3.connect({str(database_path)!r})
        tables = {{
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }}
        missing = {{"team", "portfolio", "position"}} - tables
        if missing:
            raise SystemExit(f"Missing tables: {{sorted(missing)}}")
        """
    )
    env = {
        **os.environ,
        "AI_STOCKS_DATABASE_URL": f"sqlite:///{database_path}",
    }

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        cwd=os.getcwd(),
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr + result.stdout


def test_team_user_portfolio_position_can_be_persisted():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        team = Team(name="Core Research")
        user = User(email="analyst@example.com", display_name="Analyst")
        portfolio = Portfolio(team=team, name="Main Book", base_currency="USD")
        position = Position(
            portfolio=portfolio,
            ticker="AAPL",
            quantity=10,
            average_cost=150,
            currency="USD",
        )
        session.add(team)
        session.add(user)
        session.add(portfolio)
        session.add(position)
        session.commit()

    with Session(engine) as session:
        stored = session.exec(select(Position).where(Position.ticker == "AAPL")).one()
        assert stored.quantity == 10
        assert stored.portfolio.name == "Main Book"


def test_member_role_values_are_stable():
    assert MemberRole.owner.value == "owner"
    assert MemberRole.analyst.value == "analyst"
    assert MemberRole.viewer.value == "viewer"


def test_paper_run_and_core_event_log_can_be_persisted():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        team = Team(name="Run Ledger")
        session.add(team)
        session.commit()
        session.refresh(team)

        run = PaperRun(
            team_id=team.id,
            trading_day="2026-06-13",
            trigger=PaperRunTrigger.manual,
            status=PaperRunStatus.started,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        event = CoreEventLog(
            team_id=team.id,
            run_id=run.id,
            event_id="event-1",
            topic="order_state",
            sequence=1,
            correlation_id="corr-1",
            payload_json='{"current_state":"filled"}',
        )
        session.add(event)
        session.commit()

    with Session(engine) as session:
        stored_run = session.exec(select(PaperRun)).one()
        stored_event = session.exec(select(CoreEventLog)).one()

        assert stored_run.trigger == PaperRunTrigger.manual
        assert stored_run.status == PaperRunStatus.started
        assert stored_event.run_id == stored_run.id
        assert stored_event.topic == "order_state"
