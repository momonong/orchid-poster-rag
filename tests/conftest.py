import pytest


@pytest.fixture(autouse=True)
def isolated_records(tmp_path, monkeypatch):
    # Every app uses real SQLite, but never the deployment's visitor database.
    monkeypatch.setenv("ORCHID_RECORDS_FILE", str(tmp_path / "visitor-records.sqlite3"))
    for name in ("SELFHOST_MODEL_CONTEXT_TOKENS", "SELFHOST_MODEL_API_KEY",
                 "SELFHOST_MODEL_API_KEY_FILE", "SELFHOST_MODEL_BASE_URL", "SELFHOST_MODEL_EXPECTED_ID"):
        monkeypatch.delenv(name, raising=False)
