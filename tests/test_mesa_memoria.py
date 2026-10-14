"""La palabra grande de DECIDE dice lo que el sistema SOSTIENE (campana 138).

Medido en 140 antes de escribir la regla (72 h de scalp_signal_snapshot, 2026-10-11/14): la palabra
de una evaluacion cambiaba en el 37 % de las evaluaciones seguidas de BTC, y la mesa refresca cada
15 s. Estos tests cobran la regla declarada en `ai_context.palabra_sostenida`, los cinco plantados
del encargo que se ven sin navegador (a-e) y que lo servido basta para recalcular la palabra y su
edad EXACTAMENTE, con una implementacion de aqui y no la de la ruta.
"""

import random
from datetime import UTC, datetime, timedelta

import pytest

from app import ai_context as A
from app.ai_context import palabra_de_la_decision, palabra_registrada, palabra_sostenida

L, S, N, E = A.MESA_PALABRA_LONG, A.MESA_PALABRA_SHORT, A.MESA_PALABRA_SIN_LADO, A.MESA_PALABRA_NO_EVALUABLE
T0 = datetime(2026, 10, 14, 12, 0, tzinfo=UTC)
PASO = 13.9  # la cadencia del colector


def serie(*tramos, desde=T0):
    """(palabra, cuantas) en orden, a 13.9 s. Devuelve la serie y el instante siguiente."""
    out, t = [], desde
    for palabra, cuantas in tramos:
        for _ in range(cuantas):
            out.append((t, palabra))
            t += timedelta(seconds=PASO)
    return out, t


def sostenida(s, *, instante=None, motivo=None, as_of=None):
    return palabra_sostenida(
        s,
        instante=instante if instante is not None else s[-1][1],
        motivo_instante=motivo,
        as_of=as_of if as_of is not None else s[-1][0] + timedelta(seconds=2),
    )


# --- la regla, recalculada AQUI desde lo servido (no con la funcion de la ruta) ----------------


def recalcula(memoria, palabra_del_instante, as_of):
    """La palabra grande y el inicio de su racha, solo con lo que la respuesta sirve."""
    regla = memoria["regla"]
    ts = [datetime.fromisoformat(t) for t, _ in memoria["serie"]]
    pal = [p for _, p in memoria["serie"]]

    def en(j):
        dentro = [p for t, p in zip(ts, pal, strict=True) if ts[j] - timedelta(seconds=regla["ventana_s"]) < t <= ts[j]]
        if pal[j] == E or len(dentro) < regla["minimo"]:
            return E
        for lado in (L, S):
            if dentro.count(lado) >= regla["umbral"] * len(dentro):
                return lado
        return N

    if palabra_del_instante == E:
        return E, None
    if (as_of - ts[-1]).total_seconds() > regla["frescura_s"]:
        return E, ts[-1] + timedelta(seconds=regla["frescura_s"])
    ahora = en(len(ts) - 1)
    edad = memoria["edad"]
    if edad["al_menos"]:
        return ahora, datetime.fromisoformat(edad["desde"])
    # la evaluacion de antes de la racha dice OTRA cosa, y de la racha en adelante todas dicen la de ahora
    desde = datetime.fromisoformat(edad["desde"])
    j = ts.index(desde)
    assert en(j - 1) != ahora
    assert all(en(k) == ahora for k in range(j, len(ts)))
    return ahora, desde


# --- a · un lado sostenido toda la ventana -----------------------------------------------------


def test_a_un_lado_sostenido_es_ese_lado_con_su_cuenta_y_su_edad():
    s, _ = serie((N, 60), (L, 40))
    m = sostenida(s)
    assert m["value"] == L
    assert m["motivo"] == "LONG en 22 de 22 evaluaciones de 5 min (umbral 60 %)"
    # empezo a decir LONG en la evaluacion LONG numero 14 (el 60 % de 22 es 13.2)
    assert m["edad"]["desde"] == s[60 + 13][0].isoformat()
    assert m["edad"]["antes"]["palabra"] == N and m["edad"]["al_menos"] is False
    assert m["edad"]["frase"].startswith("desde las 12:")
    assert m["edad"]["source_key"] == "mesa.decide.memoria.edad"


def test_a_el_lado_se_dice_aunque_el_instante_diga_otra_cosa():
    """Un lado sostenido SI se dice: la del instante va aparte, en la respuesta, no en la grande."""
    s, _ = serie((S, 30), (N, 1))
    assert sostenida(s, instante=N)["value"] == S


# --- b · oscila en cada evaluacion: no es un lado ----------------------------------------------


def test_b_oscilar_en_cada_evaluacion_no_es_un_lado_y_el_motivo_dice_cuanto():
    s, _ = serie(*[(L, 1), (N, 1)] * 40)
    m = sostenida(s)
    assert m["value"] == N
    assert m["motivo"] == "no sostiene un lado en 5 min: LONG 11 · SHORT 0 · NO OPERAR 11 de 22 (umbral 60 %)"
    assert m["cambios_del_instante"] == 21


def test_b_dos_de_cada_tres_si_lo_sostiene():
    s, _ = serie(*[(S, 2), (N, 1)] * 30)
    assert sostenida(s)["value"] == S


def test_un_parpadeo_de_una_evaluacion_no_mueve_la_grande():
    s, _ = serie((N, 40), (L, 1), (N, 40))
    pasos = [sostenida(s[: k + 1])["value"] for k in range(30, len(s))]
    assert set(pasos) == {N}


# --- c, d · las puertas del INSTANTE mandan sobre la memoria -----------------------------------


@pytest.mark.parametrize(
    "ahora",
    [
        {"quality_score": 60.0, "book_status": "ok"},  # c · la calidad cae AHORA por debajo de 70
        {"quality_score": 100.0, "book_status": "stale"},  # d · el libro deja de estar ok AHORA
    ],
    ids=["c-calidad", "d-libro"],
)
def test_c_d_sostenido_pero_la_puerta_del_instante_cierra(ahora):
    s, _ = serie((L, 60))
    palabra, _clave, motivo = palabra_de_la_decision(
        state="Long Pullback", coverage=90.0, **ahora
    )
    m = sostenida(s, instante=palabra, motivo=motivo)
    assert (m["value"], m["motivo"]) == (E, motivo)
    assert m["edad"]["desde"] is None and "no se sabe desde cuando" in m["edad"]["frase"]
    # y la memoria sigue servida: lo que el sistema sostenia se puede leer
    assert m["ventana"]["cuenta"][L] == 22


# --- e · el colector deja de escribir -----------------------------------------------------------


def test_e_sin_evaluaciones_recientes_no_afirma_nada_y_lo_dice():
    s, fin = serie((L, 60))
    as_of = s[-1][0] + timedelta(seconds=90)
    m = sostenida(s, as_of=as_of)
    assert m["value"] == E
    assert m["motivo"].startswith("el colector no escribe desde hace 90 s")
    assert m["edad"]["desde"] == (s[-1][0] + timedelta(seconds=60)).isoformat()
    # a los 60 s justos todavia ve
    assert sostenida(s, as_of=s[-1][0] + timedelta(seconds=60))["value"] == L


def test_e_sin_ninguna_evaluacion_registrada():
    m = palabra_sostenida([], instante=L, motivo_instante=None, as_of=T0)
    assert m["value"] == E and m["ventana"] is None and m["serie"] == []
    assert "no registro ninguna evaluacion" in m["motivo"]


def test_tras_un_hueco_la_ventana_corta_no_sostiene_nada():
    a, fin = serie((L, 60))
    b, _ = serie((L, 5), desde=fin + timedelta(seconds=400))
    m = sostenida(a + b)
    assert m["value"] == E and m["motivo"].startswith("solo 5 evaluaciones en 5 min (minimo 10)")


def test_la_ultima_evaluacion_no_evaluable_cierra():
    s, _ = serie((L, 60), (E, 1))
    m = sostenida(s, instante=L)
    assert m["value"] == E and m["motivo"].startswith("el registro no evaluo la ultima evaluacion")


# --- lo servido basta para recalcular, exactamente ----------------------------------------------


def test_lo_servido_basta_para_recalcular_la_palabra_y_su_edad():
    azar = random.Random(138)
    for _ in range(60):
        tramos = [(azar.choice([L, S, N, N, E]) if azar.random() < 0.03 else azar.choice([L, S, N]),
                   azar.randint(1, 30)) for _ in range(40)]
        s, _ = serie(*tramos)
        corte = azar.randint(30, len(s) - 1)
        vista = s[: corte + 1]
        as_of = vista[-1][0] + timedelta(seconds=azar.choice([1, 30, 59]))
        m = sostenida(vista, instante=vista[-1][1] if vista[-1][1] != E else L, as_of=as_of)
        palabra, desde = recalcula(m, vista[-1][1] if vista[-1][1] != E else L, as_of)
        assert palabra == m["value"]
        if m["edad"]["desde"] is not None:
            assert desde.isoformat() == m["edad"]["desde"]
            assert m["edad"]["s"] == round((as_of - desde).total_seconds(), 1)


def test_la_busqueda_tiene_tope_y_entonces_dice_al_menos():
    s, _ = serie((N, int((A.MEMORIA_BUSQUEDA_S + A.MEMORIA_VENTANA_S) / PASO) + 50))
    as_of = s[-1][0] + timedelta(seconds=1)
    dentro = [x for x in s if x[0] > as_of - timedelta(seconds=A.MEMORIA_BUSQUEDA_S + A.MEMORIA_VENTANA_S)]
    m = sostenida(dentro, as_of=as_of)
    assert m["value"] == N and m["edad"]["al_menos"] is True
    assert m["edad"]["frase"].startswith("desde antes de las ")


def test_lo_que_mide_C1_es_la_regla_que_la_ruta_sirve():
    """Las cifras de C1 salen de scripts/mide_palabra_grande.py (R1); esto ata ese instrumento a la ruta."""
    import scripts.mide_palabra_grande as M

    azar = random.Random(1381)
    tramos = [(azar.choice([L, S, N, N, E]) if azar.random() < 0.02 else azar.choice([L, S, N]), azar.randint(1, 25))
              for _ in range(300)]
    s, _ = serie(*tramos)
    r1 = M.REGLAS["R1 deslizante 5 min >=60% (ELEGIDA)"]
    distintas, vistas = 0, set()
    for k in range(0, len(s), 7):
        # lo que la ruta ve en as_of es lo registrado hasta la evaluacion k; el instrumento ve lo mismo
        instrumento = M.Serie([t.timestamp() for t, _ in s[: k + 1]], [p for _, p in s[: k + 1]])
        for espera in (2, 59, 61):
            as_of = s[k][0] + timedelta(seconds=espera)
            ruta = sostenida([x for x in s[: k + 1] if x[0] > as_of - timedelta(
                seconds=A.MEMORIA_BUSQUEDA_S + A.MEMORIA_VENTANA_S)], instante=L, as_of=as_of)["value"]
            distintas += ruta != M.grande(instrumento, r1, as_of.timestamp())[0]
            vistas.add(ruta)
    assert distintas == 0 and vistas == {L, S, N, E}


# --- la clasificacion de cada evaluacion registrada es la del instante -------------------------


def test_cada_evaluacion_registrada_se_clasifica_como_la_del_instante():
    import scripts.mide_palabra_grande as M

    assert palabra_registrada("Long Pullback", "ok") == L
    assert palabra_registrada("Short Rejection", "ok") == S
    assert palabra_registrada("No Trade", "ok") == N
    assert palabra_registrada("Long Pullback", "stale") == E  # libro no ok: el registro no evalua
    assert palabra_registrada("Sin datos suficientes", "ok") == E  # ahi va la cobertura < 50
    assert palabra_registrada("Estado que no existe", "ok") == E
    # y el instrumento de C1 clasifica igual, estado a estado y libro a libro
    estados = ["Long Momentum", "Long Pullback", "Short Momentum", "Short Rejection", "No Trade",
               "Sin datos suficientes", "Estado que no existe"]
    for libro in ("ok", "stale", "missing", None):
        assert [palabra_registrada(e, libro) for e in estados] == [M.palabra(e, libro or "NULL") for e in estados]


# --- la ruta: la grande en decide.bias, la del instante aparte ----------------------------------


class _Conn:
    """Un doble sin transaction(): la ruta lo dice en envelope_cut.snapshot y sigue."""

    def __init__(self, filas):
        self.filas = filas

    async def fetch(self, sql, *args):
        assert sql == A.MEMORIA_SQL
        return self.filas


async def _decide(monkeypatch, filas, *, state, quality, book="ok", frame="scalp", as_of=None):
    as_of = as_of or filas[-1]["ts"] + timedelta(seconds=3)

    async def _as_of(conn):
        return as_of

    async def _vacio(*a, **k):
        return {}

    async def _conf(conn, symbol):
        return {"quality_score": quality, "status": "ok", "snapshot_lag_seconds": 5.0}

    monkeypatch.setattr(A, "resolve_matrix_as_of", _as_of)
    monkeypatch.setattr(A, "latest_snapshot", _vacio)
    monkeypatch.setattr(A, "scalp_context", _vacio)
    monkeypatch.setattr(A, "price_barriers", _vacio)
    monkeypatch.setattr(A, "structure_detail", _vacio)
    monkeypatch.setattr(A, "data_confidence_row", _conf)
    monkeypatch.setattr(A, "compute_scalp_summary", lambda ctx: {
        "state": state, "book_status": book, "evidence_coverage_pct": 90.0, "long_score": 60.0,
        "short_score": 20.0, "confidence": "media", "reason": "r"})
    return await A.build_mesa_decide(_Conn(filas), "BTCUSDT_PERP.A", frame=frame)


def _filas(*tramos):
    s, _ = serie(*tramos)
    estado = {L: "Long Pullback", S: "Short Rejection", N: "No Trade"}
    return [{"ts": t, "state": estado[p], "book_status": "ok"} for t, p in s]


async def test_la_ruta_sirve_la_grande_en_bias_y_la_del_instante_aparte(monkeypatch):
    d = (await _decide(monkeypatch, _filas((L, 40)), state="No Trade", quality=100.0))
    assert d["schema_version"] == "mesa.decide.v3"
    dec = d["decide"]
    assert (dec["bias"]["value"], dec["bias"]["source_key"]) == (L, "mesa.decide.memoria")
    assert (dec["instante"]["value"], dec["instante"]["source_key"]) == (N, "operator_read.state")
    assert dec["instante"]["frase"] == "0 cambios en 5 min"
    assert dec["memoria"]["edad"]["frase"].startswith("desde las ")
    # el lado de confirma / invalida sigue a la palabra GRANDE
    assert dec["invalidates"][0]["source_key"] == "operator_read.invalidates_long[0]"


@pytest.mark.parametrize("quality,book", [(60.0, "ok"), (100.0, "stale")], ids=["c-calidad", "d-libro"])
async def test_c_d_por_la_ruta(monkeypatch, quality, book):
    d = await _decide(monkeypatch, _filas((L, 40)), state="Long Pullback", quality=quality, book=book)
    assert d["decide"]["bias"]["value"] == E
    assert d["decide"]["bias"]["motivo"] == d["decide"]["instante"]["motivo"]


async def test_e_por_la_ruta(monkeypatch):
    filas = _filas((L, 40))
    d = await _decide(monkeypatch, filas, state="Long Pullback", quality=100.0,
                      as_of=filas[-1]["ts"] + timedelta(seconds=75))
    assert d["decide"]["bias"]["value"] == E
    assert d["decide"]["bias"]["motivo"].startswith("el colector no escribe desde hace 75 s")


async def test_en_swing_la_memoria_viaja_con_la_lectura_del_scalp(monkeypatch):
    d = await _decide(monkeypatch, _filas((S, 40)), state="No Trade", quality=100.0, frame="swing")
    assert "memoria" not in d["decide"] and "instante" not in d["decide"]
    ls = d["lectura_scalp"]
    assert (ls["bias"]["value"], ls["bias"]["source_key"]) == (S, "mesa.decide.memoria")
    assert ls["instante"]["value"] == N and ls["memoria"]["ventana"]["cuenta"][S] == 22
