# Decision 0003: scripts de la casa declarados en la configuracion del despliegue

Fecha: 2026-11-07
Estado: propuesta (decidido por el usuario, meta H09P23)

Depende de: decision 0002 (catalogo cerrado), meta `H09` (H09P19, H09P23).

## Contexto

Para sustituir al asistente actual de la casa hacen falta sus scripts (por ejemplo,
recomendar y poner algo en la television). Los scripts son de cada hogar, no de Home
Assistant: otro despliegue tendria otros. Home Assistant los publica todos como
destructivos y de mundo abierto, sin distinguir.

## Decision

- La capa gana un tipo generico, "script declarado". El despliegue nombra en un fichero
  JSON (`IANEST_EXTERNAL_HA_SCRIPTS_FILE`, en el instalador `SCRIPTS_SOURCE`) cada script
  que se puede usar: nombre de herramienta, script de Home Assistant, descripcion,
  argumentos con esquema cerrado y marca. Ejemplo en `deploy/ejemplo.scripts.json`.
- Lista cerrada: un script que no esta declarado no se publica, como el resto del
  catalogo. Sin fichero, no hay scripts.
- La marca es obligatoria: cada entrada declara `destructiveHint` de forma explicita;
  sin ella el fichero no es valido y el servicio no arranca. La responsabilidad de la
  marca es de quien despliega; el core sigue aplicando su politica (solo endurece).
- D2 tambien para scripts: se publica solo si Home Assistant tiene ese script
  (`script__<id>`) y acepta cada argumento declarado; se comprueba en cada `tools/list`
  y antes de cada llamada.
- El nombre de herramienta no puede repetir uno del catalogo de la decision 0002.

## Descartado

- Cada script en el codigo del catalogo: cada script seria una version de la capa y el
  repo publico llevaria los nombres y la logica de un hogar concreto.

## Impacto de version

Aditivo para `v0.1.0`, que aun no se ha cortado: el contrato publico es el catalogo de la
decision 0002 mas el formato del fichero de scripts. Que scripts declara un despliegue no
es contrato de la capa.
