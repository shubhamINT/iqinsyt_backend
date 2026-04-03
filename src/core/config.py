from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "iqinsyt"
    API_KEY: str = "dev-key-change-me"
    OPENAI_API_KEY: str = ""
    BRAVE_API_KEY: str = ""
    APP_VERSION: str = "0.1.0"

    # CORS — comma-separated list of allowed origins
    CORS_ORIGINS: str = "chrome-extension://*,http://localhost:*"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_JSON_FORMAT: bool = False
    LOG_FILE: str = "logs/app.log"
    LOG_MAX_BYTES: int = 10_485_760
    LOG_BACKUP_COUNT: int = 5

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
