"""FlashPaper configuration using pydantic-settings."""

from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Gemini
    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key. Leave empty for demo mode.",
    )
    gemini_model: str = Field(
        default="gemini-2.5-flash",
        description="Gemini model to use for paper analysis (gemini-3.5-flash when released)",
    )
    gemini_max_output_tokens: int = Field(default=65536, ge=1024, le=131072)

    # App behavior
    demo_mode: bool = Field(
        default=False, description="If true, use only pre-seeded demos (no API calls)"
    )
    max_pdf_mb: int = Field(default=25, ge=1, le=100)
    generated_dir: Path = Field(default=Path("generated"))
    demo_dir: Path = Field(default=Path("demo"))

    # Rate limiting (simple in-memory for MVP)
    rate_limit_per_ip_per_hour: int = Field(default=10)

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False

    @field_validator("gemini_api_key")
    @classmethod
    def validate_api_key(cls, v: str) -> str:
        if not v or v == "your_gemini_api_key_here":
            # Allow empty in demo mode only (checked at runtime)
            return v
        return v

    @field_validator("generated_dir", "demo_dir", mode="after")
    @classmethod
    def ensure_dirs(cls, v: Path) -> Path:
        v.mkdir(parents=True, exist_ok=True)
        return v

    @property
    def is_demo_mode(self) -> bool:
        """Check if we should skip real Gemini calls."""
        return self.demo_mode or not self.gemini_api_key or self.gemini_api_key.startswith("your_")


settings = Settings()  # Singleton for import

# Ensure critical dirs exist at import time
settings.generated_dir.mkdir(parents=True, exist_ok=True)
settings.demo_dir.mkdir(parents=True, exist_ok=True)
