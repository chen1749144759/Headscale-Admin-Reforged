"""ScaleTail OTA v3 policy validation shared by publishing and delivery paths."""

from __future__ import annotations

import base64
import binascii
import re
from typing import Any
from urllib.parse import urlsplit

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .versioning import parse_semver


OTA_PUBLIC_KEY_BASE64 = "vLGmMjFWFdcyPurQt1EZ1cDZgY4FcroH4aRMfDpEP2o="
MAX_INSTALLER_SIZE = 1024 * 1024 * 1024
MAX_POLICY_REVISION = (1 << 53) - 1
UPDATE_ACTIONS = ("suggested", "forced", "clear")
_UNRESERVED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")
_PLATFORM = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_V3_SIGNATURE = re.compile(r"^v3\.([A-Za-z0-9+/]{86}==)$")


def validated_download_url(raw: str) -> str:
    value = str(raw or "").strip()
    if not value or len(value) > 2048 or value.endswith("?"):
        raise ValueError("安装包下载地址无效")
    try:
        parsed = urlsplit(value)
        _ = parsed.port
    except ValueError as exc:
        raise ValueError("安装包下载地址无效") from exc
    host = str(parsed.hostname or "").lower()
    if (
        parsed.scheme.lower() != "https"
        or not _valid_download_host(host)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
        or not parsed.netloc
    ):
        raise ValueError("安装包下载地址必须是无凭据、无片段且非本地 DNS 主机名的 HTTPS URL")
    port = parsed.port
    path = _normalize_url_component(parsed.path or "/")
    query = _normalize_url_component(parsed.query)
    canonical = f"https://{host}"
    if port and port != 443:
        canonical += f":{port}"
    canonical += path
    if query:
        canonical += f"?{query}"
    return canonical


def _valid_download_host(host: str) -> bool:
    if not host or host.endswith(".") or host == "localhost" or host.endswith(".localhost"):
        return False
    if ":" in host:
        return False
    labels = host.split(".")
    return all(
        label
        and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and all(char.isascii() and (char.islower() or char.isdigit() or char == "-") for char in label)
        for label in labels
    ) and not _numeric_host_literal(labels)


def _numeric_host_literal(labels: list[str]) -> bool:
    for label in labels:
        if label.startswith("0x"):
            if len(label) == 2 or any(char not in "0123456789abcdef" for char in label[2:]):
                return False
            continue
        if not label.isdigit():
            return False
    return True


def _normalize_url_component(value: str) -> str:
    result: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if ord(char) < 0x21 or ord(char) > 0x7E or char == "\\":
            raise ValueError("安装包下载地址包含不安全字符")
        if char != "%":
            result.append(char)
            index += 1
            continue
        hex_value = value[index + 1 : index + 3]
        if len(hex_value) != 2 or not re.fullmatch(r"[0-9A-Fa-f]{2}", hex_value):
            raise ValueError("安装包下载地址包含无效转义")
        decoded = chr(int(hex_value, 16))
        result.append(decoded if decoded in _UNRESERVED else f"%{hex_value.upper()}")
        index += 3
    return "".join(result)


def canonical_version(raw: str) -> str:
    value = str(raw or "").strip()
    if parse_semver(value) is None:
        raise ValueError("版本号必须符合 Semantic Versioning")
    if value[:1] in ("v", "V"):
        value = value[1:]
    return value


def canonical_policy(
    policy_revision: int,
    update_type: str,
    version: str,
    platform: str,
    sha256_hex: str,
    file_size: int,
    download_url: str,
) -> dict[str, Any]:
    try:
        revision = int(policy_revision)
        size = int(file_size)
    except (TypeError, ValueError) as exc:
        raise ValueError("更新策略修订号或安装包大小无效") from exc
    if revision <= 0 or revision > MAX_POLICY_REVISION:
        raise ValueError("更新策略修订号必须是正整数且不超过 JavaScript 安全整数范围")

    action = str(update_type or "").strip().lower()
    if action not in UPDATE_ACTIONS:
        raise ValueError("更新策略动作必须是 suggested、forced 或 clear")
    canonical_platform = str(platform or "").strip().lower()
    if not _PLATFORM.fullmatch(canonical_platform):
        raise ValueError("平台标识只能包含小写字母、数字和短横线")

    result = {
        "policy_revision": revision,
        "update_type": action,
        "version": canonical_version(version),
        "platform": canonical_platform,
        "sha256": str(sha256_hex or "").strip().lower(),
        "file_size": size,
        "download_url": str(download_url or "").strip(),
    }
    if action == "clear":
        if result["sha256"] or size != 0 or result["download_url"]:
            raise ValueError("clear 策略不能包含安装包元数据")
        return result

    if not _SHA256.fullmatch(result["sha256"]):
        raise ValueError("SHA-256 必须是 64 位十六进制字符串")
    if size <= 0 or size > MAX_INSTALLER_SIZE:
        raise ValueError("安装包大小必须在 1 字节到 1 GiB 之间")
    result["download_url"] = validated_download_url(result["download_url"])
    return result


def ota_message(
    policy_revision: int,
    update_type: str,
    version: str,
    platform: str,
    sha256_hex: str,
    file_size: int,
    download_url: str,
) -> bytes:
    policy = canonical_policy(
        policy_revision,
        update_type,
        version,
        platform,
        sha256_hex,
        file_size,
        download_url,
    )
    return (
        "scaletail-update-v3\n"
        f"{policy['policy_revision']}\n"
        f"{policy['update_type']}\n"
        f"{policy['version']}\n"
        f"{policy['platform']}\n"
        f"{policy['sha256']}\n"
        f"{policy['file_size']}\n"
        f"{policy['download_url']}\n"
    ).encode("utf-8")


def verify_release_signature(
    policy_revision: int,
    update_type: str,
    version: str,
    platform: str,
    sha256_hex: str,
    file_size: int,
    download_url: str,
    signature_envelope: str,
) -> dict[str, Any]:
    try:
        public_key = base64.b64decode(OTA_PUBLIC_KEY_BASE64, validate=True)
        signature = _parse_v3_signature(signature_envelope)
    except (ValueError, binascii.Error) as exc:
        raise ValueError("Ed25519 签名必须是有效的 v3 信封") from exc
    if len(public_key) != 32:
        raise ValueError("内置 Ed25519 公钥长度无效")
    policy = canonical_policy(
        policy_revision,
        update_type,
        version,
        platform,
        sha256_hex,
        file_size,
        download_url,
    )
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(
            signature,
            ota_message(**_message_kwargs(policy)),
        )
    except InvalidSignature as exc:
        raise ValueError("Ed25519 签名与更新策略元数据不匹配") from exc
    return policy


def _message_kwargs(policy: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy_revision": policy["policy_revision"],
        "update_type": policy["update_type"],
        "version": policy["version"],
        "platform": policy["platform"],
        "sha256_hex": policy["sha256"],
        "file_size": policy["file_size"],
        "download_url": policy["download_url"],
    }


def _parse_v3_signature(value: str) -> bytes:
    match = _V3_SIGNATURE.fullmatch(str(value or "").strip())
    if not match:
        raise ValueError("签名不是 v3 信封")
    try:
        signature = base64.b64decode(match.group(1), validate=True)
    except binascii.Error as exc:
        raise ValueError("签名编码无效") from exc
    if len(signature) != 64:
        raise ValueError("Ed25519 签名长度无效")
    return signature


def encode_v3_signature(signature: bytes) -> str:
    if len(signature) != 64:
        raise ValueError("Ed25519 签名长度无效")
    return f"v3.{base64.b64encode(signature).decode('ascii')}"


def release_signature_valid(release: dict[str, Any]) -> bool:
    try:
        verify_release_signature(
            int(release.get("policy_revision") or 0),
            str(release.get("update_type") or ""),
            str(release.get("version") or ""),
            str(release.get("platform") or ""),
            str(release.get("sha256") or ""),
            int(release.get("file_size") or 0),
            str(release.get("download_url") or ""),
            str(release.get("signature") or ""),
        )
        return True
    except (TypeError, ValueError):
        return False
