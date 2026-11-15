"""A5 (DATOS A, F3-F3): en la extraccion de la anatomia, un minuto sin filas de la cinta era 0.0 aunque nadie
estuviera escuchando ese venue. Ahora es cero solo si orderflow_cobertura certifica que todos los venues de la clase
se oyeron el minuto entero; si no, None. Sin numpy: corre siempre."""
import gzip
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import anatomia_extrae as X  # noqa: E402

from app import anatomia as A  # noqa: E402

DIA, H = "2026-10-21", 4
TODOS = A.VENUES_PERP + A.VENUES_SPOT


def _gz(ruta: Path, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(ruta, "wt") as f:
        f.writelines("\t".join(map(str, x)) + "\n" for x in filas)


def _archivo(tmp_path: Path, cobertura=None) -> Path:
    """Una hora de cinta con BTC en binance_usdm solo los minutos 0-39 (una compra de 100 USD por minuto)."""
    arch = tmp_path / "archivo"
    _gz(arch / "cinta" / DIA / f"orderflow_cinta-20261021T{H:02d}Z.tsv.gz",
        [(f"{DIA} {H:02d}:{m:02d}:01+00", "binance_usdm", "BTC", 100, 1, 100, "t", m) for m in range(40)])
    if cobertura is not None:
        _gz(arch / X.COBERTURA[0] / DIA / f"{X.COBERTURA[1]}-20261021T{H:02d}Z.tsv.gz",
            [(f"{DIA} {H:02d}:{m:02d}:00+00", v, s, seg, 0, 0, 0, 0, "t", f"{DIA} 05:00:00+00")
             for (m, v, s), seg in cobertura.items()])
    return arch


def _col(d, s, m, c):
    return d.m[s][H * 60 + m][X.COL[c]]


def test_sin_cobertura_un_minuto_sin_filas_no_es_cero(tmp_path):
    d = X.Dia(_archivo(tmp_path), DIA).corre()

    assert _col(d, "ETH", 10, "dp") is None          # main: 0.0 (ETH no tiene ni una fila en la hora)
    assert _col(d, "BTC", 45, "dp") is None          # BTC sin filas desde el 40
    assert _col(d, "BTC", 10, "vol_spot") is None    # ningun spot oido
    assert _col(d, "BTC", 45, "vol_ref") is None
    assert (_col(d, "BTC", 10, "dp"), _col(d, "BTC", 10, "np")) == (100.0, 1)   # lo oido se queda
    assert _col(d, "BTC", 10, "vol_ref") == 100.0
    assert d.sin_cert == {"BTC": 60, "ETH": 60, "SOL": 60}


def test_con_cobertura_entera_el_minuto_sin_filas_es_cero(tmp_path):
    cob = {(m, v, "BTC"): 60 for m in range(40, 60) for v in TODOS}
    cob[(50, "bybit_linear", "BTC")] = 30            # un venue perp que se oyo medio minuto
    cob.update({(0, v, "ETH"): 60 for v in TODOS})
    d = X.Dia(_archivo(tmp_path, cob), DIA).corre()

    assert (_col(d, "BTC", 45, "dp"), _col(d, "BTC", 45, "ds"), _col(d, "BTC", 45, "vol_ref")) == (0.0, 0.0, 0.0)
    assert _col(d, "BTC", 50, "dp") is None          # perp no certificado
    assert _col(d, "BTC", 50, "ds") == 0.0           # spot si
    assert _col(d, "BTC", 50, "vol_ref") == 0.0      # binance_usdm si se oyo entero
    assert _col(d, "ETH", 0, "dp") == 0.0 and _col(d, "ETH", 1, "dp") is None
    assert d.sin_cert["BTC"] == 40 + 1               # 0-39 sin spot oido, y el 50


def test_extrae_cuenta_los_minutos_sin_certificar(tmp_path):
    hu = X.extrae(_archivo(tmp_path), tmp_path / "salida", desde=DIA, log=lambda *a: None)
    assert hu["minutos_flujo_sin_certificar"] == {"BTC": 60, "ETH": 60, "SOL": 60}


def test_la_suma_de_48_de_60_minutos_lo_dice():
    v = [1.0] * 48 + [None] * 12
    assert A.suma_ventana_n(v) == (48.0, 48)         # suma, y cuantos minutos la sostienen
    assert A.suma_ventana(v) == 48.0                 # la de siempre no cambia
    assert A.suma_ventana_n([1.0] * 47 + [None] * 13) == (None, 47)
