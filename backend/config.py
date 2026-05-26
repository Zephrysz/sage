from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    gemini_api_key: str
    supabase_url: str
    supabase_service_key: str
    transcripts_path: str = "/data/transcripts.zip"
    port: int = 8000
    next_public_api_url: str = "http://localhost:8000"
    google_tts_key: str = ""


settings = Settings()
