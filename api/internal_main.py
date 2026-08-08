"""Private ScaleTail client API, reachable only through its dedicated UDS."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from api.internal_auth import MAX_BODY_BYTES, verify_internal_request
from api.routers import client_reports_router
from api.routers.dependencies import get_db_conn
from api.routers.headscale_client import close_client


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    close_client()


app = FastAPI(
    title="ScaleForge Internal Client API",
    docs_url=None,
    openapi_url=None,
    redoc_url=None,
    lifespan=lifespan,
)


@app.middleware("http")
async def verify_private_request(request: Request, call_next):
    if request.url.path == "/internal/health":
        return await call_next(request)
    body = await request.body()
    if len(body) > MAX_BODY_BYTES or not verify_internal_request(
        request.method,
        request.url.path,
        request.url.query,
        body,
        request.headers,
    ):
        return JSONResponse(
            status_code=401,
            content={"detail": "internal request authentication failed"},
        )
    return await call_next(request)


app.include_router(client_reports_router)


@app.get("/internal/health")
def health_check():
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
    return {"code": 0, "msg": "ok"}
