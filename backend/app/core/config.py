from pydantic_settings import BaseSettings
from typing import List
import os

class Settings(BaseSettings):
    APP_NAME: str = "GoatRaw"
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "change-me-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", os.getenv("FRONTEND_URL", "https://app.goatraw.ai")]
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/goatraw")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    TOGETHER_API_KEY: str = os.getenv("TOGETHER_API_KEY", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    SLACK_BOT_TOKEN: str = os.getenv("SLACK_BOT_TOKEN", "")
    WHATSAPP_ACCESS_TOKEN: str = os.getenv("WHATSAPP_ACCESS_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    WHATSAPP_VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "goatraw-verify")
    DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
    SERPAPI_KEY: str = os.getenv("SERPAPI_KEY", "")
    ENABLE_BROWSER_TOOL: bool = os.getenv("ENABLE_BROWSER_TOOL", "false").lower() == "true"
    MAX_TASK_STEPS: int = 10
    TASK_TIMEOUT_SECONDS: int = 300
    RATE_LIMIT_FREE: int = 10
    RATE_LIMIT_PRO: int = 100
    RATE_LIMIT_ENTERPRISE: int = 1000
    DEFAULT_HEARTBEAT_INTERVAL: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
