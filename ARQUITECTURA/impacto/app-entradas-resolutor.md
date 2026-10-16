# Impacto · `app/entradas/resolutor.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

12 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_cero`](#-cero) | 429 | 2 | **0** | 0 | **2** |
| [`_cobros`](#-cobros) | 414 | 2 | **0** | 0 | **2** |
| [`_minuto`](#-minuto) | 124 | 2 | **0** | 0 | **2** |
| [`_pata`](#-pata) | 154 | 2 | **0** | 0 | **2** |
| [`_t`](#-t) | 112 | 2 | **0** | 2 ↑ | **2** |
| [`_t23`](#-t23) | 407 | 2 | **0** | 0 | **2** |
| [`cobros_funding`](#cobros-funding) | 144 | 2 | **0** | 2 ↑ | **2** |
| [`entrada_t`](#entrada-t) | 133 | 2 | **0** | 2 ↑ | **2** |
| [`foto_de`](#foto-de) | 128 | 2 | **0** | 0 | **2** |
| [`iso`](#iso) | 120 | 2 | **0** | 0 | **2** |
| [`resolver`](#resolver) | 165 | 2 | **0** | 2 ↑ | **2** |
| [`ventana`](#ventana) | 138 | 2 | **0** | 2 ↑ | **2** |

## _cero

`app/entradas/resolutor.py:429` · clave completa `app.entradas.resolutor._cero`

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

## _cobros

`app/entradas/resolutor.py:414` · clave completa `app.entradas.resolutor._cobros`

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

## _minuto

`app/entradas/resolutor.py:124` · clave completa `app.entradas.resolutor._minuto`

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

## _pata

`app/entradas/resolutor.py:154` · clave completa `app.entradas.resolutor._pata`

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

## _t

`app/entradas/resolutor.py:112` · clave completa `app.entradas.resolutor._t`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (mas ancha)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_resultado` — la escribe `app.entradas.resultados.guardar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 9 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## _t23

`app/entradas/resolutor.py:407` · clave completa `app.entradas.resolutor._t23`

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

## cobros_funding

`app/entradas/resolutor.py:144` · clave completa `app.entradas.resolutor.cobros_funding`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (mas ancha)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_resultado` — la escribe `app.entradas.resultados.guardar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## entrada_t

`app/entradas/resolutor.py:133` · clave completa `app.entradas.resolutor.entrada_t`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (mas ancha)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_resultado` — la escribe `app.entradas.resultados.guardar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## foto_de

`app/entradas/resolutor.py:128` · clave completa `app.entradas.resolutor.foto_de`

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

## iso

`app/entradas/resolutor.py:120` · clave completa `app.entradas.resolutor.iso`

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

<sub>k=0 es exacto. La cota k<=2 sube por 10 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## resolver

`app/entradas/resolutor.py:165` · clave completa `app.entradas.resolutor.resolver`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (mas ancha)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_resultado` — la escribe `app.entradas.resultados.guardar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ventana

`app/entradas/resolutor.py:138` · clave completa `app.entradas.resolutor.ventana`

**Radio exacto: 2 rutas** de 75 · **cota superior: 2** (mas ancha)

### Por llamada — 2 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_resultado` — la escribe `app.entradas.resultados.guardar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

