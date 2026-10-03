# Impacto · `app/entradas/ruta.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

3 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_reglamento`](#-reglamento) | 286 | 1 | **0** | 0 | **1** |
| [`_resumen`](#-resumen) | 117 | 1 | **0** | 0 | **1** |
| [`construir`](#construir) | 158 | 1 | **0** | 0 | **1** |

## _reglamento

`app/entradas/ruta.py:286` · clave completa `app.entradas.ruta._reglamento`

**Radio exacto: 1 rutas** de 74 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _resumen

`app/entradas/ruta.py:117` · clave completa `app.entradas.ruta._resumen`

**Radio exacto: 1 rutas** de 74 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## construir

`app/entradas/ruta.py:158` · clave completa `app.entradas.ruta.construir`

**Radio exacto: 1 rutas** de 74 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 1 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

