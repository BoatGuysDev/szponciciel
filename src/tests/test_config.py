from pathlib import Path

from config import PROJECT_ROOT, Settings


def test_defaults_when_env_empty(monkeypatch, tmp_path):
    for var in (
        "RUN_MODE",
        "MEDIA_ROOT",
        "DB_PATH",
        "COMPUTE_DEVICE",
        "WHISPER_MODEL",
        "MODEL",
        "ZERNIO_API_KEY",
        "GROUND_TRUTH_MEDIA_ACCOUNT_ID",
        "GOOGLE_GENAI_USE_VERTEXAI",
        "GOOGLE_CLOUD_PROJECT",
    ):
        monkeypatch.delenv(var, raising=False)

    s = Settings(_env_file=tmp_path / "missing.env")

    assert s.run_mode == "development"
    assert s.media_root == PROJECT_ROOT / "media"
    assert s.db_path == Path("szponciciel.db")
    assert s.compute_device == "cpu"
    assert s.whisper_model == "base"
    assert s.llm_model == "gemini-2.5-flash-lite"
    assert s.zernio_api_key is None
    assert s.ground_truth_media_account_id is None


def test_env_var_overrides(monkeypatch, tmp_path):
    monkeypatch.setenv("RUN_MODE", "test")
    monkeypatch.setenv("COMPUTE_DEVICE", "cuda")
    monkeypatch.setenv("WHISPER_MODEL", "large-v3")
    monkeypatch.setenv("MODEL", "gemini-2.0-pro")
    monkeypatch.setenv("ZERNIO_API_KEY", "secret")

    s = Settings(_env_file=tmp_path / "missing.env")

    assert s.run_mode == "test"
    assert s.compute_device == "cuda"
    assert s.whisper_model == "large-v3"
    assert s.llm_model == "gemini-2.0-pro"
    assert s.zernio_api_key == "secret"


def test_env_file_is_loaded(monkeypatch, tmp_path):
    for var in ("RUN_MODE", "COMPUTE_DEVICE", "MODEL"):
        monkeypatch.delenv(var, raising=False)

    env_file = tmp_path / ".env"
    env_file.write_text("RUN_MODE=production\nCOMPUTE_DEVICE=mps\nMODEL=gemini-x\n")

    s = Settings(_env_file=env_file)

    assert s.run_mode == "production"
    assert s.compute_device == "mps"
    assert s.llm_model == "gemini-x"
