from sqlmodel import Session, SQLModel, create_engine, select

from app.domain.models import AuditLog, MemberRole, Team, User
from app.security.permissions import Permission, can
from app.services.audit import record_audit


def test_services_import_star_exports_existing_modules():
    namespace: dict[str, object] = {}

    exec("from app.services import *", namespace)

    assert "audit" in namespace


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
            metadata={"source": "导入", "rows": 2},
        )

        stored = session.exec(select(AuditLog)).one()
        assert stored.team_id == team.id
        assert stored.user_id == user.id
        assert stored.action == "portfolio.imported"
        assert stored.entity_type == "imported_file"
        assert stored.entity_id == "sample.csv"
        assert stored.metadata_json == '{"rows": 2, "source": "导入"}'
