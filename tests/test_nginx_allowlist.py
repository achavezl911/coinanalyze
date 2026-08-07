from pathlib import Path


def test_nginx_template_includes_server_allowlist():
    config = Path("deploy/nginx/coinalyze.conf").read_text()
    assert config.count("include /etc/nginx/snippets/coinalyze-allowlist.conf;") == 2
    assert "proxy_set_header X-Internal-Token __API_INTERNAL_TOKEN__;" in config


def test_install_scripts_write_nginx_allowlist():
    for script in ("deploy/proxmox/install.sh", "scripts/update.sh", "scripts/configure_secrets.sh"):
        text = Path(script).read_text()
        assert "render_nginx_allowlist" in text
        assert "/etc/nginx/snippets/coinalyze-allowlist.conf" in text
        assert "deny all;" in text
