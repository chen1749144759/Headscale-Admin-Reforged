"""
路由模块初始化
"""
from .auth import router as auth_router
from .machines import router as machines_router
from .accounts import router as accounts_router
from .routes import router as routes_router
from .acl import router as acl_router
from .preauthkeys import router as preauthkeys_router
from .settings import router as settings_router
from .logs import router as logs_router
from .groups import router as groups_router
from .traffic import router as traffic_router
from .client_policies import router as client_policies_router
from .security import router as security_router
from .client_reports import router as client_reports_router

__all__ = [
    "auth_router",
    "machines_router",
    "accounts_router",
    "routes_router",
    "acl_router",
    "preauthkeys_router",
    "settings_router",
    "logs_router",
    "groups_router",
    "traffic_router",
    "client_policies_router",
    "security_router",
    "client_reports_router",
]
