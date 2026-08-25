#!/bin/bash
# K06  las tablas de visibilidad tienen que seguir ESCRIBIENDO. ROJO hoy: dos pararon
# el 2026-08-20 y nadie se entero. Umbral: 6 h sin escribir es paro.
#
# Las dos columnas son verified_visible_at, que es CUANDO SE ESCRIBIO el certificado.
# Antes esta consulta miraba source_finalized_at en outcome_final, que es cuando se
# finalizo el outcome de origen, no cuando se certifico. Medido el 2026-08-25 justo
# despues de desplegar 5d90ee7: verified_visible_at iba 9 segundos por detras de
# now() -la tabla escribia 500 filas cada 40 s- mientras source_finalized_at seguia
# en el 21-ago porque estaba drenando 206884 outcomes atrasados. Con la columna
# vieja el check decia "parada 116h" de una tabla que estaba escribiendo delante de
# sus narices: medir el avance del atasco no es medir si la tabla escribe.
# Salida 2 = NO MEDIDO. Se comprueba PRIMERO que el canal responde: si no, un error
# de transporte se leeria como "tabla parada", que es una medicion falsa.
set -uo pipefail
B=/srv/coinanalyze/harness
vivo=$("$B/bin/prodsql" "SELECT 'canal_ok'" 2>/dev/null | tr -d ' ' | head -1)
[ "$vivo" = "canal_ok" ] || { echo "NO MEDIDO: prodsql no responde"; exit 2; }
viejas=$("$B/bin/prodsql" "
SELECT 'outcome_final '||round(extract(epoch FROM now()-max(verified_visible_at))/3600)||'h'
  FROM signal_outcome_final_visibility HAVING max(verified_visible_at) < now()-interval '6 hours'
UNION ALL
SELECT 'research_bundle '||round(extract(epoch FROM now()-max(verified_visible_at))/3600)||'h'
  FROM signal_research_bundle_visibility HAVING max(verified_visible_at) < now()-interval '6 hours'
" 2>/dev/null | sed 's/^ *//' | grep -v '^$' | grep -v CORTADO | tr '\n' ' ')
[ -z "${viejas// /}" ] || { echo "paradas: $viejas"; exit 1; }
echo "las tablas de visibilidad escriben dentro de 6 h"
