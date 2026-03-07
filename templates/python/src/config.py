"""Application configuration via Pydantic Settings."""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Application
    app_name: str = Field(default="{{PROJECT_NAME}}")
    app_version: str = Field(default="0.1.0")
    debug: bool = Field(default=False)
    
    # Server
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    
    # Database
    database_url: str = Field(
        default="sqlite:///./{{PROJECT_NAME}}.db",
        description="Database connection URL"
    )
    
    # Security
    secret_key: str = Field(
        default="change-me-in-production",
        description="Secret key for JWT tokens"
    )
    access_token_expire_minutes: int = Field(default=30)
    
    # CORS
    cors_origins: list[str] = Field(default=["*"])
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
