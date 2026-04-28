"""
路由模块初始化
"""
from .auth import router as auth_router
from .nodes import router as nodes_router
from .users import router as users_router
from .routes import router as routes_router
from .acl import router as acl_router
from .preauthkeys import router as preauthkeys_router
from .settings import router as settings_router
from .logs import router as logs_router
from .hs_users import router as hs_users_router

__all__ = [
    "auth_router",
    "nodes_router",
    "users_router",
    "routes_router",
    "acl_router",
    "preauthkeys_router",
    "settings_router",
    "logs_router",
    "hs_users_router",
]
