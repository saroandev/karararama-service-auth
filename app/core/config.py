"""
Application configuration using Pydantic Settings.
Loads environment variables from .env file.
"""
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Attributes:
        APP_NAME: Application name
        APP_VERSION: Application version
        DEBUG: Debug mode flag
        DATABASE_URL: PostgreSQL connection string
        JWT_SECRET_KEY: Secret key for JWT encoding/decoding
        JWT_ALGORITHM: JWT algorithm (default: HS256)
        ACCESS_TOKEN_EXPIRE_MINUTES: Access token expiration time
        REFRESH_TOKEN_EXPIRE_DAYS: Refresh token expiration time
        CORS_ORIGINS: Allowed CORS origins
        HOST: Server host
        PORT: Server port
    """

    # Application
    APP_NAME: str = "OneDocs Auth Service"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5441
    POSTGRES_USER: str = "onedocs_user"
    POSTGRES_PASSWORD: str = "onedocs_pass_2024"
    POSTGRES_DB: str = "onedocs_auth"
    DATABASE_URL: str

    # JWT
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8001

    # Password Reset
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 30
    PASSWORD_RESET_RATE_LIMIT_REQUESTS: int = 3
    PASSWORD_RESET_RATE_LIMIT_WINDOW_HOURS: int = 1
    FRONTEND_RESET_PASSWORD_URL: str = "http://localhost:3000/reset-password"

    # pgAdmin (optional, not used in app)
    PGADMIN_DEFAULT_EMAIL: str = "admin@onedocs.com"
    PGADMIN_DEFAULT_PASSWORD: str = "admin123"
    PGADMIN_PORT: int = 5051

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True
    )

    @property
    def cors_origins_list(self) -> List[str]:
        """Convert CORS_ORIGINS string to list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]


# Global settings instance
settings = Settings()