import importlib

from config import load_config


def test_cli_import_does_not_assume_repository_root():
    importlib.import_module("cli")


def test_load_config_uses_api_samples_directory_by_default(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@db:5432/test")
    monkeypatch.delenv("SAMPLE_DIR", raising=False)

    assert load_config().sample_dir.name == "api-samples"
