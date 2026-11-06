# Decision 0001: genesis de la integracion con Home Assistant

Fecha: 2026-11-06

## Decision

Se siembra `ia_nest_external_home_assistant` como semilla documental, sin
codigo ni contrato publico. Su papel (cliente del servidor MCP de Home Assistant
que publica al core herramientas clasificadas), su zona (Exterior) y el contrato
con el core (MCP) estan decididos en el hito H09 de meta (H08P3, H09P7-H09P10);
este repo no los repite.

## Motivo

El tramo 2 de H09 (el ente ve y controla la casa) necesita una capa que traduzca
y clasifique las herramientas de Home Assistant, y el core necesita una peticion
formal de esa capa para abrir `tool_contracts` (`core ADR 0022` lo difiere hasta
tener una herramienta concreta). El usuario crea el repo vacio en GitHub y se
siembra en local.

## Consecuencia

- Fila de la capa en `meta docs/REGISTRO_CAPAS.md` como semilla.
- `external_home_assistant CR-0001` al core, en `meta docs/change_requests/`.
- El diseno interno (como se clasifica cada llamada) se abre en el hilo de H09
  cuando el core haya decidido la forma de `tool_contracts`.
- Sin SemVer ni tag hasta que exista contrato publico.

## Impacto de version

Ninguno: no hay contrato publico.
