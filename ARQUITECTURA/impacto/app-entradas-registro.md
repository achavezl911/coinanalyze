# Impacto · `app/entradas/registro.py`

> Generado por `harness/bin/arquitectura`. No editar a mano.

9 funciones de este fichero alcanzan alguna ruta. **Tocar cualquiera de ellas puede cambiar las rutas que se listan.**

El radio POR TABLA va con **dos numeros**: `k=0` es lo que la funcion escribe ella misma (**exacto**), y `k<=2` sube por los llamadores (**cota superior declarada**). Nunca uno solo.

| funcion | linea | por llamada | tabla k=0 | tabla k<=2 (cota) | total exacto |
|---|---|---|---|---|---|
| [`_argumentos`](#-argumentos) | 164 | 0 | **0** | 2 ↑ | **0** |
| [`cargar_previos`](#cargar-previos) | 127 | 0 | **0** | 2 ↑ | **0** |
| [`como_sombra_tardia`](#como-sombra-tardia) | 175 | 0 | **0** | 2 ↑ | **0** |
| [`filas_esperadas`](#filas-esperadas) | 54 | 0 | **0** | 2 ↑ | **0** |
| [`insertar`](#insertar) | 180 | 0 | **2** | 2 | **2** |
| [`latir`](#latir) | 219 | 0 | **2** | 2 | **2** |
| [`registrar_reglamento`](#registrar-reglamento) | 66 | 0 | **2** | 2 | **2** |
| [`ultimo_tick`](#ultimo-tick) | 233 | 0 | **0** | 2 ↑ | **0** |
| [`ventana_previos`](#ventana-previos) | 112 | 0 | **0** | 2 ↑ | **0** |

## _argumentos

`app/entradas/registro.py:164` · clave completa `app.entradas.registro._argumentos`

**Radio exacto: 0 rutas** de 88 · **cota superior: 2** (mas ancha)

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

## cargar_previos

`app/entradas/registro.py:127` · clave completa `app.entradas.registro.cargar_previos`

**Radio exacto: 0 rutas** de 88 · **cota superior: 2** (mas ancha)

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

## como_sombra_tardia

`app/entradas/registro.py:175` · clave completa `app.entradas.registro.como_sombra_tardia`

**Radio exacto: 0 rutas** de 88 · **cota superior: 2** (mas ancha)

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

## filas_esperadas

`app/entradas/registro.py:54` · clave completa `app.entradas.registro.filas_esperadas`

**Radio exacto: 0 rutas** de 88 · **cota superior: 2** (mas ancha)

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
- `entrada_reglamento` — la escribe `app.entradas.registro.registrar_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## insertar

`app/entradas/registro.py:180` · clave completa `app.entradas.registro.insertar`

**Radio exacto: 2 rutas** de 88 · **cota superior: 2** (igual al exacto)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 2 rutas · **exacto**

Escribe **ella misma**: `entrada_registro`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k<=2 — 2 rutas · **cota superior**

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

## latir

`app/entradas/registro.py:219` · clave completa `app.entradas.registro.latir`

**Radio exacto: 2 rutas** de 88 · **cota superior: 2** (igual al exacto)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 2 rutas · **exacto**

Escribe **ella misma**: `entrada_latido`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k<=2 — 2 rutas · **cota superior**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_latido` — la escribe `app.entradas.registro.latir`
- `entrada_reglamento` — la escribe `app.entradas.registro.registrar_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 4 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## registrar_reglamento

`app/entradas/registro.py:66` · clave completa `app.entradas.registro.registrar_reglamento`

**Radio exacto: 2 rutas** de 88 · **cota superior: 2** (igual al exacto)

### Por llamada — 0 rutas

La ruta **ejecuta** esta funcion. Es exacto: o esta en su cierre o no esta.

_ninguna ruta la ejecuta._

### Por tabla · k=0 — 2 rutas · **exacto**

Escribe **ella misma**: `entrada_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

### Por tabla · k<=2 — 2 rutas · **cota superior**

Ella o alguien que la llama hasta k=2 escribe:

- `entrada_latido` — la escribe `app.entradas.registro.latir`
- `entrada_reglamento` — la escribe `app.entradas.registro.registrar_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ultimo_tick

`app/entradas/registro.py:233` · clave completa `app.entradas.registro.ultimo_tick`

**Radio exacto: 0 rutas** de 88 · **cota superior: 2** (mas ancha)

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
- `entrada_reglamento` — la escribe `app.entradas.registro.registrar_reglamento`

Y esas tablas las leen:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

**2 rutas se enteran SOLO por el dato**, sin
ejecutar nada de esta funcion. Son las que un grafo de llamadas no ve:

- [`/api/entradas`](../rutas/api-entradas.md)
- [`/api/mesa/entradas`](../rutas/api-mesa-entradas.md)

<sub>k=0 es exacto. La cota k<=2 sube por 2 llamadores y **no es una lista de afectadas**: es un techo. Lo que este mas arriba de k=2 no se afirma en ninguno de los dos.</sub>

## ventana_previos

`app/entradas/registro.py:112` · clave completa `app.entradas.registro.ventana_previos`

**Radio exacto: 0 rutas** de 88 · **cota superior: 2** (mas ancha)

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

