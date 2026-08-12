# Headscale Admin - FastAPI Backend
# 纯 JSON API 后端服务，前后端分离模式

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    auth_router,
    machines_router,
    accounts_router,
    routes_router,
    acl_router,
    settings_router,
    logs_router,
    groups_router,
    traffic_router,
    client_policies_router,
    security_router,
    client_releases_router,
)

# ─── 配置 ─────────────────────────────────────────────
from api.routers.dependencies import (
    SESSION_COOKIE_NAME,
    TRUSTED_ORIGINS,
    get_db_conn,
    load_config,
)
from api.routers.headscale_client import close_client
from api.routers.traffic import run_scheduled_traffic_maintenance
from api.routers.utils import check_headscale_health
load_config()

logger = logging.getLogger(__name__)


async def _traffic_maintenance_loop():
    while True:
        try:
            await asyncio.to_thread(run_scheduled_traffic_maintenance)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("scheduled traffic maintenance failed")
        await asyncio.sleep(3600)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    maintenance_task = asyncio.create_task(_traffic_maintenance_loop())
    try:
        yield
    finally:
        maintenance_task.cancel()
        try:
            await maintenance_task
        except asyncio.CancelledError:
            pass
        close_client()

# ─── FastAPI 应用 ─────────────────────────────────────
api_docs_enabled = os.environ.get('ENABLE_API_DOCS', 'false').strip().lower() in ('1', 'true', 'yes', 'on')

app = FastAPI(
    title='ScaleForge API',
    version='4.0.0',
    docs_url='/api/docs' if api_docs_enabled else None,
    openapi_url='/api/openapi.json' if api_docs_enabled else None,
    redoc_url=None,
    lifespan=lifespan,
)

if TRUSTED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(TRUSTED_ORIGINS),
        allow_credentials=True,
        allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
        allow_headers=['Content-Type', 'Accept'],
    )


def _csrf_origin_allowed(request: Request) -> bool:
    origin = request.headers.get('origin', '').strip()
    if not origin:
        return False
    if origin in TRUSTED_ORIGINS:
        return True
    parsed = urlsplit(origin)
    return parsed.scheme in ('http', 'https') and parsed.netloc.lower() == request.headers.get('host', '').lower()


@app.middleware('http')
async def api_security_headers(request: Request, call_next):
    if (
        request.method in {'POST', 'PUT', 'PATCH', 'DELETE'}
        and request.url.path.startswith('/api/')
        and not _csrf_origin_allowed(request)
    ):
        return JSONResponse(
            status_code=403,
            content={'detail': {'code': 'csrf_rejected', 'message': '请求来源校验失败'}},
        )
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    if request.url.scheme == 'https':
        response.headers['Strict-Transport-Security'] = 'max-age=15552000; includeSubDomains'
    if request.url.path.startswith('/api/auth/'):
        response.headers['Cache-Control'] = 'no-store'
    return response

# ─── 注册路由 ─────────────────────────────────────────
app.include_router(auth_router)
app.include_router(machines_router)
app.include_router(accounts_router)
app.include_router(routes_router)
app.include_router(acl_router)
app.include_router(settings_router)
app.include_router(logs_router)
app.include_router(groups_router)
app.include_router(traffic_router)
app.include_router(client_policies_router)
app.include_router(security_router)
app.include_router(client_releases_router)

# ─── 健康检查 ─────────────────────────────────────────
@app.get('/api/health')
def health_check():
    """Verify the public API's database and Headscale control dependencies."""
    conn = None
    try:
        conn = get_db_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:
        raise HTTPException(503, "database unavailable") from exc
    finally:
        if conn is not None:
            conn.close()
    if not check_headscale_health():
        raise HTTPException(503, "headscale unavailable")
    return {'code': 0, 'msg': 'ok'}

# ─── 启动入口 ─────────────────────────────────────────
if __name__ == '__main__':
    import uvicorn
    uvicorn.run('main:app', host='127.0.0.1', port=5175, workers=1, log_level='info')
