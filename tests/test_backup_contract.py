from pathlib import Path


def test_full_backup_is_encrypted_complete_and_excludes_its_key() -> None:
    source = Path("scripts/backup.sh").read_text(encoding="utf-8")

    assert "pg_dump" in source
    assert "source.backup(target)" in source
    assert "copy_tree /opt/coinalyze" in source
    assert "copy_tree /opt/coinalyze-ai-bridge" in source
    assert "copy_tree /etc/coinalyze-ai-bridge" in source
    assert "openssl enc -aes-256-cbc" in source
    assert "--exclude 'backup.key'" in source
    assert "The encryption key is intentionally excluded" in source


def test_backup_excludes_python_build_artifacts() -> None:
    source = Path("scripts/backup.sh").read_text(encoding="utf-8")

    assert "--exclude 'build'" in source
