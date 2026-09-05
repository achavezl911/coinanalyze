# ARQUITECTURA · la arquitectura funcional viva

> **Este directorio se REGENERA. No se edita a mano.**
> `harness/bin/arquitectura` lo produce entero desde el AST del arbol, y
> `harness/checks/K88-la-arquitectura-que-miente.sh` se pone ROJO si lo commiteado no
> coincide con una regeneracion fresca, o si hay una ruta en el codigo que aqui no esta.

## Por que existe

Un documento de arquitectura escrito a mano envejece, y **uno que miente es peor que
ninguno, porque la gente se fia**. El caso que lo pago: `compute_snapshot` alimenta
`publish_snapshot`, que alimenta `metrics_snapshot`, que alimenta N rutas. Eso no estaba
escrito en ningun sitio, y un arreglo de dos lineas en `metrics.py` tumbo el snapshot
entero de los tres simbolos durante 24 dias sin que nadie supiera el alcance.

## Las tres capas

| capa | quien la escribe | estado |
|---|---|---|
| **DERIVADA** | el generador, desde el codigo | **viva** — es esto |
| **DECLARADA** | a mano, una vez (pregunta del trader, familia de ventana K43, promesa) | PENDIENTE · F3 |
| **IMPACTO** | el generador, invirtiendo el grafo (`funcion/tabla -> rutas`) | PENDIENTE · F2 |

## Como se lee sin leerlo entero

1. `INDICE.md` — las 68 rutas en una tabla.
2. `rutas/<ruta>.md` — **una ficha por ruta.** Si vas a tocar `/api/setup`, abre
   `rutas/api-setup.md` y nada mas.
3. `derivada.json` — lo mismo para maquinas, y es lo que K88 compara.

## Que sabe y que no sabe

Es analisis **estatico**: ve lo que el AST dice. **No ve** despacho dinamico, SQL
concatenado en tiempo de ejecucion, ni middlewares que reescriban la respuesta. Cada
limite de esos aparece como PENDIENTE **con su motivo** en la ficha de la ruta. Un hueco
declarado es informacion; un hueco rellenado con lo plausible es la averia que este
directorio existe para no repetir.

## Cifras de esta regeneracion

- rutas descubiertas: **68**
- rutas con al menos un campo derivado: **62**
- rutas sin ningun campo derivado (PENDIENTE, con motivo en su ficha): **6**
- funciones alcanzables desde alguna ruta: **308**
- tablas del catalogo `sql/schema.sql`: **40**
- tablas alcanzadas desde alguna ruta: **30**

## Regenerar

```sh
harness/bin/arquitectura            # reescribe ARQUITECTURA/
harness/bin/arquitectura --comprueba  # no escribe; rc=1 si lo commiteado no cuadra
harness/checks/K88-la-arquitectura-que-miente.sh
```

## LOS INSUMOS · que lee el generador, y que pasa si falta

**Regenerar en otra maquina con media copia produce un mapa distinto y K88 lo llama ROJO.**
Medido regenerando desde copias parciales: **sin `static/`, `tests/`, `tools/` y
`README.md` difieren 56 ficheros; sin `harness/checks`, 15.** No es un fallo del check: es
que el mapa describe menos cosas porque ha visto menos.

| insumo | para que | si falta |
|---|---|---|
| `app/**.py` | AST: rutas, campos, llamadas, SQL, constantes | no hay mapa |
| `sql/schema.sql` | catalogo de tablas y columnas; valida que una tabla existe | ninguna tabla se afirma |
| `static/app.js`, `static/index.html` | consumidores: **llamada** desde el panel | toda ruta parece instrumento interno |
| `harness/checks/**` | consumidores: checks que la miden | 5 rutas de `/api/signals/*` salen huerfanas |
| `tests/**`, `tools/**`, `README.md` | consumidores: llamadas y menciones | menos rastro del que hay |
| `ARQUITECTURA/declarada/*.md` | **FUENTE de la capa declarada**; se lee, no se escribe | todas las rutas salen PENDIENTE de declaracion |

Lo que el generador **NO** lee, y es deliberado: la foto de produccion
(`entregas/*-foto-prod-*.json`). No esta versionada, asi que si entrara aqui, regenerar sin
ella daria ROJO por no tener una medicion en vez de por estar mal. Lo observado en
produccion vive en la capa **declarada**, con su fecha y su cita.
