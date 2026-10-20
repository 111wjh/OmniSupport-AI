
from sqlalchemy.orm import DeclarativeBase

#帮助 SQLAlchemy 识别 Python 类与数据库表之间的映射关系。
class Base(DeclarativeBase):
    """
    所有 SQLAlchemy ORM 模型的公共基类。

    后续 Conversation、Message 等模型
    都会继承这个 Base。
    """
    pass
