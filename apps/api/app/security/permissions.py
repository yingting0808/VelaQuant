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
