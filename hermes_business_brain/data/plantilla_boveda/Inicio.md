---
id: SYS-INICIO
tipo: mapa
estado_editorial: aprobado
sensibilidad: interno
---
# Business Brain of {{EMPRESA_NOMBRE}}

> **Welcome.** Your company develops with Codex; this page is a consultation point, not a form nor a source of truth by itself. Identifier: `{{EMPRESA_ID}}`.

## Start or continue with Codex

1. If this is the first time, use the `iniciar-empresa` flow from the master repository.
2. Describe what business you have and what you want to develop; Codex **retrieves sources before asking you**.
3. Codex retrieves sources and proposes **which notes should exist, which to reuse, and how to link them** before drafting D/X. It uses vNext and K1–K4, without inventing facts or producing empty templates.
4. Consult the [[00_Mapas/Mapa_de_empresa|business map]] and your approved notes; never confuse a draft with a current offer.
5. For another session, read the latest notes in `90_Sistema/Continuidad/` and verify their sources.

## Work views (Obsidian Bases)

- [Offers, products, and consulting](90_Sistema/Vistas/Ofertas.base)
- [Commercial, accounts, and agreements](90_Sistema/Vistas/Comercial.base)
- [Projects and implementations](90_Sistema/Vistas/Proyectos.base)
- [Meetings and sessions](90_Sistema/Vistas/Reuniones_y_sesiones.base)
- [Tasks: table and board](90_Sistema/Vistas/Tareas.base)
- [People and organizations](90_Sistema/Vistas/Personas_y_organizaciones.base)
- [Processes and protocols](90_Sistema/Vistas/Procesos_y_protocolos.base)
- [Research and learnings](90_Sistema/Vistas/Investigacion_y_aprendizajes.base)
- [Sources and authority](90_Sistema/Vistas/Fuentes_y_autoridad.base)
- [Financial and operational indicators](90_Sistema/Vistas/Indicadores.base)
- [Communications](90_Sistema/Vistas/Comunicacion.base)
- [Resources and dependencies](90_Sistema/Vistas/Recursos_y_dependencias.base)

## Dynamic knowledge map (when authorized)

The note-and-relationship network can be browsed with a Markdown view and a derived Canvas, created by Codex after running `mapa-conocimiento` and obtaining authorization to `publicar-mapa` with a backup. The intended path is 00_Mapas/Mapa_Derivado_Conocimiento.md, alongside its .canvas pair. These files are not created automatically and are not a source of truth. The 16 Bases above let you query notes by type and properties.

## Authority, open items, and evidence

- [[90_Sistema/Autoridades|Declared authorities]]
- [[90_Sistema/Pendientes|Pending knowledge]]
- [[90_Sistema/Pruebas_de_recuperacion|Recovery tests]]
- [[00_Mapas/Relaciones_de_conocimiento|Declared typed relationships]]
- [[90_Sistema/Como_usar|Short manual of this vault]]

> **Important:** a YAML property does not limit who can open a note. Do not store secrets or share this vault without reviewing real permissions. The GitHub repository is the software, not the destination for your company's data.
