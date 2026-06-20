# Headscale Admin - FastAPI Backend
# 纯 JSON API 后端服务，前后端分离模式

import os
import sys

# 添加 api 目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import (
    auth_router,
    machines_router,
    accounts_router,
    routes_router,
    acl_router,
    preauthkeys_router,
    settings_router,
    logs_router,
    groups_router,
    traffic_router,
    client_policies_router,
    security_router,
    client_reports_router,
)

# ─── 配置 ─────────────────────────────────────────────
from routers.dependencies import ensure_observability_schema, load_config
load_config()
ensure_observability_schema()

# ─── FastAPI 应用 ─────────────────────────────────────
app = FastAPI(
    title='Headscale Admin API',
    version='4.0.0',
    docs_url='/api/docs',
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

# ─── 注册路由 ─────────────────────────────────────────
app.include_router(auth_router)
app.include_router(machines_router)
app.include_router(accounts_router)
app.include_router(routes_router)
app.include_router(acl_router)
app.include_router(preauthkeys_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(groups_router)
app.include_router(traffic_router)
app.include_router(client_policies_router)
app.include_router(security_router)
app.include_router(client_reports_router)

# ─── 健康检查 ─────────────────────────────────────────
@app.get('/api/health')
def health_check():
    """API 健康检查"""
    return {'code': 0, 'msg': 'ok'}

# ─── 启动入口 ─────────────────────────────────────────
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='0.0.0.0', port=5175, workers=2, log_level='info')
