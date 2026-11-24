# AUDITOR · regla sellada ANTES de medir (encargo del dueno, seccion 6; su respuesta del 11-23 a la pregunta 4)

Con 60 vidas pareadas, si Opus no supera a DECIDE (el intervalo de la diferencia incluye 0 o es negativo), el dueno evalua apagar la evaluacion de Opus y quedarse con DECIDE y el auditor; la decision final es del dueno.

- Vida pareada: una posicion cerrada cuyo PRIMER veredicto automatico (motivo «posicion nueva») tuvo veredicto de Opus y de DECIDE, los dos con lado (A FAVOR / EN CONTRA) y con pnl. Acierto, para los dos: (pnl > 0) == A FAVOR, la regla de R1. Los /evalua a mano no cuentan.
- Las 60: las PRIMERAS 60 pareadas en orden de cierre (`calidad._pareada`, `muestra[:60]`), no las ultimas ni una semana.
- Diferencia: (b - c) / 60, donde b = las vidas en que acierta solo Opus y c = las que acierta solo DECIDE. Su intervalo al 95 %: el de Wilson de b / (b + c), llevado a (b + c) / 60 · (2w - 1). Sin discordantes, la diferencia es 0 exacto: incluye 0, asi que Opus NO supera.
- Opus supera solo si el limite inferior de ese intervalo es mayor que 0. Se reporta junto a la prueba de signos exacta (dos colas) sobre b y c.
- El informe semanal la imprime con su texto en cuanto hay 60 (`calidad.texto_medicion`, linea «REGLA SELLADA»). Antes de eso dice «n/60 vidas pareadas, sin lectura».
- El operador sella el sha256 de este fichero en hechos al auditar.
