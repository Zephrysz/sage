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
    transcripts_path: str = "/data/Transcricoes/courses/output"
    port: int = 8000
    next_public_api_url: str = "http://localhost:8000"
    google_tts_key: str = ""
    # Allowed CORS origins — comma-separated list, e.g. "https://app.example.com,http://localhost:3000"
    cors_origins: str = "http://localhost:3000,http://localhost:3333"
    # Session store path — use a volume-mounted path in prod
    session_store_path: str = "/tmp/cefis_sessions.json"

    @property
    def tts_api_key(self) -> str:
        return self.google_tts_key or self.gemini_api_key

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
