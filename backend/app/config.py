from pydantic_settings import BaseSettings, SettingsConfigDict


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://naive:naive@postgres:5432/naive"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 720
    admin_username: str = "admin"
    admin_password: str = "admin"
    domain: str = ""
    singbox_config_path: str = "/data/singbox/config.json"
    caddyfile_path: str = "/data/caddy/Caddyfile"
    singbox_container: str = "singbox"
    caddy_container: str = "caddy"


settings = AppSettings()
