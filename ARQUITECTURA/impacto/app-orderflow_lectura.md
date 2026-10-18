# Impacto · `app/orderflow_lectura.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

3 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`activo_de`](#activo-de) | 72 | 1 | **0** | 0 | **1** |
| [`pasos`](#pasos) | 97 | 1 | **0** | 0 | **1** |
| [`texto`](#texto) | 50 | 1 | **0** | 0 | **1** |

## activo_de

`app/orderflow_lectura.py:72` · clave completa `app.orderflow_lectura.activo_de`

**Radio exacto: 1 rutas** de 92 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/libro/ultimo`](../rutas/api-libro-ultimo.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 16 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## pasos

`app/orderflow_lectura.py:97` · clave completa `app.orderflow_lectura.pasos`

**Radio exacto: 1 rutas** de 92 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/libro/ultimo`](../rutas/api-libro-ultimo.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 12 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## texto

`app/orderflow_lectura.py:50` · clave completa `app.orderflow_lectura.texto`

**Radio exacto: 1 rutas** de 92 · **cota superior: 1** (igual al exacto)

### Por llamada — 1 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/libro/ultimo`](../rutas/api-libro-ultimo.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 0 rutas · **cota superior**

_ni ella ni sus llamadores hasta k=2 escriben ninguna tabla._

<sub>k=0 es exacto. La cota k<=2 sube por 28 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

