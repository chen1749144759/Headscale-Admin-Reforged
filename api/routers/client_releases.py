"""
客户端版本发布路由。
管理端用于发布 ScaleTail 客户端版本，客户端通过 client-reports 通道读取最新可用版本。
"""
import base64
import binascii
import re

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from .dependencies import CurrentUser, get_db_conn, record_log, require_manager

router = APIRouter(prefix="/api/client-releases", tags=["客户端版本"])

UPDATE_TYPES = ("suggested", "forced")
SHA256_PATTERN = re.compile(r"^[a-f0-9]{64}$")
MAX_INSTALLER_SIZE = 1024 * 1024 * 1024


class ClientReleaseReq(BaseModel):
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
    enabled: bool = True


class ReleaseToggleReq(BaseModel):
    enabled: bool


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

    if not req.version:
        raise HTTPException(400, "版本号不能为空")
    if not req.platform:
        raise HTTPException(400, "平台不能为空")
    if req.update_type not in UPDATE_TYPES:
        raise HTTPException(400, "更新类型只能是 suggested 或 forced")
    if not req.download_url:
        raise HTTPException(400, "下载地址不能为空")
    if not req.download_url.lower().startswith(("http://", "https://")):
        raise HTTPException(400, "下载地址必须以 http:// 或 https:// 开头")
    if not SHA256_PATTERN.fullmatch(req.sha256):
        raise HTTPException(400, "SHA-256 必须是 64 位十六进制字符串")
    try:
        signature = base64.b64decode(req.signature, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, "Ed25519 签名必须是有效的 Base64")
    if len(signature) != 64:
        raise HTTPException(400, "Ed25519 签名长度无效")
    if req.file_size <= 0 or req.file_size > MAX_INSTALLER_SIZE:
        raise HTTPException(400, "安装包大小必须在 1 字节到 1 GiB 之间")
    return req


@router.get("")
def list_releases(user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute(
            """
            SELECT
                id, version, platform, update_type, title, description,
                download_url, sha256, signature, file_size,
                release_notes, enabled, created_by,
                TO_CHAR(created_at, 'YYYY-MM-DD HH24:MI:SS') AS created_at,
                TO_CHAR(updated_at, 'YYYY-MM-DD HH24:MI:SS') AS updated_at
            FROM client_releases
            ORDER BY enabled DESC, created_at DESC, id DESC
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
                version, platform, update_type, title, description,
                download_url, sha256, signature, file_size,
                release_notes, enabled, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING id
            """,
            (
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
                req.enabled,
                user.id,
            ),
        )
        row = cur.fetchone()
        record_log(conn, user.id, f"发布客户端版本 #{row['id']} {req.version} ({req.update_type})")
        conn.commit()
        return {"code": 0, "msg": "客户端版本已发布", "data": row}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.put("/{release_id}")
def update_release(release_id: int, req: ClientReleaseReq, user: CurrentUser = Depends(require_manager)):
    req = _clean_release(req)
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE client_releases SET
                version=%s, platform=%s, update_type=%s, title=%s, description=%s,
                download_url=%s, sha256=%s, signature=%s, file_size=%s,
                release_notes=%s, enabled=%s, updated_at=NOW()
            WHERE id=%s
            """,
            (
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
                req.enabled,
                release_id,
            ),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "客户端版本不存在")
        record_log(conn, user.id, f"更新客户端版本 #{release_id} {req.version}")
        conn.commit()
        return {"code": 0, "msg": "客户端版本已更新"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.patch("/{release_id}/toggle")
def toggle_release(release_id: int, req: ReleaseToggleReq, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE client_releases SET enabled=%s, updated_at=NOW() WHERE id=%s",
            (req.enabled, release_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "客户端版本不存在")
        record_log(conn, user.id, f"{'启用' if req.enabled else '停用'}客户端版本 #{release_id}")
        conn.commit()
        return {"code": 0, "msg": "状态已更新"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@router.delete("/{release_id}")
def delete_release(release_id: int, user: CurrentUser = Depends(require_manager)):
    conn = get_db_conn()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM client_releases WHERE id=%s", (release_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "客户端版本不存在")
        record_log(conn, user.id, f"删除客户端版本 #{release_id}")
        conn.commit()
        return {"code": 0, "msg": "客户端版本已删除"}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
