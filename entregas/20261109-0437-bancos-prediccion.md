# Bancos de /flujo y K121 mira el clic · PREDICCION (escrita antes de medir, rama claude/bancos-flujo sobre main@fdab736)

Lo leido antes de escribir esto: K109-banco.py:43-51 y K112-banco.py:45-75 (DDL a mano); sql/schema.sql:2945-3045 (las
siete orderflow_*; celda, cinta y celda_hora PARTITION BY RANGE (ts)); `grep -nE '(FROM|JOIN)' app/orderflow_lectura.py`
(literales + `FROM {tabla}` en :201 y :1051, que la red de FROM/JOIN literal no ve); entrega 146-D P2-P3.

P1 · los cuatro controles EN LA RAMA, al acabar:
  K109-control  N de N, VERDE (el banco crea orderflow_cinta: la pagina pinta, «listo» deja de ser False).
  K112-control  42 de 42 (+ lo que anada el plantado del paso 3 si va por esta linea): la (S) vuelve a ver el 503.
  K113-control  27 de 27 si lo unico que lo tumbaba era la 1h (B1). NO lo doy por seguro: la 146-D midio en K113 suelto
                otras clases fuera de la 1h (T 15m 892, T ETH 5m 846, VIVO) iguales en rama y main; si siguen, K113-control
                sigue ROJO por ellas y lo digo con su frase, sin tocar el juez.
  K121-control  19 de 19 (los 18 de hoy + el plantado 6, ROJO por el brazo del clic con su frase).
  En main@fdab736 de control: K109 ROJO, K112 32 de 42, K113 ROJO en el bueno, K121 18 de 18 (VERDE: K121 recorre 1m y
  5m, que no leen orderflow_hora_hecha).
P2 · la guarda encuentra MAS de lo que dicen B1 y B2: orderflow_celda_hora (la lee el tramo de horas, :201 con
  {tabla}) falta en los DOS bancos; en K109 ademas orderflow_hora_hecha. data_gap (:499, :1068): NO SE SABE aun si la
  alcanza alguna ruta que K109 sirve; si la alcanza, falta tambien.
Criterio de la guarda: tablas = CREATE TABLE de sql/schema.sql que aparecen como palabra en las cadenas que alcanzan, por
el grafo de nombres del modulo, las funciones que cada banco sirve (sus RUTAS). Plantado: el banco sin hora_hecha -> ROJO
nombrandola.
