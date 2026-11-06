# ia_nest_external_home_assistant

Estado: semilla (sin codigo ni contrato publico)
Version: - (2026-11-06)

Integracion exterior que ACTUA sobre la casa en nombre del ente IA_NEST
(`core docs/FRONTERAS.md`, seccion `ia_nest_external_*`). Es la primera capa de
esa familia.

## Que hara

Un servicio pequeno, fuera de Home Assistant, que:

- se conecta al servidor MCP de Home Assistant con un usuario no administrador y
  token propio, limitado a las entidades expuestas a los asistentes;
- publica hacia el core, tambien por MCP, una lista de herramientas filtrada y
  clasificada: cada herramienta es de solo lectura, inocua o destructiva segun el
  tipo de entidad a la que va (encender una luz no es lo mismo que "encender" una
  cerradura, que la bloquea);
- no publica lo que no sabe clasificar.

El core decide si y cuando invocar una herramienta, con denegar por defecto y su
politica por perfil (`core ADR 0007`). Esta capa no decide como piensa el ente
(`core ADR 0033`).

## Por que existe como capa aparte

- La clasificacion es logica de Home Assistant y el core no absorbe la logica
  de cada integracion.
- El servidor MCP de Home Assistant no sirve tal cual: marca como destructivas
  casi todas sus herramientas, incluida la lectura de estado, y usa la misma
  herramienta para una luz que para una cerradura.
- No es un componente de Home Assistant (esos viven en `ha-addons`, como la
  integracion de voz) ni parte del borde, que atiende a quien llama al ente desde
  fuera.

Decidido en el hito H09 de `ia_nest_meta` (`docs/plan/hitos/`), pasos H08P3 y
H09P7-H09P10.

Para el orden de lectura y las normas entre capas, ver `AGENTS.md`.
