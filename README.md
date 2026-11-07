# ia_nest_external_home_assistant

Estado: propuesta
Version: v0.1.0 en preparacion (2026-11-06)

Servicio MCP local que presenta al core un catalogo cerrado de acciones de Home
Assistant. La capa clasifica; el core decide si ofrece o invoca una herramienta
segun su politica (`core ADR 0007`, `core ADR 0053`).

## Catalogo

El contrato publico de v0.1.0 es la tabla D1 de la [decision
0002](docs/decision_records/0002-catalogo-cerrado-por-tipo-de-entidad.md). Cada
entrada tiene un esquema cerrado y, cuando procede, fija el tipo de entidad
antes de llamar a Assist. Por ejemplo, `light_turn_on` siempre envia
`domain: ["light"]`; no existe un `HassTurnOn` generico.

En cada `tools/list` y antes de cada llamada, la capa comprueba que Assist
publica la intencion y acepta los argumentos fijados. Si no, no publica ni
invoca la herramienta. Home Assistant caido produce una lista vacia.

## Scripts de la casa

Ademas del catalogo, un despliegue puede declarar scripts propios de su hogar en un
fichero JSON (`IANEST_EXTERNAL_HA_SCRIPTS_FILE`), con esquema cerrado y marca obligatoria
([decision 0003](docs/decision_records/0003-scripts-de-la-casa-en-configuracion.md)).
Lo que no esta declarado no se publica.

## Instalacion y configuracion

Se requiere Python >=3.13. Para desarrollo:

```bash
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
```

El servicio lee estos valores del entorno:

- `IANEST_EXTERNAL_HA_URL`: base de Home Assistant; el codigo anade
  `/api/mcp/assist`.
- `IANEST_EXTERNAL_HA_TOKEN_FILE`: fichero con el token del usuario no
  administrador de Home Assistant.
- `IANEST_EXTERNAL_HA_CORE_TOKEN_FILE`: fichero con el token Bearer que debe
  presentar el core. Es obligatorio para arrancar.
- `IANEST_EXTERNAL_HA_SCRIPTS_FILE`: opcional, scripts declarados.
- `IANEST_EXTERNAL_HA_TIMEOUT_S`: segundos por operacion; por defecto `8` y
  siempre menor que `10`.

Arranque manual:

```bash
ianest-external-ha --host 127.0.0.1 --port 8770
```

El endpoint MCP es `http://127.0.0.1:8770/mcp`. Toda solicitud necesita
`Authorization: Bearer <token-del-core>`; la comparacion es en tiempo
constante. Los registros son una linea JSON por llamada, sin tokens.

Para systemd, editar fuera del repositorio una copia de
`deploy/ejemplo.setup.conf` y ejecutar como root:

```bash
deploy/setup.sh --config /ruta/privada/external_ha.setup.conf
```

El instalador crea el usuario de servicio, copia los tokens con modo 600,
instala desde este arbol, activa y reinicia
`ianest-external-ha.service`. Despues verifica que el servicio se reinicio, que
un `tools/list` autenticado incluye `get_live_context` y que la misma ruta sin
Bearer responde 401.

## Pruebas

```bash
.venv/bin/pytest -q
```

Las pruebas arrancan una falsificacion local de Assist a partir de los esquemas
necesarios de la respuesta real de referencia. No contactan Home Assistant ni
el core reales.
