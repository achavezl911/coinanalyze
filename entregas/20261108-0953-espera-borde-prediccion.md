# espera-borde · prediccion (escrita ANTES de medir, sobre main@aa84195)

Sujeto: tests/test_entradas_espera.py::test_a_c_d_... (el brazo del borde: SOL llega a 207.5 s del
reglamento, el ultimo intento de v2 es 210 s; a ESCALA 10 son 0.25 s reales de margen).
Carga: 4 procesos python en bucle ocupado, nice 0, en los 4 nucleos de 143 (carga de fondo previa
de 143 a las 09:53Z: load average 3.39, que NO controlo).

P1 · con el test de main y esa carga, N = 12: fallan entre 1 y 4 (prediccion central 2), todos en
     la asercion de a (`_fallos_a` ... SOL incompleto 14 de 15 / SOMBRA datos). Si fallan 0, subo a
     8 procesos ocupados y lo digo.
P2 · el fichero entero sin carga: el despues tarda como mucho un 20 % mas que el antes (el arreglo
     solo repite en premisa rota, que sin carga no deberia pasar: prediccion +0-5 %).
