from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Ellub Chat"
    secret_key: str = "troque-esta-chave-em-producao"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    database_url: str = "sqlite:///./multiatendimento.db"
    app_env: str = "development"
    demo_mode: bool = True
    cookie_secure: bool = False
    max_upload_size_mb: int = 10
    response_sla_minutes: int = 15
    whatsapp_customer_window_hours: int = 24
    whatsapp_window_warning_hours: int = 6
    whatsapp_window_urgent_minutes: int = 60
    enable_whatsapp_window_enforcement: bool = True

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def validate_runtime(self) -> None:
        if self.is_production:
            if self.secret_key == "troque-esta-chave-em-producao":
                raise RuntimeError("SECRET_KEY deve ser configurada em producao.")
            if self.demo_mode:
                raise RuntimeError("DEMO_MODE deve estar desativado em producao.")
            if self.database_url.startswith("sqlite"):
                raise RuntimeError("SQLite nao deve ser usado em producao.")
            if not self.cookie_secure:
                raise RuntimeError("COOKIE_SECURE deve ser true em producao.")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
