# Impacto · `app/entradas/papel.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

4 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_pendiente`](#-pendiente) | 63 | 2 | **0** | 0 | **2** |
| [`_sin_resultado`](#-sin-resultado) | 74 | 2 | **0** | 0 | **2** |
| [`_usd`](#-usd) | 59 | 2 | **0** | 0 | **2** |
| [`cuenta`](#cuenta) | 87 | 2 | **0** | 0 | **2** |

## _pendiente

`app/entradas/papel.py:63` · clave completa `app.entradas.papel._pendiente`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _sin_resultado

`app/entradas/papel.py:74` · clave completa `app.entradas.papel._sin_resultado`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _usd

`app/entradas/papel.py:59` · clave completa `app.entradas.papel._usd`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cuenta

`app/entradas/papel.py:87` · clave completa `app.entradas.papel.cuenta`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (igual al exacto)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

