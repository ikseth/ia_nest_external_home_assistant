# Decision 0002: catalogo cerrado por tipo de entidad, servidor MCP local al core

Fecha: 2026-11-06
Estado: propuesta (catalogo decidido por el usuario, meta H09P13; el resto, por
defecto del disenador, a reconciliar en la revision)

Depende de: decision 0001 (genesis), `core ADR 0053` (`tool_contracts` por MCP,
core `v0.5.0`), `core ADR 0007` (denegar por defecto), meta `H09` (H09P7-H09P10,
H09P13).

## Contexto

El core `v0.5.0` es cliente MCP: abre una sesion por turno con el proveedor que
declara el dominio `domotica`, pide `tools/list`, ofrece al modelo solo lo que
pasa su politica y vuelve a comprobarlo antes de invocar. Una herramienta pasa si
esta en la lista del perfil y no es destructiva: `readOnlyHint: true` o
`destructiveHint: false`; sin anotaciones cuenta como destructiva.

El servidor MCP de Home Assistant (API de Assist, solo entidades expuestas) no
sirve tal cual, visto en produccion con `tools/list`:

- marca sus dos consultas (`GetLiveContext`, `GetDateTime`) de solo lectura, y
  todo lo demas destructivo, tambien encender una luz;
- `HassTurnOn` y `HassTurnOff` actuan sobre cualquier entidad expuesta segun el
  `domain` que elija quien llama: encienden una luz y tambien bloquean una
  cerradura o abren una persiana;
- publica ademas anuncio, temporizadores y los scripts de la casa.

## Decision

### D1. Catalogo cerrado en codigo (meta H09P13)

La capa publica una lista fija de herramientas propias. Cada una llama a UNA
herramienta de Home Assistant con el tipo de entidad fijado por la capa; el
modelo no puede elegirlo. Lo que no esta en el catalogo no se publica.

| Herramienta | Llama a | Argumentos que acepta | Fijado por la capa | Anotaciones |
|---|---|---|---|---|
| `get_live_context` | `GetLiveContext` | `name`, `area`, `domain` (filtros de Home Assistant) | - | solo lectura |
| `get_date_time` | `GetDateTime` | ninguno | - | solo lectura |
| `light_turn_on` | `HassTurnOn` | `name`, `area`, `floor` | `domain: [light]` | no destructiva |
| `light_turn_off` | `HassTurnOff` | `name`, `area`, `floor` | `domain: [light]` | no destructiva |
| `light_set` | `HassLightSet` | `name`, `area`, `floor`, `brightness` 0-100, `color`, `temperature` | `domain: [light]` | no destructiva |
| `media_pause` | `HassMediaPause` | `name`, `area`, `floor` | `domain: [media_player]` | no destructiva |
| `media_unpause` | `HassMediaUnpause` | `name`, `area`, `floor` | `domain: [media_player]` | no destructiva |
| `media_set_volume` | `HassSetVolume` | `name`, `area`, `floor`, `volume_level` 0-100 | `domain: [media_player]` | no destructiva |
| `climate_set_temperature` | `HassClimateSetTemperature` | `name`, `area`, `floor`, `temperature` | - | no destructiva |
| `fan_set_speed` | `HassFanSetSpeed` | `name`, `area`, `floor`, `percentage` 0-100 | `domain: [fan]` | no destructiva |

Visto en el laboratorio el 2026-11-06: la lectura sin filtro de la casa ocupa
unos 11 KB y no cabe en la ventana de 4096 tokens del modelo de `domotica` (el
turno terminaba sin texto). Por eso `get_live_context` publica los filtros que
ya acepta Home Assistant, y una respuesta de mas de 4000 caracteres no se entrega
truncada, que llevaria a suponer estados: vuelve como `isError` pidiendo repetir
con nombre, area o dominio. Los argumentos de todas las herramientas llevan
descripcion para el modelo.

Que perfil ve cada una NO es de esta capa: son las listas `allow` del dominio en
la configuracion del core (meta H09P9).

### D2. Ante la duda, no se publica

En cada `tools/list` la capa lee las herramientas de Home Assistant y publica una
herramienta del catalogo solo si:

1. la herramienta de Home Assistant existe (por su nombre de intencion, con o sin
   el prefijo que anade Home Assistant, por ejemplo `intent__HassTurnOn`);
2. su esquema de entrada acepta cada argumento que la capa fija (por ejemplo
   `domain`). Si Home Assistant deja de aceptar `domain` en `HassTurnOn`,
   `light_turn_on` desaparece en lugar de encender cualquier cosa.

Una invocacion repite la misma comprobacion; si falla, devuelve un error MCP
(`isError`) sin llamar a Home Assistant. Un argumento que no esta en la tabla se
rechaza (esquema de entrada cerrado).

### D3. Servidor MCP local al core

- Transporte `streamable_http`, el unico del core `v0.5.0`, escuchando por
  defecto en `127.0.0.1`. Se despliega en la misma maquina que el core.
- El core se autentica con un token Bearer (en el core, `auth_env`). Sin token o
  con otro, 401. Aunque escuche en local: otros procesos de la maquina no deben
  poder accionar la casa.
- Hacia Home Assistant, cliente MCP de la API de Assist con el token de un usuario
  no administrador y solo de red local. Una sesion por llamada entrante: sin
  estado entre turnos, como el core.
- Python y la libreria `mcp`, la misma que usa el core.

### D4. Resultados, errores y registro

- El resultado de Home Assistant vuelve tal cual (texto y `isError`). Un fallo de
  red o de autenticacion hacia Home Assistant vuelve como `isError` con un texto
  corto y sin detalles internos; el core lo pasa al modelo como resultado
  (`core ADR 0053`, D3).
- Una linea de registro por llamada: herramienta, argumentos, herramienta de Home
  Assistant, estado, latencia. Nunca tokens.

### D5. Instalacion

`deploy/setup.sh` declarativo, como el del core: entorno virtual, unidad systemd,
fichero de entorno con los dos tokens (fuera del repo), reinicio al actualizar y
verificacion de que el servicio publica el catalogo con el token. La
configuracion efectiva vive en el despliegue; se versiona solo el `.example`.

## Descartado

- Reenviar todas las herramientas de Home Assistant y reclasificarlas por reglas
  (meta H09P13): el modelo elegiria el tipo en `HassTurnOn` y una regla mal
  escrita dejaria pasar una cerradura.
- Llamar a la API REST de servicios de Home Assistant en lugar de su MCP: habria
  que reimplementar la resolucion por nombre y area y el filtro de entidades
  expuestas, que ya hace Assist.
- Un componente dentro de Home Assistant: la capa es del ente, no de la casa, y
  no debe compartir proceso con produccion.

## Impacto de version

`v0.1.0`: primer contrato publico. Contrato: nombres, esquemas de entrada y
anotaciones de las herramientas de D1 (las listas `allow` del core dependen de
los nombres). Depende de `core >=0.5 <0.6`. Quitar o renombrar una herramienta,
o cerrar un argumento, rompe el contrato; anadir una herramienta es MINOR.
