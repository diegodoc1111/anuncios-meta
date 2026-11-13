# Anuncios para Meta con un redactor y un jefe que revisa

Sistema de agentes para Claude Code que escribe guiones de anuncios en video para Meta Ads (Facebook e Instagram).
No es solo una skill: **un agente redacta y otro revisa** antes de que el banco de anuncios te llegue a ti.

Hecho por Diego Osorio ([@soydiegoosorio](https://instagram.com/soydiegoosorio)).

## Qué hace

Le das tu oferta, tu cliente ideal y tu llamado a la acción, y te entrega un banco de anuncios (30 por defecto) con:

- **4 ganchos por anuncio** para probar, cada uno marcado con su fórmula y su ángulo (dolor, sueño o libre).
- **Cuerpo que explica el producto**: qué es, para qué sirve, qué gana la persona y qué le pasa si no lo hace.
- **Idioma de la gente**: problema, dolor, miedo, consecuencia y sueño; sin palabras técnicas.
- **Duración medida por palabras**: cortos (35 s a 1 min), medios (1:00 a 1:30) y largos (1:30 a 2:00).
- **Dos Word**: el completo, con la estrategia, y el limpio para quien graba.

## Cómo trabaja

1. **Brief.** La skill te pregunta el llamado a la acción y arma la ficha del producto y el glosario.
2. **Redactor** (`redactor-anuncios`, Opus). Escribe el banco siguiendo el marco.
3. **Verificador** (`scripts/verificar_banco.py`). Mide con regla: duración, ganchos, ángulos, beneficios, palabras
   técnicas y palabras prohibidas.
4. **Jefe** (`jefe-anuncios`, Fable). Lee el banco con 11 pruebas y devuelve cada anuncio como aprobado, corregir
   (con el arreglo escrito) o rehacer. Máximo dos rondas.
5. **Entrega.** Los dos Word y un resumen corto.

## Instalación

Necesitas [Claude Code](https://claude.com/claude-code) y Python 3 con `python-docx` (`pip install python-docx`).

```bash
git clone https://github.com/diegodoc1111/anuncios-meta
```

Copia las dos carpetas a tu carpeta de Claude:

- `skills/anuncios-meta/` → `~/.claude/skills/anuncios-meta/`
- `agents/redactor-anuncios.md` y `agents/jefe-anuncios.md` → `~/.claude/agents/`

En Windows, `~` es `C:\Users\TU_USUARIO`. Abre una sesión nueva de Claude Code para que cargue los agentes.

## Cómo usarlo

En Claude Code escribe, por ejemplo:

> Hazme un banco de anuncios para Meta de mi servicio de limpieza facial. El llamado a la acción es reservar por
> WhatsApp a 499 pesos.

La skill hace las preguntas que falten, y el redactor y el jefe trabajan solos.

## Qué hay adentro

| Archivo | Para qué |
|---|---|
| `skills/anuncios-meta/SKILL.md` | Las reglas y las 5 fases |
| `skills/anuncios-meta/references/marco-de-diego.md` | El marco: rompe scroll, interés, llamado a la acción |
| `skills/anuncios-meta/references/rubrica-del-jefe.md` | Las 11 pruebas del revisor |
| `skills/anuncios-meta/references/banco-de-ganchos.md` | Fórmulas de gancho y ángulos |
| `skills/anuncios-meta/references/ejemplo-*.md` | Bancos de ejemplo para el tono |
| `skills/anuncios-meta/scripts/` | Verificador y generador de los Word |
| `agents/` | El redactor y el jefe |

Los modelos de cada agente están en la primera parte de su archivo (`model: opus` y `model: fable`). Si tu plan no
tiene alguno, cámbialo ahí.
