# Changelog

## [v0.1.0] - 2026-11-09

Primer contrato publico: servidor MCP local al core con el catalogo cerrado de
Home Assistant (decision 0002) y los scripts de la casa declarados en la
configuracion del despliegue (decision 0003). Depende de `core >=0.5 <0.6`
(`tool_contracts` por MCP, `core ADR 0053`). Validado: 21 tests y tramo 2 del
hito H09 de meta en el laboratorio (estado, control y denegacion por perfil, por
la voz).

### Anadido

- Catalogo cerrado de 10 herramientas con el tipo de entidad fijado por la capa
  y anotaciones MCP (decision 0002, D1).
- Validacion D2 en cada `tools/list` y en cada invocacion: lo que Home Assistant
  no acepta tal cual no se publica ni se llama.
- `get_live_context` con filtros `name`, `area` y `domain`; una respuesta de mas
  de 4000 caracteres vuelve como error en lugar de truncada.
- Scripts de la casa declarados en un fichero JSON del despliegue, cada uno con
  su marca y su esquema cerrado (decision 0003).
- Nota para el modelo en los errores de herramientas con tipo fijado.
- Servidor sin estado en la ruta exacta `/mcp`, autenticado con token Bearer;
  una linea de registro por llamada, sin tokens.
- Instalador `deploy/setup.sh` con unidad systemd y verificacion de
  `tools/list` y de 401.
