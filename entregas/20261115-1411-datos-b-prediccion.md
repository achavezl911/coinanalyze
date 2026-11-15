# DATOS B · prediccion, escrita ANTES de tocar codigo · rama claude/datos-b sobre main@9a6156e

Arbol: repo de 143 (lectura) y 140 solo leido (`bin/prod`). Cifras de la serie de 143 `harness/estado/healthz-serie.jsonl`.

## B3 · recuperador (va primero)
- Hoy, con la fuente doblada de fable-f6: A ([60,420), 6 h justas) y C (41 min) se recuperan; B (361 min), D (dos huecos, el
  segundo cruza la rejilla de 6 h) y E (480 min) NO se piden nunca: `_pendientes_en` solo cuenta huecos ENTEROS dentro de la
  ventana y un hueco que la cruza da 0. Espero ver ese ROJO en el test antes del arreglo: B, D y E con `pedido_a_la_fuente` vacio.
- Tras el arreglo (solape en vez de inclusion + un reconcile por hueco entero al final): los cinco `recovered`, cero filas
  `unrecoverable`, y la segunda corrida seguida pide 0 ventanas.
- Fuente muda: 0 archivados, el hueco sigue `unresolved` (el recuperador no pasa `source_response_buckets`).
- Riesgo que preveo: el reconcile por hueco entero, con `omitir_ya_declarados`, no debe apuntar filas nuevas si falta parte.

## B1 · humo del despliegue
- Hoy el humo da por bueno un healthz 200 con status «degraded» (solo mira el codigo HTTP). Espero que el test con dobles
  (colector caido) NO revierta con el codigo de main: ese es su ROJO.
- Riesgo medido ANTES: en 3 dias de serie hay 392 muestras «degraded» de ~4320 (9 %); 353 son `daily` en «error» por
  `lock timeout` durante su ciclo. Un humo que exija «ok» al primer intento revertiria despliegues sanos. Por eso: «error»
  SOLO cuenta si es POSTERIOR al reinicio; «degraded» y latidos anteriores al reinicio se esperan hasta 450 s (el mismo
  tope que `update.sh`). Prediccion: con eso, el falso revert queda en lo que tarde daily en dar «ok» tras arrancar; si
  daily cae en «lock timeout» despues del reinicio, revierte, y eso es lo que pide B1. NO SE SABE la tasa real hasta
  desplegar.

## B2 · procedencia y venv
- Espero que el test con dobles muestre que hoy un sha cualquiera con su suma se instala, y que el pip corre como root.
- Tras el arreglo: sha distinto de origin/main en GitHub -> se niega; GitHub inalcanzable -> se niega (falla cerrado).
- 140 alcanza `api.github.com` (medido hoy: 200). NO SE SABE si `codeload.github.com` responde igual de rapido.

## B4
- `.claude/settings.json` solo declara ganchos de graphify de la cuenta devops: espero que nada del arnes lo necesite.
- No hay unidad «diaria» en deploy/143: lo que root ejecuta del arbol es el cron de capta-healthz y coinalyze-libretas
  (cada 5 min). Las llevo a la copia congelada.

## Suite
- Espero la suite verde salvo los fallos que ya trae main; los que salgan se comparan con main antes de culparme.
