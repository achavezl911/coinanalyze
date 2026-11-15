# DATOS A · prediccion, escrita ANTES de tocar nada · 2026-11-15 12:18Z · rama claude/datos-a desde main@9a6156e
Arbol: REPO. De 140 no se lee nada para predecir; lo que sigue sale de los informes F3, F4 y F7 (ramas locales) y no esta medido aun.

- A6 · upsert_liquidations contra base desechable: espero que las pruebas de columna y de lado NULL PASEN ya en main
  (los mutantes I1/I3/I5 sobrevivian por falta de prueba, no porque el codigo este mal). Si una falla, sera la del lado
  que falta (I3: `0` en vez de NULL) o la fila con un lado a cero.
- A7 · delta de la vela y compra/venta en USD del footprint: espero que pasen en main (F7/F2 eran mutantes supervivientes).
  Estas dos (A6, A7) NO tendran «fallaba en main»: su valor es que el mutante muera; lo comprobare plantandolo.
- A1 · 8 h con 80 min ausentes en medio: en main `complete=True`; en la rama `partial` con motivo. Espero que la cobertura
  usable sea el conteo de minutos de la tabla agregada (no hay data_gap de spot/futures_trades).
- A2 · cae del 20 al 56: en main covered_seconds=60; en la rama 24. Espero tocar ws_collector y scalp_collector.
- A3 · un activo mudo con los otros vivos: en main (60, 0, completo); en la rama hueco para ese activo.
- A4 · tabla vacia y sin latido del colector: en main available=True levels=[]; en la rama «sin dato».
- A5 · hora con fichero y minutos sin fila sin cobertura: en main 0.0; en la rama None, y suma de 48/60 marcada.
- A8 · numpy en dev: espero que las ~22 pruebas de anatomia corran; NO SE SABE si pasan (nunca corrieron en CI).
- A9 · job de reposicion desde aggTrades: idempotente, probado con un doble de la REST, sin red y sin 140.
Riesgo que espero: A2 cambia lo que escriben los colectores en 140 -> desplegar con cuidado.
