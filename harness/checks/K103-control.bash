#!/bin/bash
# K103-control · ¿ve la red una huerfana, y SOLO cuando la hay?
#
#     bash harness/checks/K103-control.bash
#
# POR QUE ESTE CONTROL, Y QUE VARIABLE DECIDE (A57). Lo que decide el veredicto de K103 es
# UNA cosa: que exista o no la fila PADRE. Todo lo demas -el nombre de la tabla, el tamano,
# el esquema- no decide nada. Asi que los sujetos difieren EN ESA: el plantado y su gemelo
# son la MISMA base sembrada igual, y entre los dos solo cambia si el padre esta.
#
# Y la primera version de K103 la suspendio: imprimia `convalidated::text` y comparaba
# contra "t", pero psql escribe `true`. Las 4 FK de produccion caian en el cubo «no
# condena» y el check daba VERDE con 80/24/17/7 en pantalla. El brazo A2 es el que lo cobra.
#
# LOS BRAZOS
#   A  plantado: una huerfana bajo FK VALIDADA        -> CONDENA, rc=1, con nombre y cuenta
#   B  GEMELO: la misma base con el padre puesto      -> PASA, rc=0
#   C  la huerfana vive en una PARTICION              -> CONDENA por la FK de primer nivel.
#      Sin este brazo, el alcance declarado («las copias por particion no se juzgan porque
#      las cubre la suya») seria una frase sin medir.
#   D  FK compuesta con huerfana                      -> CONDENA (produccion tiene 0: aqui
#      se prueba que la primera que entre no pasa de largo)
#   E  FK NOT VALID con huerfana                      -> se NOMBRA y NO condena, rc=0
#   F  el canal no puede ni leer el catalogo          -> NO MEDIDO rc=2, nunca VERDE
#   G  una base SIN NINGUNA FK                        -> NO MEDIDO rc=2: no juzgo nada
#   H  una tabla BLOQUEADA por otra sesion            -> esa FK sale NOMBRADA como no contada,
#      y como SI hay condenas contadas el veredicto sigue siendo ROJO. Una laguna no borra un
#      hecho, y un conteo que no pudo correr no es un «sin huerfanas».
#
# NO LLEVA .sh A PROPOSITO: bin/verify globea checks/*.sh.
set -uo pipefail
ORIG=${REPO:-/srv/coinanalyze/repo}
CHK="$ORIG/harness/checks/K103-la-fk-que-promete-y-no-cumple.sh"
[ -r "$CHK" ] || { echo "NO MEDIDO: no encuentro el check en $CHK"; exit 2; }
command -v psql >/dev/null || { echo "NO MEDIDO: no hay psql en esta maquina"; exit 2; }

SUC="k103_ctl_sucia_$$"; LIM="k103_ctl_limpia_$$"; VAC="k103_ctl_sinfk_$$"
limpia() { psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $SUC" -c "DROP DATABASE IF EXISTS $LIM" \
                                   -c "DROP DATABASE IF EXISTS $VAC" >/dev/null 2>&1; }
[ "${K103_CONTROL_GUARDA:-0}" = "1" ] || trap limpia EXIT
fallos=0; pasan=0
comprueba() { if [ "$2" = si ]; then pasan=$((pasan+1)); printf '  [ok   ] %-68s\n' "$1"
              else fallos=$((fallos+1)); printf '  [FALLA] %-68s\n' "$1"; fi; }

# EL ESCENARIO, igual en las dos bases. Cinco familias a proposito: simple, particionada,
# compuesta, NOT VALID, y una tabla hija cuya columna admite NULL (una fila con NULL NO esta
# sujeta a la FK -MATCH SIMPLE- y no puede contar como huerfana en ninguna de las dos).
siembra() {
  psql -X -q -v ON_ERROR_STOP=1 -d "$1" >/dev/null 2>&1 <<'SQL'
CREATE TABLE padre (id int PRIMARY KEY, dia date NOT NULL);
INSERT INTO padre SELECT i, '2026-08-29'::date FROM generate_series(1,20) i;

CREATE TABLE hija (id int PRIMARY KEY, padre_id int REFERENCES padre(id));
INSERT INTO hija SELECT i, i FROM generate_series(1,20) i;
INSERT INTO hija VALUES (999, NULL);

CREATE TABLE trozos (id int, padre_id int, dia date NOT NULL,
                     PRIMARY KEY (id, dia),
                     FOREIGN KEY (padre_id) REFERENCES padre(id)) PARTITION BY RANGE (dia);
CREATE TABLE trozos_p20260828 PARTITION OF trozos FOR VALUES FROM ('2026-08-28') TO ('2026-08-29');
CREATE TABLE trozos_p20260829 PARTITION OF trozos FOR VALUES FROM ('2026-08-29') TO ('2026-08-30');
INSERT INTO trozos SELECT i, i, '2026-08-28'::date FROM generate_series(1,10) i;
INSERT INTO trozos SELECT i, i, '2026-08-29'::date FROM generate_series(11,20) i;

CREATE TABLE padre2 (a int, b int, PRIMARY KEY (a,b));
INSERT INTO padre2 SELECT i, i*2 FROM generate_series(1,20) i;
CREATE TABLE hija2 (id int PRIMARY KEY, a int, b int,
                    FOREIGN KEY (a,b) REFERENCES padre2(a,b));
INSERT INTO hija2 SELECT i, i, i*2 FROM generate_series(1,20) i;

CREATE TABLE padre3 (id int PRIMARY KEY);
INSERT INTO padre3 SELECT i FROM generate_series(1,20) i;
CREATE TABLE hija3 (id int PRIMARY KEY, padre_id int);
INSERT INTO hija3 SELECT i, i FROM generate_series(1,20) i;
ALTER TABLE hija3 ADD CONSTRAINT hija3_sin_validar FOREIGN KEY (padre_id) REFERENCES padre3(id) NOT VALID;
SQL
}

psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $SUC" -c "CREATE DATABASE $SUC" >/dev/null 2>&1
psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $LIM" -c "CREATE DATABASE $LIM" >/dev/null 2>&1
siembra "$SUC"; siembra "$LIM"

# LA MUTACION, Y SOLO EN LA SUCIA: se van filas PADRE sin que nadie toque a las hijas. Es el
# fenomeno de produccion reproducido, no simulado: `session_replication_role='replica'` apaga
# los disparadores de la FK, asi que las hijas quedan huerfanas y las FK siguen VALIDADAS.
# LA CUENTA, ESCRITA ANTES DE CORRER Y CORREGIDA POR EL BRAZO 0. La primera version de este
# control decia «3 en hija» y son 4: borrar al padre 15 tambien deja huerfana a la hija 15,
# no solo a la fila de `trozos`. El brazo 0 la cobro antes de que la cifra mala viajara a los
# demas brazos, que es exactamente para lo que esta.
#   padre 1,2,3  -> hija 1,2,3   y trozos (1,2,3 viven en p20260828)
#   padre 15     -> hija 15      y trozos (15 vive en p20260829)
#   = hija 4 · trozos 4 (3 en una particion y 1 en la otra) · hija2 2 · TOTAL 10 en 3 FK
psql -X -q -v ON_ERROR_STOP=1 -d "$SUC" >/dev/null 2>&1 <<'SQL'
SET session_replication_role='replica';
DELETE FROM padre  WHERE id IN (1,2,3);          -- 3 en hija y 3 en trozos_p20260828
DELETE FROM padre  WHERE id = 15;                -- 1 en hija y 1 en trozos_p20260829
DELETE FROM padre2 WHERE a IN (4,5);             -- 2 huerfanas en hija2 (compuesta)
DELETE FROM padre3 WHERE id IN (6,7,8,9);        -- 4 bajo la NOT VALID: no condenan
SQL
# QUE EL PLANTADO EXISTE, CONTADO FUERA DEL CHECK. Si esto no cuadra, lo que sigue no mide.
pl_hija=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM hija c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE p.id=c.padre_id)" 2>/dev/null)
pl_troz=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM trozos c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE p.id=c.padre_id)" 2>/dev/null)
pl_comp=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM hija2 c WHERE c.a IS NOT NULL AND c.b IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre2 p WHERE p.a=c.a AND p.b=c.b)" 2>/dev/null)
pl_nov=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM hija3 c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre3 p WHERE p.id=c.padre_id)" 2>/dev/null)
gem=$(psql -X -A -t -d "$LIM" -c "SELECT (SELECT count(*) FROM hija c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE p.id=c.padre_id)) + (SELECT count(*) FROM trozos c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE p.id=c.padre_id)) + (SELECT count(*) FROM hija2 c WHERE c.a IS NOT NULL AND c.b IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre2 p WHERE p.a=c.a AND p.b=c.b))" 2>/dev/null)

corre() { OUT=$(env K103_SUJETO=local K103_BASE="$1" ${2:+K103_TIMEOUT_MS=$2} \
                    timeout -k 5 180 bash "$CHK" 2>&1); RC=$?; }

echo "K103-control · sujeto: $CHK"
echo
echo "0 · el plantado y el gemelo existen, contados FUERA del check"
comprueba "0a la sucia: 4 huerfanas en hija (dio $pl_hija)"        "$([ "$pl_hija" = 4 ] && echo si || echo no)"
comprueba "0b la sucia: 4 en trozos, repartidas en DOS particiones (dio $pl_troz)" "$([ "$pl_troz" = 4 ] && echo si || echo no)"
pl_t28=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM trozos_p20260828 c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE p.id=c.padre_id)" 2>/dev/null)
pl_t29=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM trozos_p20260829 c WHERE c.padre_id IS NOT NULL AND NOT EXISTS (SELECT 1 FROM padre p WHERE p.id=c.padre_id)" 2>/dev/null)
comprueba "0b2 y en las DOS: 3 en p20260828 y 1 en p20260829 (dio $pl_t28 y $pl_t29)" \
  "$([ "$pl_t28" = 3 ] && [ "$pl_t29" = 1 ] && echo si || echo no)"
comprueba "0c la sucia: 2 bajo la COMPUESTA (dio $pl_comp)"        "$([ "$pl_comp" = 2 ] && echo si || echo no)"
comprueba "0d la sucia: 4 bajo la NOT VALID (dio $pl_nov)"         "$([ "$pl_nov" = 4 ] && echo si || echo no)"
comprueba "0e el GEMELO esta limpio: 0 huerfanas bajo las validadas (dio $gem)" "$([ "$gem" = 0 ] && echo si || echo no)"

echo
echo "A · PLANTADO · la copia con huerfanas: CONDENA con nombre y cuenta"
corre "$SUC"
comprueba "A1 condena, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
# EL ANCLA AL FIN DE LINEA NO ES ADORNO. Sin el, estos tres brazos pasaban con el defecto del
# booleano delante: la version mala imprimia el mismo nombre y la misma cuenta, pero en el cubo
# «DECLARADAS y NO condenan», cuya linea termina en «(NO VALIDADA: no condena)». Medido contra
# la version defectuosa: A2, C1 y D1 pasaban POR LA RAZON EQUIVOCADA (x1-tmp/c131/16-...).
comprueba "A2 nombra hija_padre_id_fkey con su 4, y como CONDENA" \
  "$(printf '%s' "$OUT" | grep -qE 'hija_padre_id_fkey +public\.hija +4 *$' && echo si || echo no)"
comprueba "A3 dice el TOTAL de filas huerfanas bajo FK validadas: 10" \
  "$(printf '%s' "$OUT" | grep -q 'HUERFANAS: 10 filas hijas sin padre bajo 3 FK VALIDADA' && echo si || echo no)"
comprueba "A4 la fila con padre_id NULL NO cuenta (seria 5 en vez de 4)" \
  "$(printf '%s' "$OUT" | grep -qE 'hija_padre_id_fkey +public\.hija +5' && echo no || echo si)"

echo
echo "C · la huerfana que vive en una PARTICION la ve la FK de primer nivel"
comprueba "C1 nombra la FK de trozos con su 4 (las dos particiones a la vez), y como CONDENA" \
  "$(printf '%s' "$OUT" | grep -qE 'trozos_padre_id_fkey +public\.trozos +4 *$' && echo si || echo no)"
comprueba "C2 y NO cuenta las copias por particion como FK aparte" \
  "$(printf '%s' "$OUT" | grep -q 'son copias por particion, cubiertas por la suya' && echo si || echo no)"

echo
echo "D · la FK COMPUESTA tambien se juzga, con sus dos columnas"
comprueba "D1 nombra hija2_a_b_fkey con su 2, y como CONDENA" \
  "$(printf '%s' "$OUT" | grep -qE 'hija2_a_b_fkey +public\.hija2 +2 *$' && echo si || echo no)"
comprueba "D2 y el censo dice que hay 1 compuesta" \
  "$(printf '%s' "$OUT" | grep -q 'compuestas: 1' && echo si || echo no)"

echo
echo "E · la NOT VALID se NOMBRA y NO condena"
comprueba "E1 sale en el cubo de las declaradas, con su 4" \
  "$(printf '%s' "$OUT" | grep -qE 'hija3_sin_validar +public\.hija3 +4 \(NO VALIDADA' && echo si || echo no)"
comprueba "E2 y NO entra en el total de las validadas (10, no 14)" \
  "$(printf '%s' "$OUT" | grep -q 'HUERFANAS: 14 ' && echo no || echo si)"

echo
echo "B · GEMELO · la copia limpia PASA"
corre "$LIM"
comprueba "B1 rc=0 (rc=$RC)" "$([ "$RC" = 0 ] && echo si || echo no)"
comprueba "B2 y lo dice contando: 0 filas hijas sin padre" \
  "$(printf '%s' "$OUT" | grep -q 'cumplen: 0 filas hijas sin padre' && echo si || echo no)"
comprueba "B3 no nombra ninguna FK como huerfana" \
  "$(printf '%s' "$OUT" | grep -q 'HUERFANAS:' && echo no || echo si)"
comprueba "B4 la NOT VALID limpia tampoco sale declarada" \
  "$(printf '%s' "$OUT" | grep -q 'hija3_sin_validar' && echo no || echo si)"

echo
echo "F · si el canal no puede ni leer el CATALOGO, NO MEDIDO · nunca VERDE"
corre "$SUC" 1
comprueba "F1 rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "F2 y dice que lo que fallo fue el censo de FK, no la cuenta" \
  "$(printf '%s' "$OUT" | grep -q 'no devolvio el censo de FK' && echo si || echo no)"

echo
echo "G · una base SIN NINGUNA FK no es un VERDE: no se juzgo nada"
psql -X -q -d postgres -c "DROP DATABASE IF EXISTS $VAC" -c "CREATE DATABASE $VAC" >/dev/null 2>&1
psql -X -q -d "$VAC" -c "CREATE TABLE sola (id int PRIMARY KEY)" >/dev/null 2>&1
corre "$VAC"
comprueba "G1 rc=2 (rc=$RC)" "$([ "$RC" = 2 ] && echo si || echo no)"
comprueba "G2 y lo dice: ninguna FK de primer nivel que juzgar" \
  "$(printf '%s' "$OUT" | grep -q 'ninguna FK de primer nivel que juzgar' && echo si || echo no)"

echo
echo "H · una tabla que no se puede CONTAR sale nombrada, y no borra las condenas que si se contaron"
# El bloqueo lo pone OTRA sesion: `LOCK TABLE hija IN ACCESS EXCLUSIVE MODE` dentro de una
# transaccion abierta. El conteo de esa FK choca con el `statement_timeout`; los demas pasan.
# Es la unica forma honesta de que falle UNA sentencia y no todas: con el tope a 1 ms falla
# ya el catalogo (brazo F) y no se llega a probar esta mitad.
psql -X -q -d "$SUC" -c "BEGIN; LOCK TABLE hija IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(45);" >/dev/null 2>&1 &
PIDLOCK=$!
sleep 2
tiene=$(psql -X -A -t -d "$SUC" -c "SELECT count(*) FROM pg_locks l JOIN pg_class c ON c.oid=l.relation WHERE c.relname='hija' AND l.mode='AccessExclusiveLock'" 2>/dev/null)
comprueba "H0 el bloqueo esta puesto de verdad (locks=$tiene)" "$([ "${tiene:-0}" -ge 1 ] && echo si || echo no)"
corre "$SUC" 1500
kill "$PIDLOCK" 2>/dev/null
wait "$PIDLOCK" 2>/dev/null
comprueba "H1 sigue siendo ROJO, rc=1 (rc=$RC)" "$([ "$RC" = 1 ] && echo si || echo no)"
comprueba "H2 y NOMBRA la FK que no se pudo contar" \
  "$(printf '%s' "$OUT" | grep -q 'NO SE PUDIERON CONTAR.*hija_padre_id_fkey' && echo si || echo no)"
comprueba "H3 y las otras dos condenas siguen ahi (trozos y la compuesta)" \
  "$(printf '%s' "$OUT" | grep -q 'trozos_padre_id_fkey' && printf '%s' "$OUT" | grep -q 'hija2_a_b_fkey' && echo si || echo no)"
comprueba "H4 y la que no se conto NO cuenta como 0 en el total (6, no 10)" \
  "$(printf '%s' "$OUT" | grep -q 'HUERFANAS: 6 filas' && echo si || echo no)"

echo
total=$((pasan+fallos))
echo "$pasan de $total pasan · $fallos fallan"
[ "$fallos" -eq 0 ] || exit 1
exit 0
