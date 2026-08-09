from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path: Path, source: str) -> None:
    path.write_text(source, encoding="utf-8")
    path.chmod(0o755)


def _smoke_env(tmp_path: Path, **overrides: str) -> dict[str, str]:
    _write_executable(
        tmp_path / "systemctl",
        """#!/usr/bin/env bash
set -eu
command=$1
shift
unit=${!#}
if [[ $command == is-failed ]]; then
  [[ ${FAILED_UNIT:-} == "$unit" ]]
elif [[ $command == is-active ]]; then
  [[ ${FAILED_UNIT:-} != "$unit" ]]
else
  exit 0
fi
""",
    )
    _write_executable(
        tmp_path / "curl",
        """#!/usr/bin/env bash
set -eu
url=${!#}
case "$url" in
  */api/healthz)
    printf '{"status":"%s","services":[{"service":"api","status":"ok","updated_at":"%s"}]}' \
      "${HEALTH_STATUS:-ok}" "${HEARTBEAT_TS:-1970-01-01T00:03:30+00:00}"
    ;;
  */api/symbols) printf '[]' ;;
  *) printf '{}' ;;
esac
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "METRICS_ENABLED": "false",
            "REQUIRED_SYSTEMD_SERVICES": "coinalyze-api coinalyze-ws@1.service",
            "REQUIRED_HEARTBEATS": "api",
            "DEPLOY_RESTART_EPOCH": "200",
            "COINALYZE_ENV_FILE": str(tmp_path / "missing.env"),
        }
    )
    env.update(overrides)
    return env


def test_smoke_fails_when_health_is_degraded_and_enabled_collector_failed(tmp_path: Path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "smoke_test.sh")],
        env=_smoke_env(
            tmp_path,
            HEALTH_STATUS="degraded",
            FAILED_UNIT="coinalyze-ws@1.service",
        ),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "coinalyze-ws@1.service" in result.stderr
    assert "Smoke test OK" not in result.stdout


def test_smoke_fails_when_required_heartbeat_predates_restart(tmp_path: Path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "smoke_test.sh")],
        env=_smoke_env(tmp_path, HEARTBEAT_TS="1970-01-01T00:01:40+00:00"),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "heartbeat predates restart: api" in result.stderr
    assert "Smoke test OK" not in result.stdout


def test_smoke_accepts_only_ok_health_with_post_restart_heartbeat(tmp_path: Path):
    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "smoke_test.sh")],
        env=_smoke_env(tmp_path),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Smoke test OK" in result.stdout


def test_update_uses_database_restart_time_and_all_required_units():
    source = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")

    assert "extract(epoch FROM clock_timestamp())" in source
    assert 'REQUIRED_SYSTEMD_SERVICES="${SERVICES[*]}"' in source
    assert "ingest:ohlcv_1m" in source
    assert "ingest:metrics_5m" in source
    assert source.index("smoke_test.sh >/dev/null") < source.index('echo "Update complete."')
