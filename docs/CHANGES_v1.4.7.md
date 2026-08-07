# Coinalyze v1.4.7 — flujo ejecutado y reacción del precio

## Problema

El panel diario usaba `Acumulación` y `Distribución` para clasificar el signo de una única
sesión. El CVD solo observa órdenes agresivas ejecutadas; no observa el inventario de los
participantes ni las órdenes límite históricas que absorbieron esas ejecuciones. La etiqueta
podía hacer creer que venta neta y soporte eran incompatibles.

## Cambio

- `/api/daily` separa las cuatro combinaciones reales de signo entre spot y futuros.
- `price_response` declara si la agresión conjunta tuvo seguimiento en el precio o quedó sin
  avance. La interfaz usa “posible defensa/oferta” porque una sesión aislada no confirma
  absorción.
- La tabla sustituye los diferenciales de escalas incompatibles por esa interpretación.
- El gráfico de 24 sesiones normaliza cada pata contra su propio máximo visible.
- La nota metodológica declara el reloj NYSE y la diferencia entre agresión e inventario.

Los campos `cvd_diff_usd` y `cvd_diff_2v_usd` permanecen en la API para auditoría y
compatibilidad, pero dejan de ser una columna operativa.
