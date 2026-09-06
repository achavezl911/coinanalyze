#!/usr/bin/env bash
# K16-control · ¿el criterio nuevo caza lo que dice y NO caza de mas?
#
# El criterio viejo -«declarada 2 veces»- era trivialmente comprobable y llevaba 26 de 27
# pasadas en ROJO sin que nadie actuara. El nuevo enrojece por DIVERGENCIA y cuenta la
# duplicacion identica, asi que hace falta probar las dos mitades: que un cuerpo distinto
# enrojece, y que uno identico NO. Sin la segunda, "verde" solo diria que hoy no hay nada.
#
# El fixture es un schema.sql GENERADO aqui, no el real: asi los casos no caducan cuando
# alguien toque el fichero de verdad.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K16-particiones.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }

DIR=$(mktemp -d) || exit 2
[ "${K16_CONTROL_GUARDA:-0}" = "1" ] || trap 'rm -rf "$DIR"' EXIT
mkdir -p "$DIR/bin" "$DIR/t/sql" "$DIR/t/tests"

# --- la base de mentira. Contesta lo que 140 contestaria con todo en orden. -------------
cat > "$DIR/bin/prodsql" <<'PY'
#!/bin/sh
case "$1" in
  *count\(\)*|*"count(*)"*) printf '%s\n' "${K16C_VIVAS:-1}" ;;
  *pg_get_functiondef*)     printf '%s\n' "${K16C_CUERPO:-futures_trades_realtime spot_trades_realtime orderbook_snapshot liquidations_realtime scalp_signal_snapshot}" ;;
esac
PY
chmod +x "$DIR/bin/prodsql" 2>/dev/null || { echo "NO MEDIDO: no puedo dar el bit de ejecucion"; exit 2; }
cat > "$DIR/bin/prodsql-mudo" <<'PY'
#!/bin/sh
exit 3
PY
chmod +x "$DIR/bin/prodsql-mudo"

# --- el schema.sql de mentira ----------------------------------------------------------
# RELLENO: el check exige >=50 objetos CREATE antes de creerse un cero, asi que el fixture
# tiene que parecer un esquema y no un juguete. Es el brazo que impide que "0 duplicados"
# y "el analizador dejo de reconocer CREATE" se confundan.
relleno() { for i in $(seq 1 60); do echo "CREATE TABLE tabla_$i (id int);"; done; }

fn() {  # <nombre> <marca>
  cat <<EOF
CREATE OR REPLACE FUNCTION $1()
RETURNS void
LANGUAGE plpgsql
AS \$\$
BEGIN
    PERFORM 1 FROM cosa WHERE marca = '$2';
END
\$\$;
EOF
}

monta() {  # <fichero> <contenido extra...>
  { relleno; cat; } > "$DIR/t/sql/schema.sql"
  echo "import app.partitioning" > "$DIR/t/tests/test_p.py"
}

fallos=0; pasan=0
caso() {  # <nombre> <rc esperado> <patron>
  local nombre="$1" esperado="$2" patron="$3" psql="${4:-$DIR/bin/prodsql}"
  local out rc
  out=$(REPO="$DIR/t" K16_PRODSQL="$psql" bash "$CHK" 2>&1); rc=$?
  local ok=1
  [ "$rc" = "$esperado" ] || ok=0
  # HUELLA POSITIVA: el rc solo no basta, el mensaje tiene que demostrar que miro lo que crees.
  if [ -n "$patron" ] && ! printf '%s' "$out" | grep -qE "$patron"; then ok=0; fi
  if [ "$ok" = 1 ]; then
    pasan=$((pasan+1)); printf '  [ok   ] %-52s rc=%s\n' "$nombre" "$rc"
  else
    fallos=$((fallos+1))
    printf '  [FALLA] %-52s rc=%s (esperaba %s, patron /%s/)\n      %s\n' \
      "$nombre" "$rc" "$esperado" "$patron" "$(printf '%s' "$out" | head -2 | tr '\n' ' ' | cut -c1-160)"
  fi
}

echo "K16-control · sujeto: $CHK"
echo

echo "NEGATIVO · el check NO puede enrojecer cuando no hay divergencia"
monta <<EOF
$(fn f_unica X)
EOF
caso "N1 esquema sin duplicados" 0 "ningun objeto de schema.sql diverge"

# N2 · EL CASO QUE JUSTIFICA TODO EL CAMBIO: duplicado con el MISMO cuerpo. No enrojece, se
# CUENTA. Con el criterio viejo esto era ROJO, y es el rojo que llevaba 26 de 27 pasadas.
monta <<EOF
$(fn f_dos X)
$(fn f_dos X)
EOF
caso "N2 duplicado IDENTICO: se cuenta, no enrojece" 0 "1 objeto\(s\) declarados dos veces con el MISMO cuerpo"

# N3 · el mismo cuerpo repartido en OTRAS lineas tampoco es divergencia. Es el fallo que
# cometi al medirlo: comparar linea a linea decia "3 de 5 distintas" y las tres diferencias
# eran saltos de linea.
monta <<EOF
$(fn f_fmt X)
CREATE OR REPLACE FUNCTION f_fmt()
RETURNS void LANGUAGE plpgsql AS \$\$
BEGIN
    PERFORM 1
    FROM cosa
    WHERE marca = 'X';
END
\$\$;
EOF
caso "N3 mismo cuerpo, saltos de linea distintos: no diverge" 0 "MISMO cuerpo"

# N4 · literales adyacentes pegados contra el literal entero: PostgreSQL los concatena, asi
# que son el MISMO texto. Es exactamente la unica diferencia real entre las dos
# declaraciones de ensure_temporal_partitions en el schema.sql de verdad.
monta <<EOF
CREATE OR REPLACE FUNCTION f_lit()
RETURNS void LANGUAGE plpgsql AS \$\$
BEGIN
    EXECUTE format('CREATE TABLE %I.%I '
                   'FOR VALUES (%L)', a, b, c);
END
\$\$;
CREATE OR REPLACE FUNCTION f_lit()
RETURNS void LANGUAGE plpgsql AS \$\$
BEGIN
    EXECUTE format('CREATE TABLE %I.%I FOR VALUES (%L)', a, b, c);
END
\$\$;
EOF
caso "N4 literales adyacentes contra literal entero: no diverge" 0 "MISMO cuerpo"

# N5 · EL CASO QUE ME FALTABA Y ME COSTO UN FALSO. Mismo cuerpo con las LINEAS EN BLANCO en
# otro sitio. La primera version del comparador juntaba lineas ya colapsadas con " ".join,
# y una linea vacia dejaba dos espacios seguidos: daba DOS divergencias donde hay UNA. El
# control de entonces no lo cazaba porque ningun fixture movia los blancos.
monta <<EOF
CREATE OR REPLACE FUNCTION f_blanco()
RETURNS void LANGUAGE plpgsql AS \$\$
BEGIN

    PERFORM 1 FROM cosa WHERE marca = 'X';

END
\$\$;
CREATE OR REPLACE FUNCTION f_blanco()
RETURNS void LANGUAGE plpgsql AS \$\$
BEGIN
    PERFORM 1 FROM cosa WHERE marca = 'X';
END
\$\$;
EOF
caso "N5 mismo cuerpo, lineas en blanco en otro sitio" 0 "MISMO cuerpo"

echo
echo "REAPLICACION DELIBERADA · la tercera categoria, que nacio de ejercer la puerta 1"
# El par DROP/CREATE TRIGGER de liquidations_realtime tiene el MISMO texto que el de :377 y
# toca OTRA TABLA, porque entre los dos la migracion renombra `liquidations_realtime`.
# Medido: con esas lineas el trigger queda en 6 relaciones, sin ellas en 1. No es deuda.
monta <<EOF
$(fn f_adrede X)
-- REAPLICACION DELIBERADA: aqui el nombre significa otra tabla, ver la migracion.
$(fn f_adrede X)
EOF
caso "A1 duplicado CON motivo escrito: no es deuda" 0 "reaplicacion\(es\) DELIBERADA"

# A2 · ANTI-FANTASMA DEL MARCADOR: sin el motivo, el MISMO fixture vuelve a ser deuda. Sin
# este caso, A1 pasaria igual si el marcador no se leyera nunca.
monta <<EOF
$(fn f_adrede X)
$(fn f_adrede X)
EOF
caso "A2 el mismo, SIN motivo: vuelve a ser deuda" 0 "SIN motivo escrito"

# A3 · el marcador no puede ser un salvoconducto: una redeclaracion DIVERGENTE con el motivo
# escrito sigue siendo ROJO. Escribir "es a proposito" no hace que dos cuerpos distintos
# dejen de pisarse.
monta <<EOF
$(fn f_marcada X)
-- REAPLICACION DELIBERADA: y aun asi los cuerpos no coinciden.
$(fn f_marcada Y)
EOF
caso "A3 divergente CON motivo: sigue siendo ROJO" 1 "cuerpos DISTINTOS"

# A4 · el marcador tiene alcance: 30 lineas arriba. Uno perdido a 60 lineas no vale, o
# cualquier "REAPLICACION DELIBERADA" del fichero eximiria a todo lo de debajo.
monta <<EOF
-- REAPLICACION DELIBERADA: escrito demasiado lejos.
$(for i in $(seq 1 40); do echo "-- relleno $i"; done)
$(fn f_lejos X)
$(fn f_lejos X)
EOF
caso "A4 motivo a 40+ lineas: no exime" 0 "SIN motivo escrito"

echo
echo "POSITIVO · la divergencia SI enrojece"
# P1 · dos cuerpos distintos: el ultimo pisa al primero en silencio. Este es el defecto.
monta <<EOF
$(fn f_div X)
$(fn f_div Y)
EOF
caso "P1 duplicado DIVERGENTE" 1 "cuerpos DISTINTOS"

# P2 · y nombra al objeto, no solo cuenta. Sin esto un ROJO por otra razon contaria como acierto.
caso "P2 el mensaje nombra el objeto divergente" 1 "f_div"

# P3 · un TRIGGER divergente tambien, no solo funciones: los duplicados se DERIVAN del
# fichero y en el schema.sql real hay un trigger entre los cinco.
monta <<EOF
$(fn f_ok X)
CREATE TRIGGER t_div BEFORE INSERT ON a EXECUTE FUNCTION f1();
CREATE TRIGGER t_div AFTER UPDATE ON a EXECUTE FUNCTION f2();
EOF
caso "P3 un TRIGGER divergente tambien cuenta" 1 "t_div"

# P4 · TRES declaraciones del mismo objeto, dos iguales y una distinta: sigue siendo ROJO.
monta <<EOF
$(fn f_tres X)
$(fn f_tres X)
$(fn f_tres Z)
EOF
caso "P4 tres declaraciones, una distinta" 1 "cuerpos DISTINTOS"

echo
echo "ANTI-FANTASMA · lo que no se puede medir es NOMED, jamas VERDE"
# F1 · CERO DUPLICADOS NO ES CERO DEFECTOS si el analizador dejo de reconocer los CREATE.
# Un esquema de 3 lineas no puede dar VERDE por silencio.
monta <<EOF
-- un fichero que el analizador no reconoce
EOF
printf -- '-- nada\n' > "$DIR/t/sql/schema.sql"
caso "F1 el analizador no reconoce CREATE: NOMED" 2 "no esta reconociendolos"

monta <<EOF
$(fn f_unica X)
EOF
caso "F2 la base no responde: NOMED" 2 "prodsql no respondio" "$DIR/bin/prodsql-mudo"

rm -f "$DIR/t/sql/schema.sql"
caso "F3 sin schema.sql: NOMED" 2 "no se puede leer"

echo
echo "LOS OTROS BRAZOS siguen vivos · no los tapo al cambiar el primero"
monta <<EOF
$(fn f_unica X)
EOF
rm -f "$DIR/t/tests/test_p.py"
caso "O1 ningun test importa partitioning" 1 "ningun test importa"

monta <<EOF
$(fn f_unica X)
EOF
K16C_VIVAS=2 caso "O2 en 140 hay 2 funciones" 1 "en 140 hay"
K16C_CUERPO="solo_una_tabla" caso "O3 la funcion viva no gestiona las 5 tablas" 1 "no gestiona"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
