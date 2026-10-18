# Impacto · `app/entradas/insumos.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

9 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_f`](#-f) | 104 | 0 | **0** | 2 ↑ | **0** |
| [`barras`](#barras) | 146 | 0 | **0** | 2 ↑ | **0** |
| [`cargar`](#cargar) | 222 | 0 | **0** | 2 ↑ | **0** |
| [`flujos`](#flujos) | 186 | 0 | **0** | 2 ↑ | **0** |
| [`libro`](#libro) | 202 | 0 | **0** | 2 ↑ | **0** |
| [`listos`](#listos) | 302 | 0 | **0** | 2 ↑ | **0** |
| [`vela_de_T_completa`](#vela-de-t-completa) | 295 | 0 | **0** | 2 ↑ | **0** |
| [`velas_perfil`](#velas-perfil) | 120 | 0 | **0** | 2 ↑ | **0** |
| [`ventana_velas`](#ventana-velas) | 111 | 0 | **0** | 2 ↑ | **0** |

## _f

`app/entradas/insumos.py:104` · clave completa `app.entradas.insumos._f`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 6 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## barras

`app/entradas/insumos.py:146` · clave completa `app.entradas.insumos.barras`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## cargar

`app/entradas/insumos.py:222` · clave completa `app.entradas.insumos.cargar`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_latido` — la escribe `app.entradas.registro.latir`
- `entrada_registro` — la escribe `app.entradas.registro.insertar`
- `entrada_reglamento` — la escribe `app.entradas.registro.registrar_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 5 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## flujos

`app/entradas/insumos.py:186` · clave completa `app.entradas.insumos.flujos`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## libro

`app/entradas/insumos.py:202` · clave completa `app.entradas.insumos.libro`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## listos

`app/entradas/insumos.py:302` · clave completa `app.entradas.insumos.listos`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_latido` — la escribe `app.entradas.registro.latir`
- `entrada_registro` — la escribe `app.entradas.registro.insertar`
- `entrada_reglamento` — la escribe `app.entradas.registro.registrar_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## vela_de_T_completa

`app/entradas/insumos.py:295` · clave completa `app.entradas.insumos.vela_de_T_completa`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## velas_perfil

`app/entradas/insumos.py:120` · clave completa `app.entradas.insumos.velas_perfil`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ventana_velas

`app/entradas/insumos.py:111` · clave completa `app.entradas.insumos.ventana_velas`

**Radio exacto: 0 rutas** de 90 · **cota superior: 2** (mas ancha)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 0 rutas · **exacto**

_no escribe ninguna tabla ella misma._ Si es una funcion pura, su
impacto por dato viaja por quien la llama: mira la cota de abajo.

### Por tabla · k<=2 — 2 rutas · **cota superior**

**Esta cota es MAS ANCHA que el dato exacto** (2 contra 0). Parte de la diferencia puede entrar por un bucle
de colector que solo comparte llamador, no dato. **Es un techo, no una lista**
**de afectadas.**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_registro` — la escribe `app.entradas.registro.insertar`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 3 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

