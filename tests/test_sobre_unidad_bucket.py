"""El sobre de una serie dice EN QUE UNIDAD habla, y no convierte un NULO en un cero.

POR QUE EXISTE. `/api/whale/delta` respondia `coverage.served_window.complete = true` y
`data_gaps.status = "clean"` mientras una de sus filas publicaba `missing_minutes = 1`. No son
dos afirmaciones contrarias: son dos GRANULARIDADES con la misma palabra -el sobre cuenta CUBOS
y la fila cuenta MINUTOS dentro de su cubo-. Lo que no aguantaba es que la unidad se adivinara.

Y HAY UN TERCER ESTADO. Medido en 140 el 2026-09-10 sobre las 576 filas de
/api/whale/delta?interval=5min: 573 con entero 0, 1 con entero 1, y **2 con NULO** -los dos
cubos mas recientes, todavia llenandose-. Sumar el NULO como cero seria inventar un dato
tranquilizador justo donde menos se sabe, que es el defecto que esto viene a quitar.
"""

from app.api import minutos_de_las_filas


def test_los_tres_estados_se_cuentan_por_separado() -> None:
    filas = [
        {"missing_minutes": 0},
        {"missing_minutes": 0},
        {"missing_minutes": 1},
        {"missing_minutes": 7},
        {"missing_minutes": None},
        {"missing_minutes": None},
    ]
    d = minutos_de_las_filas(filas)
    assert d["unit"] == "bucket"
    assert d["buckets_con_minutos_incompletos"] == 2
    assert d["missing_minutes_total"] == 8
    # EL QUE IMPORTA: los dos NULOS no se han sumado como ceros ni se han perdido.
    assert d["buckets_con_minutos_sin_medir"] == 2


def test_un_NULO_no_es_un_CERO() -> None:
    """El control que distingue este arreglo de no haber hecho nada."""
    ceros = minutos_de_las_filas([{"missing_minutes": 0}, {"missing_minutes": 0}])
    nulos = minutos_de_las_filas([{"missing_minutes": None}, {"missing_minutes": None}])
    assert ceros["buckets_con_minutos_sin_medir"] == 0
    assert nulos["buckets_con_minutos_sin_medir"] == 2
    # y ninguno de los dos inventa minutos ausentes
    assert ceros["missing_minutes_total"] == nulos["missing_minutes_total"] == 0
    assert ceros != nulos, "un cero medido y un no-medido no pueden dar el mismo sobre"


def test_la_unidad_se_dice_aunque_la_serie_no_publique_minutos() -> None:
    """Quien lee no tiene por que saber de antemano en que habla `complete`."""
    d = minutos_de_las_filas([{"bucket": "2026-09-10T00:00:00Z", "whale_delta": 1.0}])
    assert d == {"unit": "bucket"}


def test_complete_sigue_siendo_cosa_de_CUBOS() -> None:
    """Lo que NO se ha cambiado, y se fija para que no se cambie por descuido.

    La otra salida posible era poner `complete` a falso cuando algun cubo declara minutos
    ausentes. Se descarto con una medida: COLA 95 midio que el minuto corto es la firma de CADA
    arranque -45 pares (arranque, simbolo) en 4 dias, los 45 con marca-, asi que `complete`
    seria falso casi siempre y un campo que siempre dice lo mismo no informa.
    """
    d = minutos_de_las_filas([{"missing_minutes": 3}])
    assert "complete" not in d, "esta funcion no toca `complete`: solo anade al lado"
