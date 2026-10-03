"""Las entradas · registro de hipotesis de entrada en largo y en corto (campana 135, E1).

Que es y que NO es, para quien llegue aqui sin contexto:

- Es un REGISTRO: en cada cierre de vela de su perfil, el generador apunta, append-only y
  ANTES de saber como acaba, cada cambio de estado de cada plan de entrada (VIGILANDO,
  DISPARADO, SOMBRA, EPISODIO CERRADO SIN DISPARO) con la foto entera de lo que sabia.
- NO es una orden, ni una senal de ejecucion, ni una probabilidad. «Probabilistico» sera una
  FRECUENCIA MEDIDA (E4) sobre DISPARADOS ya resueltos (E3), y hasta n efectiva 30 no se
  publica ningun porcentaje (app/analysis_prompt.py:38, app/breakout.py:1-5, COLA 100-110).
- Las reglas viven en config/entradas/reglamento.json (reglamento.py), no en el codigo.
"""
