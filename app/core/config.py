from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="CFDI Shield", alias="APP_NAME")
    app_version: str = Field(default="1.0", alias="APP_VERSION")
    debug: bool = Field(default=False, alias="DEBUG")
    api_v1_prefix: str = "/api/v1"
    database_url: str = Field(default="sqlite:///./facturas.db", alias="DATABASE_URL")
    port: int = Field(default=8000, alias="PORT")
    base_url: str = Field(default="http://127.0.0.1:8000", alias="BASE_URL")
    enable_registration: bool = Field(default=True, alias="ENABLE_REGISTRATION")
    enable_beta_mode: bool = Field(default=False, alias="ENABLE_BETA_MODE")
    beta_access_code: str = Field(default="", alias="BETA_ACCESS_CODE")
    beta_allowed_emails_raw: str = Field(default="", alias="BETA_ALLOWED_EMAILS")
    admin_maintenance_token: str = Field(default="", alias="ADMIN_MAINTENANCE_TOKEN")
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    allow_real_xml_upload: bool = Field(default=True, alias="ALLOW_REAL_XML_UPLOAD")
    auth_rate_limit_window_seconds: int = Field(default=900, alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    auth_rate_limit_ip_max_attempts: int = Field(default=10, alias="AUTH_RATE_LIMIT_IP_MAX_ATTEMPTS")
    auth_rate_limit_user_max_attempts: int = Field(default=5, alias="AUTH_RATE_LIMIT_USER_MAX_ATTEMPTS")
    sat_service_url: str = "https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc"
    sat_timeout_seconds: int = Field(default=10, alias="SAT_TIMEOUT_SECONDS")
    enable_sat_validation: bool = Field(default=True, alias="ENABLE_SAT_VALIDATION")
    sat_cache_ttl_seconds: int = Field(default=21600, alias="SAT_CACHE_TTL_SECONDS")
    enable_exchange_rate_api: bool = Field(default=True, alias="ENABLE_EXCHANGE_RATE_API")
    exchange_rate_api_url: str = Field(default="https://api.frankfurter.dev", alias="EXCHANGE_RATE_API_URL")
    exchange_rate_timeout_seconds: int = Field(default=5, alias="EXCHANGE_RATE_TIMEOUT_SECONDS")
    session_secret_key: str = Field(default="", alias="APP_SECRET_KEY")
    session_cookie_name: str = "facturas_session"
    session_max_age_seconds: int = 604800
    pending_two_factor_cookie_name: str = "facturas_pending_2fa"
    pending_two_factor_max_age_seconds: int = 900
    password_reset_token_ttl_minutes: int = 30
    two_factor_code_ttl_minutes: int = 10
    enable_two_factor: bool = Field(default=True, alias="ENABLE_2FA")
    local_mode: bool = Field(default=False, alias="LOCAL_MODE")
    master_encryption_key: str = Field(default="", alias="MASTER_ENCRYPTION_KEY")
    max_upload_size_bytes: int = Field(default=5242880, alias="MAX_UPLOAD_SIZE_BYTES")
    max_files_per_upload: int = Field(default=20, alias="MAX_FILES_PER_UPLOAD")
    smtp_host: str = Field(default="", alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_user: str = Field(default="", alias="SMTP_USER")
    smtp_password: str = Field(default="", alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(default="", alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    smtp_use_ssl: bool = Field(default=False, alias="SMTP_USE_SSL")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: str | None) -> str:
        if not value:
            return "sqlite:///./facturas.db"
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    @property
    def beta_allowed_emails(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.beta_allowed_emails_raw.split(",")
            if email.strip()
        }


settings = Settings()
