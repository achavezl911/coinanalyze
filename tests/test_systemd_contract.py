from pathlib import Path


def test_api_shutdown_timeout_is_shorter_than_systemd_timeout() -> None:
    source = Path("deploy/systemd/coinalyze-api.service").read_text(encoding="utf-8")

    assert "--timeout-graceful-shutdown 10" in source
    assert "TimeoutStopSec=20s" in source


def test_api_does_not_use_deprecated_orjson_response_class() -> None:
    source = Path("app/api.py").read_text(encoding="utf-8")

    assert "ORJSONResponse" not in source
    assert "default_response_class=JSONResponse" in source


def test_backup_service_is_hardened_and_resource_limited() -> None:
    source = Path("deploy/systemd/coinalyze-backup.service").read_text(encoding="utf-8")

    for directive in (
        "PrivateDevices=true",
        "ProtectHome=true",
        "ProtectKernelLogs=true",
        "RestrictNamespaces=true",
        "SystemCallArchitectures=native",
        "CPUWeight=25",
        "IOWeight=25",
        "TimeoutStartSec=1h",
        "ReadWritePaths=/var/backups/coinalyze /var/lib/coinalyze-ai-bridge",
    ):
        assert directive in source


def test_fresh_install_enables_unattended_security_updates() -> None:
    source = Path("deploy/proxmox/install.sh").read_text(encoding="utf-8")
    apt_config = Path("deploy/apt/20auto-upgrades").read_text(encoding="utf-8")

    assert "unattended-upgrades" in source
    assert 'APT::Periodic::Unattended-Upgrade "1";' in apt_config
    assert 'install -m 0644 "$SOURCE_DIR/deploy/apt/20auto-upgrades"' in source
    assert "apt-daily-upgrade.timer" in source


def test_install_and_update_build_package_outside_live_tree() -> None:
    install = Path("deploy/proxmox/install.sh").read_text(encoding="utf-8")
    update = Path("scripts/update.sh").read_text(encoding="utf-8")

    assert '--no-deps "$SOURCE_DIR"' in install
    assert '--no-deps "$SOURCE_DIR"' in update
    assert "--no-deps /opt/coinalyze" not in install
    assert "--no-deps /opt/coinalyze" not in update


def test_horizontal_collectors_have_compatible_template_units() -> None:
    for name, module in (("ws", "ws_collector"), ("scalp", "scalp_collector")):
        source = Path(f"deploy/systemd/coinalyze-{name}@.service").read_text(encoding="utf-8")
        assert "Environment=COLLECTOR_SHARD_COUNT=1" in source
        assert "COLLECTOR_SHARD_INDEX=%i" in source
        assert f"python -m app.{module}" in source


def test_scalable_services_acquire_lifetime_locks_before_websockets() -> None:
    for module in ("app/ws_collector.py", "app/scalp_collector.py"):
        source = Path(module).read_text(encoding="utf-8")
        assert source.index("await acquire_service_lock(") < source.index("await create_pool(")

    assert 'acquire_service_lock(settings, "ingest")' in Path("app/ingest.py").read_text()
    assert 'acquire_service_lock(settings, "daily")' in Path("app/daily_agg.py").read_text()


def test_update_restarts_active_template_instances_without_starting_legacy_duplicates() -> None:
    source = Path("scripts/update.sh").read_text(encoding="utf-8")
    assert "ACTIVE_SHARD_SERVICES" in source
    assert "'coinalyze-ws@*.service' 'coinalyze-scalp@*.service'" in source
    assert "enable --now coinalyze-scalp" not in source
