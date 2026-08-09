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


def _smoke_env_with_mid_probe_failure(
    tmp_path: Path, *, fail_after_url_substring: str, failed_unit: str
) -> dict[str, str]:
    """A collector that is healthy at the top of smoke_test.sh but dies once a specific
    HTTP probe fires. The fake `systemctl` only reports it failed once the marker file
    exists, so the pre-probe check must pass and only the post-probe recheck can catch it.
    """
    marker = tmp_path / "collector_died"
    _write_executable(
        tmp_path / "systemctl",
        f"""#!/usr/bin/env bash
set -eu
command=$1
shift
unit=${{!#}}
effective_failed=""
if [[ -f "{marker}" ]]; then
  effective_failed="{failed_unit}"
fi
if [[ $command == is-failed ]]; then
  [[ "$effective_failed" == "$unit" ]]
elif [[ $command == is-active ]]; then
  [[ "$effective_failed" != "$unit" ]]
else
  exit 0
fi
""",
    )
    _write_executable(
        tmp_path / "curl",
        f"""#!/usr/bin/env bash
set -eu
url=${{!#}}
case "$url" in
  *{fail_after_url_substring}*) touch "{marker}" ;;
esac
case "$url" in
  */api/healthz)
    printf '{{"status":"ok","services":[{{"service":"api","status":"ok","updated_at":"%s"}}]}}' \
      "${{HEARTBEAT_TS:-1970-01-01T00:03:30+00:00}}"
    ;;
  */api/symbols) printf '[]' ;;
  *) printf '{{}}' ;;
esac
""",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env['PATH']}",
            "METRICS_ENABLED": "false",
            "REQUIRED_SYSTEMD_SERVICES": f"coinalyze-api {failed_unit}",
            "REQUIRED_HEARTBEATS": "api",
            "DEPLOY_RESTART_EPOCH": "200",
            "COINALYZE_ENV_FILE": str(tmp_path / "missing.env"),
        }
    )
    return env


def test_smoke_fails_when_collector_dies_during_http_probes(tmp_path: Path):
    env = _smoke_env_with_mid_probe_failure(
        tmp_path,
        fail_after_url_substring="/api/symbols",
        failed_unit="coinalyze-ws@1.service",
    )

    result = subprocess.run(
        ["bash", str(ROOT / "scripts" / "smoke_test.sh")],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "coinalyze-ws@1.service" in result.stderr
    assert "Smoke test OK" not in result.stdout


def test_update_rechecks_services_immediately_before_success():
    source = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")

    smoke_call_idx = source.index("smoke_test.sh >/dev/null")
    complete_idx = source.index('echo "Update complete."')
    recheck_idx = source.index("has_unhealthy_service", smoke_call_idx)

    assert smoke_call_idx < recheck_idx < complete_idx


def _extract_bash_function(source: str, name: str) -> str:
    """Pull one `name() { ... }` function body out by brace-depth matching.

    Bash's own `${VAR}` expansions inside the body are balanced brace pairs, so a
    naive depth counter still finds the correct closing brace.
    """
    start = source.index(f"{name}() {{")
    open_idx = source.index("{", start)
    depth = 0
    idx = open_idx
    while True:
        char = source[idx]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                break
        idx += 1
    return source[start : idx + 1]


def _extract_final_success_gate(source: str) -> str:
    """Pull the literal `if <smoke passed> ... fi` success branch out of update.sh's
    health-gate loop (the block containing both post-smoke and post-backup rechecks),
    so the regression test below exercises the real, current code instead of a
    hand-copied reimplementation.
    """
    start = source.index('if REQUIRED_SYSTEMD_SERVICES="${SERVICES[*]}" \\\n')
    end = source.index("\n  fi\n", start) + len("\n  fi\n")
    return source[start:end]


def test_update_final_gate_rejects_inactive_not_failed_collector_after_smoke_passes(
    tmp_path: Path,
):
    """update.sh must never print 'Update complete.' if a required service is merely
    inactive (not systemd-failed) once smoke_test.sh has already succeeded — that gap
    is exactly what has_unhealthy_service (used both after smoke and after backup.sh)
    closes over the older has_failed_service, which only looked at `is-failed`.
    """
    source = (ROOT / "scripts" / "update.sh").read_text(encoding="utf-8")

    fake_smoke = tmp_path / "smoke_test.sh"
    _write_executable(fake_smoke, "#!/usr/bin/env bash\nexit 0\n")
    fake_backup = tmp_path / "backup.sh"
    _write_executable(fake_backup, "#!/usr/bin/env bash\nexit 0\n")

    success_gate = _extract_final_success_gate(source)
    success_gate = success_gate.replace(
        "/opt/coinalyze/scripts/smoke_test.sh", str(fake_smoke)
    ).replace("/opt/coinalyze/scripts/backup.sh", str(fake_backup))

    harness = "\n".join(
        [
            "#!/usr/bin/env bash",
            "set -Eeuo pipefail",
            "SERVICES=(coinalyze-api coinalyze-fake-ws)",
            "REQUIRED_HEARTBEATS=(api)",
            "DEPLOY_RESTART_EPOCH=0",
            _extract_bash_function(source, "report_service_failures"),
            _extract_bash_function(source, "has_unhealthy_service"),
            success_gate,
            "",
        ]
    )
    harness_path = tmp_path / "harness.sh"
    _write_executable(harness_path, harness)

    # coinalyze-fake-ws is inactive but NOT systemd-failed: the exact case
    # has_failed_service used to miss.
    _write_executable(
        tmp_path / "systemctl",
        """#!/usr/bin/env bash
set -eu
command=$1
shift
unit=${!#}
if [[ $command == is-failed ]]; then
  exit 1
elif [[ $command == is-active ]]; then
  [[ "$unit" != "coinalyze-fake-ws" ]]
else
  exit 0
fi
""",
    )
    env = os.environ.copy()
    env["PATH"] = f"{tmp_path}:{env['PATH']}"

    result = subprocess.run(
        ["bash", str(harness_path)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Update complete." not in result.stdout
    assert "coinalyze-fake-ws" in result.stderr
