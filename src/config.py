from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    run_mode: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"

    media_root: Path = PROJECT_ROOT / "media"

    compute_device: str = "cpu"
    whisper_model: str = "base"
    tts_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    llm_model: str = Field(default="gemini-2.5-flash-lite", validation_alias="MODEL")

    zernio_api_key: str | None = None
    tavily_api_key: str | None = None
    ground_truth_media_account_id: str | None = None
    google_genai_use_vertexai: bool | None = None
    google_cloud_project: str | None = None

    writer_critic_max_iters: int = Field(default=3, ge=1)
    script_reliability_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    max_script_length: int = Field(default=8_000, ge=1)


settings = Settings()
