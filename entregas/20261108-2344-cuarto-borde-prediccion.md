# CUARTO-BORDE · criterio escrito ANTES de medir (sobre main@0f73414, rama claude/cuarto-borde)

Commiteado antes del paso 1. Nada de lo de abajo esta medido todavia.

P1 · EL BORDE CON EL TEST DE MAIN. tests/test_entradas_espera.py::test_una_vela_reevaluada_no_registra_dos_veces,
  copia congelada de 0f73414, N = 10 arranques contra UN mismo cambio de cuarto, cada uno a un desfase distinto antes del
  borde (0.25 a 6 s, procesos ya importados que esperan al instante). Control: los mismos 10 desfases a mitad del cuarto.
  Prediccion: fallan 4 de 10 en el borde (los que cogen T antes del cambio y registran despues), 0 de 10 en el control.
  Si 0 de 10 en el borde: NO SE SABE si el fallo existe a esta escala de tiempos; se dice y se sigue.

P2 · LOS USOS DE _ahora_T (15 llamadas: 6 en test_entradas_espera.py, 9 en test_entradas_registro_postgres.py).
  Prediccion: cambio 6 (espera: la reevaluada y las dos de test_f; registro: el gemelo a tiempo de «tardio», los dos
  DISPARADOS de «dos vivos» y «de punta a punta», todos con un DISPARADO juzgado contra tope 900) y dejo 9.
