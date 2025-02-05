from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from .config import get_settings

settings = get_settings()

# 创建异步引擎
engine = create_async_engine(
    "sqlite+aiosqlite:///./sql_app.db",
    echo=True,
)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
) 