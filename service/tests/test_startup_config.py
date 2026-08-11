from pathlib import Path

from app.core.config import Settings


def test_skip_auto_migrate_is_loaded_from_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "SKIP_AUTO_MIGRATE=1\\nSEED_DATA_ENABLED=false\\n",
        encoding="utf-8",
    )

    configured = Settings(_env_file=env_file)

    assert configured.SKIP_AUTO_MIGRATE is True
    assert configured.SEED_DATA_ENABLED is False
