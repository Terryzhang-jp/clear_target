from pydantic_settings import BaseSettings
from functools import lru_cache
import os
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Clear Target API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # CORS设置
    BACKEND_CORS_ORIGINS: list = ["http://localhost:3000"]
    
    # 数据库设置
    DATABASE_URL: str = "sqlite+aiosqlite:///./sql_app.db"
    
    # JWT设置
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-for-development")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # Gemini API设置
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")

    class Config:
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
