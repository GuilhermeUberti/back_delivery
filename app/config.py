from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    COOKIE_SECURE: bool = False  # True em produção (Railway): SameSite=None; Secure

    ZAPI_INSTANCE: str = ""
    ZAPI_TOKEN: str = ""

    EFI_CLIENT_ID: str = ""
    EFI_CLIENT_SECRET: str = ""
    EFI_SANDBOX: bool = True
    EFI_CERT_PATH: str = ""  # path to .pem certificate (mTLS obrigatório em produção)
    EFI_KEY_PATH: str = ""   # path to .pem private key

    MP_ACCESS_TOKEN: str = ""
    MP_NOTIFICATION_URL: str = ""  # URL pública para receber webhooks do Mercado Pago

    R2_ACCOUNT_ID: str = ""
    R2_ACCESS_KEY_ID: str = ""
    R2_SECRET_ACCESS_KEY: str = ""
    R2_BUCKET_NAME: str = "zapedido-images"
    R2_PUBLIC_URL: str = ""


settings = Settings()
