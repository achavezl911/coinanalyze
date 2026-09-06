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

# LA MIGRACION INCRUSTADA DE MENTIRA. El check localiza la region buscando el texto del
# fichero de migracion DENTRO de schema.sql, asi que el fixture tiene que traer las dos cosas
# o el check dira NOMED con razon. Se pega al final de cada schema.sql de mentira.
mkdir -p "$DIR/t/sql/migrations"
REGION="BEGIN;
CREATE TABLE zzz_marca_de_region (id int);
COMMIT;"
printf '%s\n' "$REGION" > "$DIR/t/sql/migrations/20260809_temporal_partitioning.sql"

monta() {  # <contenido del schema por stdin>; la region se pega detras
  { relleno; cat; printf '%s\n' "$REGION"; } > "$DIR/t/sql/schema.sql"
  echo "import app.partitioning" > "$DIR/t/tests/test_p.py"
}
# monta_crudo: sin pegar la region. Para el caso que la rompe a proposito.
monta_crudo() {
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
caso "N2 duplicado IDENTICO: se cuenta, no enrojece" 0 "1 objeto\(s\) FUERA de la region declarados dos veces"

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
echo "LA MIGRACION INCRUSTADA · no se mira, y no mirarla tiene que ser comprobable"
# LOS CUATRO CASOS «REAPLICACION DELIBERADA» SE QUITARON EL 2026-09-06. Nacieron de creer que
# el par DROP/CREATE TRIGGER de dentro de la region era una redeclaracion deliberada que habia
# que conservar con un comentario encima. La premisa era falsa: la region ENTERA es
# sql/migrations/20260809_temporal_partitioning.sql copiado byte a byte, y que lo siga siendo
# lo exige un test -MIGRATION.strip() in schema-. Un marcador escrito a mano era, ademas, la
# cita mas debil posible al lado de un fichero del que ser copia.
#
# R1 · UN OBJETO QUE LA REGION REPITE NO CUENTA COMO DUPLICADO. Se mete `zzz_marca_de_region`
# tambien FUERA: el fichero lo declara dos veces, una fuera y otra dentro, y aun asi el check
# tiene que salir limpio. Es exactamente la forma de los cinco que costaron la puerta.
monta <<EOF
CREATE TABLE zzz_marca_de_region (id int);
EOF
caso "R1 un objeto que la region repite no es duplicado" 0 "NO se mira aqui"

# R2 · ANTI-FANTASMA DE LA EXCLUSION. Si la region no esta byte a byte, el check NO puede
# excluirla y NO debe adivinar: NOMED. Sin este caso, R1 pasaria igual si la exclusion se
# tragara el fichero entero, o si no se aplicara nunca y el duplicado no existiera.
# EL BYTE SE CAMBIA POR DENTRO, no al final: anadir texto DETRAS del COMMIT no rompe nada,
# porque `BEGIN;...COMMIT;` sigue siendo subcadena. Lo enseño correr el caso: daba VERDE.
monta_crudo <<EOF
CREATE TABLE zzz_marca_de_region (id int);
BEGIN;
CREATE TABLE zzz_marca_de_regionX (id int);
COMMIT;
EOF
caso "R2 region rota por un byte: NOMED, no VERDE" 2 "ya no contiene la migracion incrustada"

# R3 · y la exclusion no puede ser un colador: un duplicado FUERA de la region sigue
# contandose. Sin esto, excluir "todo" pasaria R1 y R2 igual.
monta <<EOF
$(fn f_fuera X)
$(fn f_fuera X)
EOF
caso "R3 duplicado FUERA de la region: se sigue contando" 0 "FUERA de la region declarados dos veces"

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
# La region SI va: sin ella saltaria antes la guarda de la region y este caso probaria otra
# cosa. Con ella, el fichero tiene UN solo CREATE y cae por el suelo de 50, que es el sujeto.
printf -- '-- un fichero que el analizador casi no reconoce\n%s\n' "$REGION" > "$DIR/t/sql/schema.sql"
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
