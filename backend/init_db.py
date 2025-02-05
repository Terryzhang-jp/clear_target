import asyncio
from app.database import engine
from app.models import Base

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    print("数据库表已创建完成！")

if __name__ == "__main__":
    asyncio.run(init_db()) 