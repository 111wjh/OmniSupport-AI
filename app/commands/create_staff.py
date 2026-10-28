
import asyncio
import selectors
import sys
from getpass import getpass
from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal, engine
from app.models.staff import Staff, StaffRole


async def main() -> None:
    """通过受控的本地命令创建员工账号。"""

    try:
        # 1. 获取并验证员工邮箱
        raw_email = input("员工邮箱: ").strip()
        email = str(
            TypeAdapter(EmailStr).validate_python(raw_email)
        ).lower()

        # 2. 获取员工显示名称
        display_name = input("员工显示名称: ").strip()

        if not display_name or len(display_name) > 100:
            raise ValueError("员工显示名称长度必须为 1 至 100 个字符")

        # 3. 选择员工角色
        print("可选角色:")
        for role_option in StaffRole:
            print(f"  - {role_option.value}")

        role = input("员工角色: ").strip()

        if role not in {item.value for item in StaffRole}:
            raise ValueError("无效的员工角色")

        # 4. 安全输入密码，不在终端回显
        password = getpass("员工密码（至少 12 个字符）: ")

        if len(password) < 12:
            raise ValueError("员工密码至少需要 12 个字符")

        if len(password) > 128:
            raise ValueError("员工密码不能超过 128 个字符")

        confirmation = getpass("再次输入员工密码: ")

        if password != confirmation:
            raise ValueError("两次输入的密码不一致")

        # 5. 查询数据库并创建员工
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Staff.id).where(Staff.email == email)
            )

            if result.scalar_one_or_none() is not None:
                raise ValueError("该员工邮箱已经存在")

            staff = Staff(
                email=email,
                password_hash=hash_password(password),
                display_name=display_name,
                role=role,
                is_active=True,
            )

            session.add(staff)

            try:
                await session.commit()
            except IntegrityError as exc:
                await session.rollback()
                raise ValueError(
                    "创建失败：邮箱重复或违反数据库约束"
                ) from exc

            await session.refresh(staff)

            print("员工账号创建成功")
            print(f"员工 ID: {staff.id}")
            print(f"员工邮箱: {staff.email}")
            print(f"员工角色: {staff.role}")
            print(f"账号启用: {staff.is_active}")

    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(
            main(),
            loop_factory=lambda: asyncio.SelectorEventLoop(
                selectors.SelectSelector()
            ),
        )
    except (ValueError, ValidationError) as exc:
        print(f"创建失败：{exc}", file=sys.stderr)
        raise SystemExit(1) from exc
