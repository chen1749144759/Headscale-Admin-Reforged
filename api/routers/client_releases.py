"""
客户端版本发布路由。
管理端用于发布 ScaleTail 客户端版本，客户端通过 client-reports 通道读取最新可用版本。
"""
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, get_db_conn, record_log, require_manager
from .ota import UPDATE_ACTIONS, verify_release_signature

router = APIRouter(prefix="/api/client-releases", tags=["客户端版本"])


class ClientReleaseReq(BaseModel):
    policy_revision: int = 0
    version: str
    platform: str = "windows-amd64"
    update_type: str = "suggested"
    title: str = ""
    description: str = ""
    download_url: str = ""
    sha256: str = ""
    signature: str = ""
    file_size: int = 0
    release_notes: str = ""


def _clean_release(req: ClientReleaseReq) -> ClientReleaseReq:
    req.version = str(req.version or "").strip()
    req.platform = str(req.platform or "windows-amd64").strip().lower()
    req.update_type = str(req.update_type or "suggested").strip().lower()
    req.title = str(req.title or "").strip()
    req.description = str(req.description or "").strip()
    req.download_url = str(req.download_url or "").strip()
    req.sha256 = str(req.sha256 or "").strip().lower()
    req.signature = str(req.signature or "").strip()
    req.release_notes = str(req.release_notes or "").strip()

    if len(req.version) > 64:
        raise HTTPException(400, "版本号长度不能超过 64 个字符")
    if req.update_type not in UPDATE_ACTIONS:
        raise HTTPException(400, "更新类型只能是 suggested、forced 或 clear")
    if len(req.title) > 200 or len(req.description) > 1000 or len(req.release_notes) > 20000:
        raise HTTPException(400, "客户端版本说明内容过长")
    try:
        policy = verify_release_signature(
            req.policy_revision,
            req.update_type,
            req.version,
            req.platform,
            req.sha256,
            req.file_size,
            req.download_url,
            req.signature,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    req.policy_revision = policy["policy_revision"]
    req.update_type = policy["update_type"]
    req.version = policy["version"]
    req.platform = policy["platform"]
    req.sha256 = policy["sha256"]
    req.file_size = policy["file_size"]
    req.download_url = policy["download_url"]
    return req


@router.get("")
def list_releases(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            "SELECT pg_advisory_xact_lock(hashtext(%s))",
            (f"scaletail-ota:{req.platform}",),
        )
        cur.execute(
            """
            SELECT COALESCE(MAX(policy_revision), 0) AS latest_revision
            FROM client_releases
            WHERE LOWER(platform) = %s
            """,
            (req.platform,),
        )
        latest_revision = int(cur.fetchone()["latest_revision"] or 0)
        if req.policy_revision <= latest_revision:
            raise HTTPException(
                409,
                f"策略修订号必须大于当前平台最新修订 {latest_revision}",
            )
        cur.execute(
            """
            SELECT
                id, policy_revision, version, platform, update_type, title, description,
                download_url, sha256, signature, file_size,
                release_notes, enabled, created_by_account_id,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM client_releases
            ORDER BY enabled DESC, policy_revision DESC, id DESC
            """
        )
        return {"code": 0, "data": cur.fetchall()}
    finally:
        conn.close()


@router.post("")
def create_release(req: ClientReleaseReq, user: CurrentUser = Depends(require_manager)):
    req = _clean_release(req)
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            INSERT INTO client_releases (
                policy_revision, version, platform, update_type, title, description,
                download_url, sha256, signature, file_size,
                release_notes, enabled, created_by_account_id
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, TRUE, %s)
            RETURNING id
            """,
            (
                req.policy_revision,
                req.version,
                req.platform,
                req.update_type,
                req.title,
                req.description,
                req.download_url,
                req.sha256,
                req.signature,
                req.file_size,
                req.release_notes,
                user.id,
            ),
        )
        row = cur.fetchone()
        record_log(conn, user.id, f"发布客户端更新策略 #{row['id']} r{req.policy_revision} {req.version} ({req.update_type})")
        conn.commit()
        return {"code": 0, "msg": "客户端版本已发布", "data": row}
    except psycopg2.errors.UniqueViolation as exc:
        conn.rollback()
        raise HTTPException(409, "该平台的更新策略修订号已经存在") from exc
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
