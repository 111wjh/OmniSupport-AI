from pwdlib import PasswordHash

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt

from app.core.config import get_settings

# 创建推荐的安全密码哈希算法
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """将明文密码转换为安全的密码哈希。"""
    return password_hash.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str,
) -> bool:
    """验证用户输入的密码是否正确。"""
    return password_hash.verify(
        plain_password,
        hashed_password,
    )


def create_access_token(subject: str) -> str:
    """为已通过身份验证的客户生成 JWT 访问令牌。"""

    settings = get_settings()

    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY 未配置")

    if settings.JWT_ALGORITHM != "HS256":
        raise ValueError("当前项目仅支持 HS256 算法")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )

    payload = {
        "sub": subject,
        "iat": now,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """验证 JWT 签名与有效期，并返回令牌中的声明。"""

    settings = get_settings()

    if not settings.JWT_SECRET_KEY:
        raise ValueError("JWT_SECRET_KEY 未配置")

    if settings.JWT_ALGORITHM != "HS256":
        raise ValueError("当前项目仅支持 HS256 算法")

    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )
