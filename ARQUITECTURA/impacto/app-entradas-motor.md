# Impacto · `app/entradas/motor.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

16 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_avanza`](#-avanza) | 1022 | 0 | **0** | 2 ↑ | **0** |
| [`_nuevo_episodio`](#-nuevo-episodio) | 988 | 0 | **0** | 2 ↑ | **0** |
| [`_ocupaciones`](#-ocupaciones) | 816 | 0 | **0** | 2 ↑ | **0** |
| [`arma`](#arma) | 443 | 0 | **0** | 2 ↑ | **0** |
| [`atr_mediana`](#atr-mediana) | 217 | 0 | **0** | 2 ↑ | **0** |
| [`completa`](#completa) | 212 | 0 | **0** | 2 ↑ | **0** |
| [`construir_zonas`](#construir-zonas) | 282 | 0 | **0** | 2 ↑ | **0** |
| [`de_iso`](#de-iso) | 176 | 0 | **0** | 2 ↑ | **0** |
| [`elegible`](#elegible) | 436 | 0 | **0** | 2 ↑ | **0** |
| [`estructura`](#estructura) | 425 | 0 | **0** | 2 ↑ | **0** |
| [`foto_canonica`](#foto-canonica) | 184 | 0 | **0** | 2 ↑ | **0** |
| [`grupos_por_comun`](#grupos-por-comun) | 253 | 0 | **0** | 2 ↑ | **0** |
| [`incompatibilidades`](#incompatibilidades) | 131 | 0 | **0** | 2 ↑ | **0** |
| [`iso`](#iso) | 171 | 0 | **0** | 2 ↑ | **0** |
| [`paso`](#paso) | 861 | 0 | **0** | 2 ↑ | **0** |
| [`solapan`](#solapan) | 239 | 0 | **0** | 2 ↑ | **0** |

## _avanza

`app/entradas/motor.py:1022` · clave completa `app.entradas.motor._avanza`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## _nuevo_episodio

`app/entradas/motor.py:988` · clave completa `app.entradas.motor._nuevo_episodio`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## _ocupaciones

`app/entradas/motor.py:816` · clave completa `app.entradas.motor._ocupaciones`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## arma

`app/entradas/motor.py:443` · clave completa `app.entradas.motor.arma`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## atr_mediana

`app/entradas/motor.py:217` · clave completa `app.entradas.motor.atr_mediana`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## completa

`app/entradas/motor.py:212` · clave completa `app.entradas.motor.completa`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

<sub>k=0 es exacto. La cota k<=2 sube por 10 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## construir_zonas

`app/entradas/motor.py:282` · clave completa `app.entradas.motor.construir_zonas`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## de_iso

`app/entradas/motor.py:176` · clave completa `app.entradas.motor.de_iso`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

<sub>k=0 es exacto. La cota k<=2 sube por 11 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## elegible

`app/entradas/motor.py:436` · clave completa `app.entradas.motor.elegible`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## estructura

`app/entradas/motor.py:425` · clave completa `app.entradas.motor.estructura`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## foto_canonica

`app/entradas/motor.py:184` · clave completa `app.entradas.motor.foto_canonica`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## grupos_por_comun

`app/entradas/motor.py:253` · clave completa `app.entradas.motor.grupos_por_comun`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## incompatibilidades

`app/entradas/motor.py:131` · clave completa `app.entradas.motor.incompatibilidades`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

## iso

`app/entradas/motor.py:171` · clave completa `app.entradas.motor.iso`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

<sub>k=0 es exacto. La cota k<=2 sube por 22 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## paso

`app/entradas/motor.py:861` · clave completa `app.entradas.motor.paso`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## solapan

`app/entradas/motor.py:239` · clave completa `app.entradas.motor.solapan`

**Radio exacto: 0 rutas** de 75 · **cota superior: 2** (mas ancha)

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

