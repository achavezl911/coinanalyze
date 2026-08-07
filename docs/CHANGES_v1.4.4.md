# Coinalyze v1.4.4 — Wyckoff automático y auditoría de v1.4.3

## Wyckoff automático

- Reutiliza las cinco pruebas del validador manual de rangos; no crea un segundo criterio.
- Busca automáticamente ventanas de 40 a 365 sesiones y finales entre 0 y 30 días atrás.
- Propone bordes robustos con el percentil 5 de mínimos y el percentil 95 de máximos, y después
  exige horizontalidad, contención, rotación, visitas a ambos bordes y volatilidad no expansiva.
- Clasifica el balance como compatible con acumulación, compatible con distribución o neutral.
  El score combina CVD spot, delta de futuros, volumen por dirección, progreso del precio y
  springs/upthrusts. Es evidencia explicable, no una probabilidad.
- Publica fase B/C/D/E como hipótesis trazable, confirmaciones long/short e invalidación práctica.
- Añade modo `Wyckoff 1D` a la gráfica de precio con soporte, mitad, resistencia y marcadores de
  spring/upthrust. El modo intradía de 5 minutos permanece disponible.

## Defecto corregido durante la auditoría

El estimador de ruptura incluía el empuje actualmente abierto dentro de `prior_attempts`. El
corpus histórico sólo cuenta intentos anteriores, por lo que esa diferencia movía el escenario
en vivo al estrato equivocado. Los intentos abiertos ahora se marcan y se excluyen de ese conteo.

## Verificación

- 211 pruebas automatizadas.
- `ruff check app tests scripts` limpio.
- `node --check static/app.js` limpio.
- Sintaxis de scripts Bash validada.
- Evaluación previa al despliegue contra la base viva: BTC, ETH y SOL produjeron rangos válidos
  sin excepciones, con el número de pruebas y la cobertura visibles.
