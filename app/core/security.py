from pwdlib import PasswordHash


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