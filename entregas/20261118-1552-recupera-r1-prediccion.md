# RECUPERA R1 · prediccion (antes de tocar codigo) · rama claude/recupera-r1 desde main@60709d1

Lo que espero medir, escrito antes. Todo en bases desechables (esquema por test, TEST_DATABASE_URL).

R1 · la forma del apagon (hueco ohlcv_1min de 34 h, mas uno anidado de otro detector, dato en la base
en las ultimas ~25 h, fuente doblada con reloj de 24 h):
- EN MAIN: /api/ohlcv (5min) da close=None en TODAS las velas del tramo con dato; el recuperador no
  pide nada (el hueco empieza fuera del reloj) y el hueco sigue 'unresolved'. La prueba nueva cae ahi.
- AQUI: esas velas salen con precio; la parte vieja sigue declarada en data_gaps.declared.
- POR QUE NO BASTA RECONCILIAR: reconcile_cadence_coverage solo recupera una fila con TODOS sus buckets
  (data_gaps.py:631-640); el padre de 34 h nunca los tendra. Hay que partirlo.
- EL ESTADO DEL PADRE LO DICTA K04 (harness/checks/K04-huecos.sh:94-97 y :240-261): 'recovered' esta
  rechazado por escrito, y 'unrecoverable' con method partitioned_by_source_coverage exige hijos que
  TESELEN y NINGUNO abierto. Con hijos anidados de 34 filas, la rejilla de hijos tiene que ser COMUN
  (si cada padre se parte por su cuenta, los hijos se solapan y K04 condena).
- LA PARTE VIEJA: espero ponerla 'unrecoverable' con method provider_horizon_exhausted, la prueba que
  K04 ya re-deriva (ventana pedida vacia + control reciente con filas). Sin control positivo, NO se
  archiva: queda 'unresolved', el padre no se cierra y nada se destapa. Prefiero eso a inventar.
- PREDIGO UN SEGUNDO DEFECTO: blocking_requirement_keys (data_gaps.py:138) bloquea todo 'unrecoverable',
  asi que un padre partido y cerrado SIGUE tapando a sus hijos recuperados. Hay que excluirlo ahi y en
  GAP_ISLANDS_SQL (:169). Sus hijos bloquean por si solos lo que de verdad falta.

R2 · ohlcv_5min (binance, 5min; ingest.py:516 lo detecta) entra en PLANS y en HORIZONTE con 192 h
(suelo de los «8-9 dias» de hechos.tsv:261 y del operador). Prueba: hueco de 34 h de 5min dentro del
reloj, fuente doblada -> recovered y 408 velas en la base. En main: el recuperador no lo pide (0 pedidas).

R3 · una orden `--parte --seco` y luego `--parte`, por gap o por ventana, con systemd-run sin --pipe.

NO SE SABE de antemano: si en 140 el tramo con dato esta COMPLETO (un minuto que falte dentro deja un hijo
abierto y el padre sin cerrar); el modo en seco lo dira.
