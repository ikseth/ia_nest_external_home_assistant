# Instrucciones para agentes de IA en ia_nest_external_home_assistant

Las reglas transversales del ente (texto ASCII, identificadores en ingles
snake_case, citas `<repo> ADR NNNN`, repo publico, modo ciego, regla del
registro) viven en `ia_nest_meta` y no se repiten aqui. Lee antes:

1. `meta docs/CONVENCIONES_TRANSVERSALES.md` y `meta docs/DOCTRINA_MULTI_IA.md`
2. `meta docs/REGISTRO_CAPAS.md` y `meta docs/ARQUITECTURA_DE_CAPAS.md`
3. `meta docs/plan/hitos/cerrados/H09_home_assistant_al_ente.md` (por que existe y que se
   decidio: H09P7-H09P10)
4. `core docs/FRONTERAS.md` (`ia_nest_external_*` y `tool_contracts`),
   `core ADR 0007` (denegar por defecto) y `core ADR 0033` (el exterior no dirige
   el pensar del ente)
5. `README.md` de este repo

Orden entre capas: la hoja de ruta del ente, en `meta docs/plan/HOJA_DE_RUTA.md`
(meta ADR 0014). Los hilos de un hito salen de meta; el plan de este repo lleva
solo su detalle interno.

## Reglas propias de este repo

- **La capa clasifica, el core decide.** Esta capa dice que es cada herramienta;
  si se invoca lo decide el core con su politica.
- **Ante la duda, no se publica.** Una herramienta o entidad que no encaja en una
  clase conocida no llega al core.
- **Nada destructivo** mientras siga aplazado (meta H09P10).
- **Solo entidades expuestas** y usuario no administrador en Home Assistant.
- **Credenciales fuera del repo.** Se versiona solo el `.example`.
- Mientras el repo sea semilla, todo documento nuevo nace `Estado: propuesta`.
