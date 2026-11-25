"""K122-esquema lee el schema.sql de ESQUEMA R1 (V-04): las ordenes envueltas en esquema_ddl($ddl$...$ddl$).

Antes, `ddl()` casaba el CREATE INDEX DENTRO del literal y `_sentencia` leia `$ddl$);`: el `)` dejaba el nivel en -1, el
`;` no contaba y se paraba con «sentencia sin `;`» (5 de las 10 tablas de los bancos; K112-control rc=2).
La referencia: lo que daba el lector de main@b8655df con schema@6c5b193 (antes de ESQUEMA R1) + el indice de IND R2.
"""

import importlib.util
import pathlib

import pytest

RAIZ = pathlib.Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("k122_esquema", RAIZ / "harness" / "checks" / "K122-esquema.py")
esq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(esq)

# las de K109-banco y K112-banco (TABLAS_OF) y las de /libro
TABLAS = ("libro_cobertura", "libro_foto", "libro_honda", "orderflow_celda", "orderflow_celda_hora", "orderflow_cinta",
          "orderflow_cobertura", "orderflow_grande", "orderflow_hora_hecha", "orderflow_paso")
# schema@c4eab57 (IND R2) anade `orderflow_cinta_liq_lado_ts_idx`: sus 2 lineas, tras los indices de orderflow_cinta. Lo
# demas es la referencia de 6c5b193 sin tocar un byte: `git show 9fe0e9a:tests/fixtures/k122_ddl_6c5b193.sql | diff -
# tests/fixtures/k122_ddl_c4eab57.sql` da solo `100a101,102`. Un indice nuevo en estas 10 tablas la vuelve a mover.
REFERENCIA = (RAIZ / "tests" / "fixtures" / "k122_ddl_c4eab57.sql").read_text(encoding="utf-8")


def _ddl(tablas):
    try:
        return esq.ddl(tablas)
    except SystemExit as exc:  # el lector se para con SystemExit: aqui es un fallo con su motivo, no una salida
        pytest.fail(f"ddl{tablas} se paro: {exc}")


def test_ddl_de_las_diez_tablas_igual_que_con_el_esquema_de_antes():
    assert _ddl(TABLAS) == REFERENCIA


@pytest.mark.parametrize("tabla", TABLAS)
def test_ddl_por_tabla_igual_que_con_el_esquema_de_antes(tabla):
    """Tabla a tabla, para que el fallo nombre la tabla: el trozo de la referencia que es suyo."""
    trozo = _ddl((tabla,))
    assert trozo.startswith(f"CREATE TABLE IF NOT EXISTS {tabla} ")
    assert trozo in REFERENCIA


def test_las_envueltas_salen_desenvueltas():
    """Los indices envueltos (los que rompian) salen como orden suelta con su `;`, sin `$ddl$` ni `SELECT`."""
    for t in ("libro_cobertura", "orderflow_cinta", "orderflow_cobertura", "orderflow_grande", "orderflow_hora_hecha"):
        d = _ddl((t,))
        assert "$ddl$" not in d and "esquema_ddl" not in d
        assert any(x.startswith("CREATE INDEX IF NOT EXISTS ") and x.endswith(";") for x in d.splitlines())


def test_orden_envuelta_con_superada_por_y_comillas_de_dolar(tmp_path):
    sql = tmp_path / "schema.sql"
    sql.write_text(
        "CREATE TABLE IF NOT EXISTS t_x (\n    a text DEFAULT $q$x;)y$q$,\n    b int\n);\n"
        "SELECT esquema_ddl($ddl$CREATE INDEX IF NOT EXISTS t_x_a_idx ON t_x (a)$ddl$);\n"
        "SELECT esquema_ddl($e$ALTER TABLE t_x ADD COLUMN IF NOT EXISTS c int CHECK (c > 0)$e$, 't_x_c');\n",
        encoding="utf-8")
    assert esq.ddl(("t_x",), sql) == (
        "CREATE TABLE IF NOT EXISTS t_x (\n    a text DEFAULT $q$x;)y$q$,\n    b int\n);\n"
        "CREATE INDEX IF NOT EXISTS t_x_a_idx ON t_x (a);\n"
        "ALTER TABLE t_x ADD COLUMN IF NOT EXISTS c int CHECK (c > 0);\n")


def test_envuelta_sin_cerrar_se_para_diciendolo(tmp_path):
    sql = tmp_path / "schema.sql"
    sql.write_text("CREATE TABLE IF NOT EXISTS t_x (a int);\nSELECT esquema_ddl($ddl$CREATE INDEX t_x_i ON t_x (a));\n",
                   encoding="utf-8")
    with pytest.raises(SystemExit, match="sin cerrar"):
        esq.ddl(("t_x",), sql)
