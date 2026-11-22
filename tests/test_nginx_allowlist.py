from pathlib import Path


def test_nginx_template_includes_server_allowlist():
    config = Path("deploy/nginx/coinalyze.conf").read_text()
    assert config.count("include /etc/nginx/snippets/coinalyze-allowlist.conf;") == 2
    assert "proxy_set_header X-Internal-Token __API_INTERNAL_TOKEN__;" in config


def test_install_scripts_write_nginx_allowlist():
    for script in ("deploy/proxmox/install.sh", "scripts/configure_secrets.sh"):
        text = Path(script).read_text()
        assert "render_nginx_allowlist" in text
        assert "/etc/nginx/snippets/coinalyze-allowlist.conf" in text
        assert "deny all;" in text


def _bloques(texto: str) -> list[tuple[str, list[str]]]:
    """(cabecera, directivas propias) de cada bloque «x {...}»; las de los bloques hijos no cuentan en el padre."""
    pila: list[tuple[str, list[str]]] = [("", [])]
    salida: list[tuple[str, list[str]]] = []
    for linea in texto.splitlines():
        linea = linea.strip()
        if linea.startswith("#"):
            continue
        if linea.endswith("{"):
            pila.append((linea[:-1].strip(), []))
        elif linea == "}":
            salida.append(pila.pop())
        elif linea:
            pila[-1][1].append(linea)
    return salida


def _cabeceras(directivas: list[str]) -> dict[str, str]:
    return {d.split()[1]: d.split(None, 2)[2] for d in directivas if d.startswith("add_header ")}


def test_solo_flujo_se_deja_enmarcar_y_solo_desde_el_mismo_origen():
    bloques = _bloques(Path("deploy/nginx/coinalyze.conf").read_text())
    servidor = next(d for c, d in bloques if c == "server" and "listen 8443 ssl default_server;" in d)
    locs = {c: d for c, d in bloques if c.startswith("location")}
    flujo, raiz = locs["location = /flujo"], locs["location /"]
    del_servidor, de_flujo = _cabeceras(servidor), _cabeceras(flujo)
    # add_header en una location anula los del servidor: los siete, y con los mismos valores salvo el marco.
    assert len(del_servidor) == 7 and set(de_flujo) == set(del_servidor)
    assert len([d for d in flujo if d.startswith("add_header ")]) == 7
    assert "frame-ancestors 'none'" in del_servidor["Content-Security-Policy"]
    assert del_servidor["X-Frame-Options"] == '"DENY" always;'
    assert de_flujo["Content-Security-Policy"] == del_servidor["Content-Security-Policy"].replace(
        "frame-ancestors 'none'", "frame-ancestors 'self'")
    assert de_flujo["X-Frame-Options"] == '"SAMEORIGIN" always;'
    for nombre in set(del_servidor) - {"Content-Security-Policy", "X-Frame-Options"}:
        assert de_flujo[nombre] == del_servidor[nombre], nombre
    # El mismo proxy que «location /».
    assert [d for d in flujo if not d.startswith("add_header ")] == raiz
    # Nadie mas se deja enmarcar.
    for cabecera, directivas in bloques:
        if cabecera != "location = /flujo":
            texto = " ".join(directivas)
            assert "frame-ancestors 'self'" not in texto and "SAMEORIGIN" not in texto, cabecera
