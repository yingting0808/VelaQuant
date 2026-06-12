# AI US Stocks Tool MVP Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable first MVP vertical slice for the internal AI US stocks research and portfolio monitoring tool.

**Architecture:** Use a monorepo with a FastAPI backend in `apps/api` and a Next.js App Router frontend in `apps/web`. The backend owns permissions, audit logs, portfolio/watchlist data, import parsing, mockable market data adapters, alert generation, and a deterministic LangGraph research workflow; the frontend renders the professional dashboard shell with a persistent AI sidecar.

**Tech Stack:** Next.js App Router, TypeScript, Tailwind, shadcn/ui-ready layout, TanStack-style tables, FastAPI, SQLModel, Postgres-compatible SQL, pytest, Playwright, Docker Compose, LangGraph.

---

## Scope Check

The approved spec covers multiple future subsystems. This plan intentionally implements only the first testable MVP foundation:

- Included: app scaffolding, Docker Compose, backend domain model, role permissions, audit logs, watchlists, portfolios, CSV import, mock market data adapter, event alerts, deterministic AI workflow, dashboard shell, AI sidecar, and one E2E path.
- Excluded from this plan: real broker connection, real order placement, paid market data subscriptions, all-market high-frequency scanning, public SaaS billing, mobile app, and quantitative backtesting.

Follow-up plans should be created separately for:

- Real provider integration with OpenBB/SEC EDGAR/Finnhub/Polygon.
- Real LLM provider configuration, streaming, evaluation, and prompt/version governance.
- Broker read-only integration.
- Quantitative strategy lab and backtesting.

## File Structure

Workspace root: `D:\Documents\AI美股`

Create or modify these files:

- `package.json`: root scripts for web, API, tests, and Docker helpers.
- `.env.example`: local configuration contract.
- `docker-compose.yml`: Postgres, Redis, API, and web services for local/inside-LAN use.
- `apps/api/pyproject.toml`: backend dependencies and pytest config.
- `apps/api/app/main.py`: FastAPI app factory and router mounting.
- `apps/api/app/core/config.py`: environment settings.
- `apps/api/app/db/session.py`: SQLModel engine/session helpers.
- `apps/api/app/domain/models.py`: SQLModel tables and domain enums.
- `apps/api/app/security/permissions.py`: role permission checks.
- `apps/api/app/services/audit.py`: audit event writer.
- `apps/api/app/services/portfolio.py`: portfolio exposure and validation logic.
- `apps/api/app/services/imports.py`: CSV import parser with row-level errors.
- `apps/api/app/data/providers/base.py`: provider protocol and shared data shapes.
- `apps/api/app/data/providers/mock.py`: deterministic provider for tests and first UI.
- `apps/api/app/services/alerts.py`: event-driven alert generation.
- `apps/api/app/ai/schemas.py`: structured AI output schemas.
- `apps/api/app/ai/workflow.py`: deterministic LangGraph workflow.
- `apps/api/app/api/routes/*.py`: API endpoints.
- `apps/api/tests/*.py`: backend unit/API tests.
- `apps/web/package.json`: frontend dependencies and scripts.
- `apps/web/src/app/layout.tsx`: root layout.
- `apps/web/src/app/page.tsx`: dashboard page.
- `apps/web/src/app/portfolio/page.tsx`: portfolio page.
- `apps/web/src/app/import/page.tsx`: CSV import page.
- `apps/web/src/app/alerts/page.tsx`: alerts page.
- `apps/web/src/components/app-shell.tsx`: left nav + main + AI sidecar layout.
- `apps/web/src/components/ai-sidecar.tsx`: contextual AI assistant panel.
- `apps/web/src/lib/api.ts`: typed API client.
- `apps/web/src/lib/sample-data.ts`: fallback UI data for offline shell rendering.
- `apps/web/tests/mvp.spec.ts`: Playwright E2E smoke test.

---

### Task 1: Backend API Skeleton

**Files:**
- Create: `apps/api/pyproject.toml`
- Create: `apps/api/app/__init__.py`
- Create: `apps/api/app/main.py`
- Create: `apps/api/app/core/__init__.py`
- Create: `apps/api/app/core/config.py`
- Test: `apps/api/tests/test_health.py`

- [ ] **Step 1: Write the failing health test**

Create `apps/api/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_health_endpoint_returns_service_status():
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "ai-us-stocks-api"}
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_health.py -v
```

Expected: FAIL because `app.main` does not exist.

- [ ] **Step 3: Add backend project metadata**

Create `apps/api/pyproject.toml`:

```toml
[project]
name = "ai-us-stocks-api"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
  "fastapi>=0.115.0",
  "uvicorn[standard]>=0.30.0",
  "pydantic-settings>=2.4.0",
  "sqlmodel>=0.0.22",
  "psycopg[binary]>=3.2.0",
  "python-multipart>=0.0.9",
  "openpyxl>=3.1.5",
  "langgraph>=0.2.0",
]

[project.optional-dependencies]
dev = [
  "httpx>=0.27.0",
  "pytest>=8.3.0",
  "pytest-cov>=5.0.0",
]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
pythonpath = ["."]
testpaths = ["tests"]
```

- [ ] **Step 4: Add settings and app factory**

Create `apps/api/app/__init__.py`:

```python
__all__ = ["main"]
```

Create `apps/api/app/core/__init__.py`:

```python
__all__ = ["config"]
```

Create `apps/api/app/core/config.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ai-us-stocks-api"
    database_url: str = "sqlite:///./local.db"
    cors_origin: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="AI_STOCKS_")


def get_settings() -> Settings:
    return Settings()
```

Create `apps/api/app/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
```

- [ ] **Step 5: Run test to verify it passes**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_health.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/pyproject.toml apps/api/app apps/api/tests/test_health.py
git commit -m "feat(api): add FastAPI skeleton"
```

---

### Task 2: Domain Models and Database Session

**Files:**
- Create: `apps/api/app/db/__init__.py`
- Create: `apps/api/app/db/session.py`
- Create: `apps/api/app/domain/__init__.py`
- Create: `apps/api/app/domain/models.py`
- Test: `apps/api/tests/test_domain_models.py`

- [ ] **Step 1: Write failing model tests**

Create `apps/api/tests/test_domain_models.py`:

```python
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import MemberRole, Portfolio, Position, Team, User


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_domain_models.py -v
```

Expected: FAIL because `app.domain.models` does not exist.

- [ ] **Step 3: Add models and database helpers**

Create `apps/api/app/db/__init__.py`:

```python
__all__ = ["session"]
```

Create `apps/api/app/domain/__init__.py`:

```python
__all__ = ["models"]
```

Create `apps/api/app/domain/models.py`:

```python
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MemberRole(str, Enum):
    owner = "owner"
    analyst = "analyst"
    viewer = "viewer"


class AlertStatus(str, Enum):
    open = "open"
    assigned = "assigned"
    closed = "closed"


class Team(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    created_at: datetime = Field(default_factory=utc_now)

    portfolios: list["Portfolio"] = Relationship(back_populates="team")


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True)
    display_name: str
    created_at: datetime = Field(default_factory=utc_now)


class TeamMembership(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    role: MemberRole
    created_at: datetime = Field(default_factory=utc_now)


class Security(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    ticker: str = Field(index=True)
    name: str
    exchange: str = "NASDAQ"
    cik: Optional[str] = Field(default=None, index=True)
    currency: str = "USD"
    updated_at: datetime = Field(default_factory=utc_now)


class WatchlistItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: str = Field(index=True)
    thesis: str = ""
    created_at: datetime = Field(default_factory=utc_now)


class Portfolio(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: Optional[UUID] = Field(default=None, foreign_key="team.id", index=True)
    name: str
    base_currency: str = "USD"
    created_at: datetime = Field(default_factory=utc_now)

    team: Optional[Team] = Relationship(back_populates="portfolios")
    positions: list["Position"] = Relationship(back_populates="portfolio")


class Position(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    portfolio_id: Optional[UUID] = Field(default=None, foreign_key="portfolio.id", index=True)
    ticker: str = Field(index=True)
    quantity: float
    average_cost: float
    currency: str = "USD"
    updated_at: datetime = Field(default_factory=utc_now)

    portfolio: Optional[Portfolio] = Relationship(back_populates="positions")


class Alert(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: str = Field(index=True)
    title: str
    reason: str
    status: AlertStatus = Field(default=AlertStatus.open, index=True)
    source: str
    created_at: datetime = Field(default_factory=utc_now)


class Note(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    ticker: Optional[str] = Field(default=None, index=True)
    title: str
    body: str
    created_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    created_at: datetime = Field(default_factory=utc_now)


class AiRun(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: UUID = Field(foreign_key="team.id", index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    prompt: str
    output_json: str
    evidence_json: str
    created_at: datetime = Field(default_factory=utc_now)


class AuditLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    team_id: Optional[UUID] = Field(default=None, foreign_key="team.id", index=True)
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    action: str
    entity_type: str
    entity_id: Optional[str] = None
    metadata_json: str = "{}"
    created_at: datetime = Field(default_factory=utc_now)
```

Create `apps/api/app/db/session.py`:

```python
from collections.abc import Generator

from sqlmodel import Session, SQLModel, create_engine

from app.core.config import get_settings


def get_engine():
    settings = get_settings()
    connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
    return create_engine(settings.database_url, connect_args=connect_args)


engine = get_engine()


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
```

- [ ] **Step 4: Run model tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_domain_models.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/db apps/api/app/domain apps/api/tests/test_domain_models.py
git commit -m "feat(api): add domain models"
```

---

### Task 3: Permissions and Audit Logs

**Files:**
- Create: `apps/api/app/security/__init__.py`
- Create: `apps/api/app/security/permissions.py`
- Create: `apps/api/app/services/__init__.py`
- Create: `apps/api/app/services/audit.py`
- Test: `apps/api/tests/test_permissions_audit.py`

- [ ] **Step 1: Write failing permission and audit tests**

Create `apps/api/tests/test_permissions_audit.py`:

```python
from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import AuditLog, MemberRole, Team, User
from app.security.permissions import Permission, can
from app.services.audit import record_audit


def test_role_permission_matrix():
    assert can(MemberRole.owner, Permission.manage_settings)
    assert can(MemberRole.analyst, Permission.create_ai_draft)
    assert can(MemberRole.analyst, Permission.import_positions)
    assert can(MemberRole.viewer, Permission.view_dashboard)
    assert not can(MemberRole.viewer, Permission.import_positions)
    assert not can(MemberRole.analyst, Permission.manage_settings)


def test_record_audit_persists_action():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        team = Team(name="Core")
        user = User(email="owner@example.com", display_name="Owner")
        session.add(team)
        session.add(user)
        session.commit()
        session.refresh(team)
        session.refresh(user)

        record_audit(
            session=session,
            team_id=team.id,
            user_id=user.id,
            action="portfolio.imported",
            entity_type="imported_file",
            entity_id="sample.csv",
            metadata={"rows": 2},
        )

        stored = session.exec(select(AuditLog)).one()
        assert stored.action == "portfolio.imported"
        assert '"rows": 2' in stored.metadata_json
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_permissions_audit.py -v
```

Expected: FAIL because `app.security.permissions` and `app.services.audit` do not exist.

- [ ] **Step 3: Add permissions and audit service**

Create `apps/api/app/security/__init__.py`:

```python
__all__ = ["permissions"]
```

Create `apps/api/app/services/__init__.py`:

```python
__all__ = ["audit", "portfolio", "imports", "alerts"]
```

Create `apps/api/app/security/permissions.py`:

```python
from enum import Enum

from app.domain.models import MemberRole


class Permission(str, Enum):
    view_dashboard = "view_dashboard"
    manage_settings = "manage_settings"
    import_positions = "import_positions"
    create_ai_draft = "create_ai_draft"
    manage_alerts = "manage_alerts"


ROLE_PERMISSIONS: dict[MemberRole, set[Permission]] = {
    MemberRole.owner: {
        Permission.view_dashboard,
        Permission.manage_settings,
        Permission.import_positions,
        Permission.create_ai_draft,
        Permission.manage_alerts,
    },
    MemberRole.analyst: {
        Permission.view_dashboard,
        Permission.import_positions,
        Permission.create_ai_draft,
        Permission.manage_alerts,
    },
    MemberRole.viewer: {
        Permission.view_dashboard,
    },
}


def can(role: MemberRole, permission: Permission) -> bool:
    return permission in ROLE_PERMISSIONS[role]
```

Create `apps/api/app/services/audit.py`:

```python
import json
from typing import Any
from uuid import UUID

from sqlmodel import Session

from app.domain.models import AuditLog


def record_audit(
    *,
    session: Session,
    team_id: UUID | None,
    user_id: UUID | None,
    action: str,
    entity_type: str,
    entity_id: str | None,
    metadata: dict[str, Any],
) -> AuditLog:
    entry = AuditLog(
        team_id=team_id,
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        metadata_json=json.dumps(metadata, ensure_ascii=False, sort_keys=True),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_permissions_audit.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/security apps/api/app/services apps/api/tests/test_permissions_audit.py
git commit -m "feat(api): add permissions and audit logs"
```

---

### Task 4: Portfolio Exposure Logic

**Files:**
- Create: `apps/api/app/services/portfolio.py`
- Test: `apps/api/tests/test_portfolio_service.py`

- [ ] **Step 1: Write failing portfolio service tests**

Create `apps/api/tests/test_portfolio_service.py`:

```python
from app.services.portfolio import PositionInput, calculate_exposure


def test_calculate_exposure_returns_weights_and_total_market_value():
    positions = [
        PositionInput(ticker="AAPL", quantity=10, price=200),
        PositionInput(ticker="MSFT", quantity=5, price=400),
    ]

    result = calculate_exposure(positions)

    assert result.total_market_value == 4000
    assert result.items[0].ticker == "AAPL"
    assert result.items[0].market_value == 2000
    assert result.items[0].weight == 0.5
    assert result.items[1].ticker == "MSFT"
    assert result.items[1].weight == 0.5


def test_calculate_exposure_rejects_negative_quantity():
    positions = [PositionInput(ticker="AAPL", quantity=-1, price=200)]

    try:
        calculate_exposure(positions)
    except ValueError as exc:
        assert "quantity must be non-negative" in str(exc)
    else:
        raise AssertionError("negative quantity should fail")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_portfolio_service.py -v
```

Expected: FAIL because `app.services.portfolio` does not exist.

- [ ] **Step 3: Implement portfolio service**

Create `apps/api/app/services/portfolio.py`:

```python
from pydantic import BaseModel, Field


class PositionInput(BaseModel):
    ticker: str = Field(min_length=1)
    quantity: float
    price: float


class ExposureItem(BaseModel):
    ticker: str
    market_value: float
    weight: float


class ExposureResult(BaseModel):
    total_market_value: float
    items: list[ExposureItem]


def calculate_exposure(positions: list[PositionInput]) -> ExposureResult:
    for position in positions:
        if position.quantity < 0:
            raise ValueError(f"{position.ticker} quantity must be non-negative")
        if position.price < 0:
            raise ValueError(f"{position.ticker} price must be non-negative")

    market_values = [
        ExposureItem(
            ticker=position.ticker.upper(),
            market_value=position.quantity * position.price,
            weight=0,
        )
        for position in positions
    ]
    total = sum(item.market_value for item in market_values)
    if total == 0:
        return ExposureResult(total_market_value=0, items=market_values)

    weighted = [
        ExposureItem(
            ticker=item.ticker,
            market_value=item.market_value,
            weight=round(item.market_value / total, 6),
        )
        for item in market_values
    ]
    return ExposureResult(total_market_value=total, items=weighted)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_portfolio_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/portfolio.py apps/api/tests/test_portfolio_service.py
git commit -m "feat(api): add portfolio exposure calculation"
```

---

### Task 5: CSV Import Parser With Row Errors

**Files:**
- Create: `apps/api/app/services/imports.py`
- Test: `apps/api/tests/test_imports_service.py`

- [ ] **Step 1: Write failing import parser tests**

Create `apps/api/tests/test_imports_service.py`:

```python
from app.services.imports import parse_positions_csv


def test_parse_positions_csv_accepts_valid_rows():
    content = "ticker,quantity,average_cost,currency\nAAPL,10,150,USD\nMSFT,5,300,USD\n"

    result = parse_positions_csv(content)

    assert len(result.positions) == 2
    assert result.positions[0].ticker == "AAPL"
    assert result.positions[0].quantity == 10
    assert result.errors == []


def test_parse_positions_csv_reports_row_level_errors():
    content = "ticker,quantity,average_cost,currency\n,10,150,USD\nTSLA,nope,200,USD\n"

    result = parse_positions_csv(content)

    assert result.positions == []
    assert result.errors == [
        {"row": 2, "field": "ticker", "message": "ticker is required"},
        {"row": 3, "field": "quantity", "message": "quantity must be a number"},
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_imports_service.py -v
```

Expected: FAIL because `app.services.imports` does not exist.

- [ ] **Step 3: Implement CSV parser**

Create `apps/api/app/services/imports.py`:

```python
import csv
from io import StringIO
from typing import Any

from pydantic import BaseModel


class ImportedPosition(BaseModel):
    ticker: str
    quantity: float
    average_cost: float
    currency: str = "USD"


class ImportResult(BaseModel):
    positions: list[ImportedPosition]
    errors: list[dict[str, Any]]


def _parse_float(value: str, row_number: int, field: str, errors: list[dict[str, Any]]) -> float | None:
    try:
        return float(value)
    except ValueError:
        errors.append({"row": row_number, "field": field, "message": f"{field} must be a number"})
        return None


def parse_positions_csv(content: str) -> ImportResult:
    reader = csv.DictReader(StringIO(content))
    positions: list[ImportedPosition] = []
    errors: list[dict[str, Any]] = []

    for index, row in enumerate(reader, start=2):
        ticker = (row.get("ticker") or "").strip().upper()
        quantity_raw = (row.get("quantity") or "").strip()
        average_cost_raw = (row.get("average_cost") or "").strip()
        currency = (row.get("currency") or "USD").strip().upper()

        row_errors_before = len(errors)
        if not ticker:
            errors.append({"row": index, "field": "ticker", "message": "ticker is required"})
        quantity = _parse_float(quantity_raw, index, "quantity", errors)
        average_cost = _parse_float(average_cost_raw, index, "average_cost", errors)

        if len(errors) == row_errors_before and quantity is not None and average_cost is not None:
            positions.append(
                ImportedPosition(
                    ticker=ticker,
                    quantity=quantity,
                    average_cost=average_cost,
                    currency=currency,
                )
            )

    return ImportResult(positions=positions, errors=errors)
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_imports_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/imports.py apps/api/tests/test_imports_service.py
git commit -m "feat(api): add CSV position import parser"
```

---

### Task 6: Mock Data Provider Adapter

**Files:**
- Create: `apps/api/app/data/__init__.py`
- Create: `apps/api/app/data/providers/__init__.py`
- Create: `apps/api/app/data/providers/base.py`
- Create: `apps/api/app/data/providers/mock.py`
- Test: `apps/api/tests/test_mock_provider.py`

- [ ] **Step 1: Write failing provider tests**

Create `apps/api/tests/test_mock_provider.py`:

```python
from app.data.providers.mock import MockMarketDataProvider


def test_mock_provider_returns_quote_with_source_metadata():
    provider = MockMarketDataProvider()

    quote = provider.get_quote("aapl")

    assert quote.ticker == "AAPL"
    assert quote.price > 0
    assert quote.source == "mock"
    assert quote.updated_at.endswith("Z")


def test_mock_provider_returns_evidence_items():
    provider = MockMarketDataProvider()

    evidence = provider.get_research_evidence("MSFT")

    assert len(evidence) >= 2
    assert evidence[0].ticker == "MSFT"
    assert evidence[0].source in {"mock_filing", "mock_news", "mock_quote"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_mock_provider.py -v
```

Expected: FAIL because provider modules do not exist.

- [ ] **Step 3: Implement provider protocol and mock provider**

Create `apps/api/app/data/__init__.py`:

```python
__all__ = ["providers"]
```

Create `apps/api/app/data/providers/__init__.py`:

```python
__all__ = ["base", "mock"]
```

Create `apps/api/app/data/providers/base.py`:

```python
from typing import Protocol

from pydantic import BaseModel


class Quote(BaseModel):
    ticker: str
    price: float
    currency: str
    source: str
    updated_at: str


class EvidenceItem(BaseModel):
    ticker: str
    title: str
    summary: str
    source: str
    source_url: str
    observed_at: str


class MarketDataProvider(Protocol):
    def get_quote(self, ticker: str) -> Quote:
        raise NotImplementedError

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        raise NotImplementedError
```

Create `apps/api/app/data/providers/mock.py`:

```python
from app.data.providers.base import EvidenceItem, Quote


class MockMarketDataProvider:
    def get_quote(self, ticker: str) -> Quote:
        normalized = ticker.upper()
        prices = {"AAPL": 210.12, "MSFT": 430.55, "NVDA": 125.75}
        return Quote(
            ticker=normalized,
            price=prices.get(normalized, 100.0),
            currency="USD",
            source="mock",
            updated_at="2026-06-12T13:30:00Z",
        )

    def get_research_evidence(self, ticker: str) -> list[EvidenceItem]:
        normalized = ticker.upper()
        return [
            EvidenceItem(
                ticker=normalized,
                title=f"{normalized} latest filing snapshot",
                summary="Revenue growth remains positive while operating expense growth requires monitoring.",
                source="mock_filing",
                source_url=f"https://example.local/filings/{normalized}",
                observed_at="2026-06-12T13:00:00Z",
            ),
            EvidenceItem(
                ticker=normalized,
                title=f"{normalized} market news",
                summary="Recent market coverage highlights demand resilience and valuation sensitivity.",
                source="mock_news",
                source_url=f"https://example.local/news/{normalized}",
                observed_at="2026-06-12T13:10:00Z",
            ),
        ]
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_mock_provider.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/data apps/api/tests/test_mock_provider.py
git commit -m "feat(api): add mock market data provider"
```

---

### Task 7: Alert Generation Service

**Files:**
- Create: `apps/api/app/services/alerts.py`
- Test: `apps/api/tests/test_alerts_service.py`

- [ ] **Step 1: Write failing alert tests**

Create `apps/api/tests/test_alerts_service.py`:

```python
from app.services.alerts import AlertCandidate, generate_event_alerts


def test_generate_event_alerts_matches_portfolio_tickers():
    candidates = [
        AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="sec_edgar"),
        AlertCandidate(ticker="TSLA", title="TSLA news", reason="News event", source="mock_news"),
    ]

    alerts = generate_event_alerts(portfolio_tickers=["aapl", "msft"], candidates=candidates)

    assert len(alerts) == 1
    assert alerts[0].ticker == "AAPL"
    assert alerts[0].title == "AAPL 10-Q filed"


def test_generate_event_alerts_deduplicates_by_ticker_title_source():
    candidates = [
        AlertCandidate(ticker="MSFT", title="Earnings date changed", reason="Calendar update", source="calendar"),
        AlertCandidate(ticker="MSFT", title="Earnings date changed", reason="Calendar update", source="calendar"),
    ]

    alerts = generate_event_alerts(portfolio_tickers=["MSFT"], candidates=candidates)

    assert len(alerts) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_alerts_service.py -v
```

Expected: FAIL because `app.services.alerts` does not exist.

- [ ] **Step 3: Implement alert service**

Create `apps/api/app/services/alerts.py`:

```python
from pydantic import BaseModel, Field


class AlertCandidate(BaseModel):
    ticker: str = Field(min_length=1)
    title: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source: str = Field(min_length=1)


class GeneratedAlert(BaseModel):
    ticker: str
    title: str
    reason: str
    source: str


def generate_event_alerts(
    *,
    portfolio_tickers: list[str],
    candidates: list[AlertCandidate],
) -> list[GeneratedAlert]:
    tracked = {ticker.upper() for ticker in portfolio_tickers}
    seen: set[tuple[str, str, str]] = set()
    alerts: list[GeneratedAlert] = []

    for candidate in candidates:
        ticker = candidate.ticker.upper()
        key = (ticker, candidate.title, candidate.source)
        if ticker not in tracked or key in seen:
            continue
        seen.add(key)
        alerts.append(
            GeneratedAlert(
                ticker=ticker,
                title=candidate.title,
                reason=candidate.reason,
                source=candidate.source,
            )
        )

    return alerts
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_alerts_service.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/services/alerts.py apps/api/tests/test_alerts_service.py
git commit -m "feat(api): add event alert generation"
```

---

### Task 8: Deterministic LangGraph AI Workflow

**Files:**
- Create: `apps/api/app/ai/__init__.py`
- Create: `apps/api/app/ai/schemas.py`
- Create: `apps/api/app/ai/workflow.py`
- Test: `apps/api/tests/test_ai_workflow.py`

- [ ] **Step 1: Write failing AI workflow tests**

Create `apps/api/tests/test_ai_workflow.py`:

```python
from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow


def test_research_workflow_returns_structured_answer_with_evidence():
    request = ResearchRequest(
        ticker="AAPL",
        question="What should we watch?",
        evidence=[
            EvidenceItemInput(
                title="AAPL filing",
                summary="Revenue grew but margin narrowed.",
                source="mock_filing",
                source_url="https://example.local/aapl",
            )
        ],
    )

    result = run_research_workflow(request)

    assert result.ticker == "AAPL"
    assert result.status == "complete"
    assert result.summary
    assert result.evidence_count == 1
    assert result.trade_plan_draft.entry_condition
    assert result.trade_plan_draft.requires_human_review is True


def test_research_workflow_refuses_when_evidence_is_missing():
    request = ResearchRequest(ticker="AAPL", question="Should we buy?", evidence=[])

    result = run_research_workflow(request)

    assert result.status == "insufficient_evidence"
    assert result.summary == "Insufficient evidence to produce a research view."
    assert result.evidence_count == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_ai_workflow.py -v
```

Expected: FAIL because `app.ai.workflow` does not exist.

- [ ] **Step 3: Implement schemas and workflow**

Create `apps/api/app/ai/__init__.py`:

```python
__all__ = ["schemas", "workflow"]
```

Create `apps/api/app/ai/schemas.py`:

```python
from pydantic import BaseModel, Field


class EvidenceItemInput(BaseModel):
    title: str
    summary: str
    source: str
    source_url: str


class ResearchRequest(BaseModel):
    ticker: str = Field(min_length=1)
    question: str = Field(min_length=1)
    evidence: list[EvidenceItemInput]


class TradePlanDraft(BaseModel):
    entry_condition: str
    invalidation_condition: str
    risk_notes: list[str]
    requires_human_review: bool = True


class ResearchResult(BaseModel):
    ticker: str
    status: str
    summary: str
    bull_case: str
    bear_case: str
    watch_items: list[str]
    evidence_count: int
    trade_plan_draft: TradePlanDraft
```

Create `apps/api/app/ai/workflow.py`:

```python
from typing import TypedDict

from langgraph.graph import END, StateGraph

from app.ai.schemas import ResearchRequest, ResearchResult, TradePlanDraft


class ResearchState(TypedDict):
    request: ResearchRequest
    result: ResearchResult | None


def analyze(state: ResearchState) -> ResearchState:
    request = state["request"]
    ticker = request.ticker.upper()
    if not request.evidence:
        state["result"] = ResearchResult(
            ticker=ticker,
            status="insufficient_evidence",
            summary="Insufficient evidence to produce a research view.",
            bull_case="No bull case generated because evidence is missing.",
            bear_case="No bear case generated because evidence is missing.",
            watch_items=["Add filings, market data, or team notes before relying on AI output."],
            evidence_count=0,
            trade_plan_draft=TradePlanDraft(
                entry_condition="No entry condition generated.",
                invalidation_condition="No invalidation condition generated.",
                risk_notes=["Evidence package is empty."],
            ),
        )
        return state

    combined = " ".join(item.summary for item in request.evidence)
    state["result"] = ResearchResult(
        ticker=ticker,
        status="complete",
        summary=f"{ticker}: {combined}",
        bull_case="Positive evidence exists, but the team must validate durability and valuation.",
        bear_case="Risk remains if fundamentals weaken or valuation compresses.",
        watch_items=[
            "Confirm the latest filing trend.",
            "Compare news impact with portfolio exposure.",
            "Review whether the thesis changed.",
        ],
        evidence_count=len(request.evidence),
        trade_plan_draft=TradePlanDraft(
            entry_condition="Only consider action after a human reviews the evidence and confirms the thesis.",
            invalidation_condition="Invalidate the draft if new filings or news contradict the evidence package.",
            risk_notes=["This is a draft, not an executable order.", "Human approval is required."],
        ),
    )
    return state


def build_graph():
    graph = StateGraph(ResearchState)
    graph.add_node("analyze", analyze)
    graph.set_entry_point("analyze")
    graph.add_edge("analyze", END)
    return graph.compile()


def run_research_workflow(request: ResearchRequest) -> ResearchResult:
    graph = build_graph()
    final_state = graph.invoke({"request": request, "result": None})
    result = final_state["result"]
    if result is None:
        raise RuntimeError("research workflow did not produce a result")
    return result
```

- [ ] **Step 4: Run tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_ai_workflow.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/api/app/ai apps/api/tests/test_ai_workflow.py
git commit -m "feat(api): add deterministic research workflow"
```

---

### Task 9: API Routes for MVP Data

**Files:**
- Create: `apps/api/app/api/__init__.py`
- Create: `apps/api/app/api/routes/__init__.py`
- Create: `apps/api/app/api/routes/mvp.py`
- Modify: `apps/api/app/main.py`
- Test: `apps/api/tests/test_mvp_routes.py`

- [ ] **Step 1: Write failing API route tests**

Create `apps/api/tests/test_mvp_routes.py`:

```python
from fastapi.testclient import TestClient

from app.main import create_app


def test_mvp_dashboard_route_returns_portfolio_alerts_and_ai_prompts():
    client = TestClient(create_app())

    response = client.get("/api/mvp/dashboard")

    assert response.status_code == 200
    payload = response.json()
    assert payload["portfolio"]["name"] == "Main Book"
    assert payload["alerts"][0]["ticker"] == "AAPL"
    assert "Find portfolio risks" in payload["ai_prompts"]


def test_mvp_research_route_returns_structured_ai_result():
    client = TestClient(create_app())

    response = client.post(
        "/api/mvp/research",
        json={"ticker": "AAPL", "question": "What changed?"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["ticker"] == "AAPL"
    assert payload["status"] == "complete"
    assert payload["trade_plan_draft"]["requires_human_review"] is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_mvp_routes.py -v
```

Expected: FAIL because `/api/mvp/dashboard` is not mounted.

- [ ] **Step 3: Add MVP routes**

Create `apps/api/app/api/__init__.py`:

```python
__all__ = ["routes"]
```

Create `apps/api/app/api/routes/__init__.py`:

```python
__all__ = ["mvp"]
```

Create `apps/api/app/api/routes/mvp.py`:

```python
from fastapi import APIRouter
from pydantic import BaseModel

from app.ai.schemas import EvidenceItemInput, ResearchRequest
from app.ai.workflow import run_research_workflow
from app.data.providers.mock import MockMarketDataProvider
from app.services.alerts import AlertCandidate, generate_event_alerts
from app.services.portfolio import PositionInput, calculate_exposure

router = APIRouter(prefix="/api/mvp", tags=["mvp"])


class ResearchBody(BaseModel):
    ticker: str
    question: str


@router.get("/dashboard")
def dashboard() -> dict:
    provider = MockMarketDataProvider()
    positions = [
        PositionInput(ticker="AAPL", quantity=10, price=provider.get_quote("AAPL").price),
        PositionInput(ticker="MSFT", quantity=5, price=provider.get_quote("MSFT").price),
    ]
    exposure = calculate_exposure(positions)
    alerts = generate_event_alerts(
        portfolio_tickers=[item.ticker for item in exposure.items],
        candidates=[
            AlertCandidate(ticker="AAPL", title="AAPL 10-Q filed", reason="SEC filing", source="mock_sec"),
            AlertCandidate(ticker="NVDA", title="NVDA news", reason="News event", source="mock_news"),
        ],
    )
    return {
        "portfolio": {
            "name": "Main Book",
            "total_market_value": exposure.total_market_value,
            "positions": [item.model_dump() for item in exposure.items],
        },
        "alerts": [alert.model_dump() for alert in alerts],
        "ai_prompts": [
            "Explain current page",
            "Find portfolio risks",
            "Generate bull/base/bear view",
            "Draft a trade plan",
        ],
    }


@router.post("/research")
def research(body: ResearchBody) -> dict:
    provider = MockMarketDataProvider()
    evidence = [
        EvidenceItemInput(
            title=item.title,
            summary=item.summary,
            source=item.source,
            source_url=item.source_url,
        )
        for item in provider.get_research_evidence(body.ticker)
    ]
    result = run_research_workflow(
        ResearchRequest(ticker=body.ticker, question=body.question, evidence=evidence)
    )
    return result.model_dump()
```

Modify `apps/api/app/main.py` to mount the router:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.mvp import router as mvp_router
from app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.cors_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(mvp_router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": settings.app_name}

    return app


app = create_app()
```

- [ ] **Step 4: Run route tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest tests/test_mvp_routes.py -v
```

Expected: PASS.

- [ ] **Step 5: Run all backend tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add apps/api/app/api apps/api/app/main.py apps/api/tests/test_mvp_routes.py
git commit -m "feat(api): expose MVP dashboard and research routes"
```

---

### Task 10: Root Tooling and Docker Compose

**Files:**
- Create: `package.json`
- Create: `.env.example`
- Create: `docker-compose.yml`

- [ ] **Step 1: Add root scripts**

Create `package.json`:

```json
{
  "name": "ai-us-stocks-tool",
  "private": true,
  "scripts": {
    "api:dev": "cd apps/api && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000",
    "api:test": "cd apps/api && python -m pytest -v",
    "web:dev": "cd apps/web && npm run dev",
    "web:test:e2e": "cd apps/web && npx playwright test",
    "dev": "docker compose up --build"
  }
}
```

- [ ] **Step 2: Add local environment contract**

Create `.env.example`:

```dotenv
AI_STOCKS_DATABASE_URL=postgresql+psycopg://ai_stocks:ai_stocks@postgres:5432/ai_stocks
AI_STOCKS_CORS_ORIGIN=http://localhost:3000
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

- [ ] **Step 3: Add Docker Compose stack**

Create `docker-compose.yml`:

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: ai_stocks
      POSTGRES_PASSWORD: ai_stocks
      POSTGRES_DB: ai_stocks
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6379:6379"

  api:
    image: python:3.12-slim
    working_dir: /workspace/apps/api
    command: sh -c "pip install -e '.[dev]' && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    env_file:
      - .env
    ports:
      - "8000:8000"
    volumes:
      - .:/workspace
    depends_on:
      - postgres
      - redis

  web:
    image: node:22
    working_dir: /workspace/apps/web
    command: sh -c "npm install && npm run dev -- --hostname 0.0.0.0"
    environment:
      NEXT_PUBLIC_API_BASE_URL: http://localhost:8000
    ports:
      - "3000:3000"
    volumes:
      - .:/workspace
    depends_on:
      - api

volumes:
  postgres_data:
```

- [ ] **Step 4: Validate compose syntax**

Run:

```powershell
cd D:\Documents\AI美股
docker compose config
```

Expected: command exits successfully and prints merged Compose config.

- [ ] **Step 5: Commit**

```powershell
git add package.json .env.example docker-compose.yml
git commit -m "chore: add local development stack"
```

---

### Task 11: Frontend App Shell and API Client

**Files:**
- Create: `apps/web/package.json`
- Create: `apps/web/next.config.ts`
- Create: `apps/web/tsconfig.json`
- Create: `apps/web/src/app/layout.tsx`
- Create: `apps/web/src/app/styles.css`
- Create: `apps/web/src/app/page.tsx`
- Create: `apps/web/src/components/app-shell.tsx`
- Create: `apps/web/src/components/ai-sidecar.tsx`
- Create: `apps/web/src/lib/api.ts`
- Create: `apps/web/src/lib/sample-data.ts`

- [ ] **Step 1: Add frontend package files**

Create `apps/web/package.json`:

```json
{
  "name": "ai-us-stocks-web",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "^16.0.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "lucide-react": "^0.468.0"
  },
  "devDependencies": {
    "@types/node": "^22.0.0",
    "@types/react": "^19.0.0",
    "@types/react-dom": "^19.0.0",
    "typescript": "^5.6.0",
    "tailwindcss": "^4.0.0"
  }
}
```

Create `apps/web/next.config.ts`:

```ts
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
};

export default nextConfig;
```

Create `apps/web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "es2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "paths": {
      "@/*": ["./src/*"]
    }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 2: Add API client and sample data**

Create `apps/web/src/lib/sample-data.ts`:

```ts
export const sampleDashboard = {
  portfolio: {
    name: "Main Book",
    total_market_value: 4153.95,
    positions: [
      { ticker: "AAPL", market_value: 2101.2, weight: 0.5058 },
      { ticker: "MSFT", market_value: 2152.75, weight: 0.5182 }
    ]
  },
  alerts: [
    { ticker: "AAPL", title: "AAPL 10-Q filed", reason: "SEC filing", source: "mock_sec" }
  ],
  ai_prompts: [
    "Explain current page",
    "Find portfolio risks",
    "Generate bull/base/bear view",
    "Draft a trade plan"
  ]
};
```

Create `apps/web/src/lib/api.ts`:

```ts
import { sampleDashboard } from "./sample-data";

export type DashboardPayload = typeof sampleDashboard;

const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export async function getDashboard(): Promise<DashboardPayload> {
  try {
    const response = await fetch(`${apiBaseUrl}/api/mvp/dashboard`, { cache: "no-store" });
    if (!response.ok) {
      return sampleDashboard;
    }
    return (await response.json()) as DashboardPayload;
  } catch {
    return sampleDashboard;
  }
}
```

- [ ] **Step 3: Add root layout**

Create `apps/web/src/app/layout.tsx`:

```tsx
import type { Metadata } from "next";
import "./styles.css";

export const metadata: Metadata = {
  title: "AI US Stocks",
  description: "Internal AI research and portfolio monitoring workspace"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="zh-CN">
      <body>{children}</body>
    </html>
  );
}
```

Create `apps/web/src/app/styles.css`:

```css
:root {
  color-scheme: light;
  font-family: Arial, Helvetica, sans-serif;
  background: #f6f7f9;
  color: #111827;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
}

a {
  color: inherit;
  text-decoration: none;
}

button {
  font: inherit;
}
```

- [ ] **Step 4: Add dashboard shell and sidecar**

Create `apps/web/src/components/ai-sidecar.tsx`:

```tsx
export function AiSidecar({ prompts }: { prompts: string[] }) {
  return (
    <aside style={{ width: 320, background: "#111827", color: "white", padding: 16 }}>
      <h2 style={{ margin: "0 0 12px", fontSize: 18 }}>AI 助手</h2>
      <div style={{ display: "grid", gap: 8 }}>
        {prompts.map((prompt) => (
          <button
            key={prompt}
            style={{
              border: "1px solid #374151",
              background: "#1f2937",
              color: "white",
              borderRadius: 6,
              padding: "10px 12px",
              textAlign: "left"
            }}
          >
            {prompt}
          </button>
        ))}
      </div>
    </aside>
  );
}
```

Create `apps/web/src/components/app-shell.tsx`:

```tsx
import { AiSidecar } from "./ai-sidecar";

const navItems = ["总览", "自选股", "组合", "预警", "研究笔记", "数据导入", "设置"];

export function AppShell({
  children,
  prompts
}: {
  children: React.ReactNode;
  prompts: string[];
}) {
  return (
    <main style={{ minHeight: "100vh", display: "grid", gridTemplateColumns: "220px 1fr 320px" }}>
      <nav style={{ borderRight: "1px solid #e5e7eb", background: "white", padding: 16 }}>
        <h1 style={{ margin: "0 0 18px", fontSize: 20 }}>AI 美股</h1>
        <div style={{ display: "grid", gap: 6 }}>
          {navItems.map((item) => (
            <div key={item} style={{ borderRadius: 6, padding: "9px 10px", background: item === "总览" ? "#111827" : "transparent", color: item === "总览" ? "white" : "#374151" }}>
              {item}
            </div>
          ))}
        </div>
      </nav>
      <section style={{ padding: 20 }}>{children}</section>
      <AiSidecar prompts={prompts} />
    </main>
  );
}
```

- [ ] **Step 5: Add dashboard page**

Create `apps/web/src/app/page.tsx`:

```tsx
import { AppShell } from "@/components/app-shell";
import { getDashboard } from "@/lib/api";

export default async function DashboardPage() {
  const dashboard = await getDashboard();

  return (
    <AppShell prompts={dashboard.ai_prompts}>
      <div style={{ display: "grid", gap: 16 }}>
        <header>
          <p style={{ margin: 0, color: "#667085" }}>内部投研与组合监控</p>
          <h2 style={{ margin: "6px 0 0", fontSize: 28 }}>{dashboard.portfolio.name}</h2>
        </header>
        <section style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 12 }}>
          <div style={{ border: "1px solid #e5e7eb", background: "white", borderRadius: 8, padding: 14 }}>
            <div style={{ color: "#667085" }}>组合市值</div>
            <strong>${dashboard.portfolio.total_market_value.toFixed(2)}</strong>
          </div>
          <div style={{ border: "1px solid #e5e7eb", background: "white", borderRadius: 8, padding: 14 }}>
            <div style={{ color: "#667085" }}>持仓数量</div>
            <strong>{dashboard.portfolio.positions.length}</strong>
          </div>
          <div style={{ border: "1px solid #e5e7eb", background: "white", borderRadius: 8, padding: 14 }}>
            <div style={{ color: "#667085" }}>待处理预警</div>
            <strong>{dashboard.alerts.length}</strong>
          </div>
        </section>
        <section style={{ border: "1px solid #e5e7eb", background: "white", borderRadius: 8, padding: 14 }}>
          <h3 style={{ marginTop: 0 }}>组合暴露</h3>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr>
                <th align="left">Ticker</th>
                <th align="right">Market Value</th>
                <th align="right">Weight</th>
              </tr>
            </thead>
            <tbody>
              {dashboard.portfolio.positions.map((position) => (
                <tr key={position.ticker}>
                  <td>{position.ticker}</td>
                  <td align="right">${position.market_value.toFixed(2)}</td>
                  <td align="right">{(position.weight * 100).toFixed(2)}%</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      </div>
    </AppShell>
  );
}
```

- [ ] **Step 6: Run frontend build**

Run:

```powershell
cd D:\Documents\AI美股\apps\web
npm install
npm run build
```

Expected: build exits successfully.

- [ ] **Step 7: Commit**

```powershell
git add apps/web
git commit -m "feat(web): add dashboard shell and AI sidecar"
```

---

### Task 12: MVP E2E Smoke Test

**Files:**
- Create: `apps/web/playwright.config.ts`
- Create: `apps/web/tests/mvp.spec.ts`

- [ ] **Step 1: Add Playwright config**

Create `apps/web/playwright.config.ts`:

```ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./tests",
  webServer: {
    command: "npm run dev",
    url: "http://127.0.0.1:3000",
    reuseExistingServer: true,
    timeout: 120_000
  },
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry"
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] }
    }
  ]
});
```

- [ ] **Step 2: Add E2E smoke test**

Create `apps/web/tests/mvp.spec.ts`:

```ts
import { expect, test } from "@playwright/test";

test("dashboard renders portfolio, alerts, and AI sidecar", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "Main Book" })).toBeVisible();
  await expect(page.getByText("组合市值")).toBeVisible();
  await expect(page.getByText("AAPL")).toBeVisible();
  await expect(page.getByRole("heading", { name: "AI 助手" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Find portfolio risks" })).toBeVisible();
});
```

- [ ] **Step 3: Install Playwright**

Run:

```powershell
cd D:\Documents\AI美股\apps\web
npm install -D @playwright/test
npx playwright install chromium
```

Expected: dependencies and Chromium install successfully.

- [ ] **Step 4: Run E2E test**

Run:

```powershell
cd D:\Documents\AI美股\apps\web
npx playwright test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add apps/web/playwright.config.ts apps/web/tests/mvp.spec.ts apps/web/package.json apps/web/package-lock.json
git commit -m "test(web): add MVP dashboard smoke test"
```

---

### Task 13: Final Verification for This Plan

**Files:**
- Modify only if verification exposes failures in files created by earlier tasks.

- [ ] **Step 1: Run backend tests**

Run:

```powershell
cd D:\Documents\AI美股\apps\api
python -m pytest -v
```

Expected: all backend tests PASS.

- [ ] **Step 2: Run frontend build**

Run:

```powershell
cd D:\Documents\AI美股\apps\web
npm run build
```

Expected: build exits successfully.

- [ ] **Step 3: Run E2E test**

Run:

```powershell
cd D:\Documents\AI美股\apps\web
npx playwright test
```

Expected: all Playwright tests PASS.

- [ ] **Step 4: Validate Docker Compose**

Run:

```powershell
cd D:\Documents\AI美股
docker compose config
```

Expected: command exits successfully and prints merged config.

- [ ] **Step 5: Commit verification fixes if any were needed**

If files changed during verification, run:

```powershell
git add apps package.json docker-compose.yml .env.example
git commit -m "fix: stabilize MVP foundation verification"
```

If no files changed, run:

```powershell
git status --short
```

Expected: no unstaged or staged changes.

---

## Source References

- Next.js App Router project structure: https://nextjs.org/docs/app/getting-started/project-structure
- FastAPI TestClient: https://fastapi.tiangolo.com/reference/testclient/
- FastAPI testing guide: https://fastapi.tiangolo.com/tutorial/testing/
- LangGraph human-in-the-loop: https://docs.langchain.com/oss/python/langchain/human-in-the-loop
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- OpenBB provider extensions: https://docs.openbb.co/odp/python/extensions/providers
