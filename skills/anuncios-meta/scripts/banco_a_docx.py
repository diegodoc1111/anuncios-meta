"""Convierte el banco (Markdown) en los dos Word que usa Diego:

  1. <nombre>-COMPLETO.docx      → para Diego: con fórmulas, niveles, elementos y duración.
  2. <nombre>-PARA-GRABAR.docx   → para quien graba: instrucciones arriba y, por anuncio, solo quién lo graba,
                                   los ganchos, el cuerpo y el CTA. Sin etiquetas de estrategia.

Uso:  python -X utf8 banco_a_docx.py banco.md [--marca "Clínica Confort"] [--salida carpeta]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

sys.path.insert(0, str(Path(__file__).resolve().parent))
from verificar_banco import mmss, partir  # noqa: E402

INSTRUCCIONES = [
    "Cada anuncio viene separado en GANCHOS, CUERPO y CTA (llamado a la acción).",
    "Graba TODOS los ganchos de cada anuncio, uno por uno: así probamos cuál funciona mejor.",
    "El CUERPO y el CTA se graban una sola vez por anuncio; en edición se pegan detrás de cada gancho.",
    "Di el texto tal cual, mirando a la cámara, como si se lo contaras a una persona.",
    "Graba con buen sonido y buena luz (aro de luz o ventana de frente). Celular en vertical.",
]


def base(titulo: str) -> Document:
    d = Document()
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(11)
    d.add_heading(titulo, level=0)
    return d


def linea(d: Document, etiqueta: str, texto: str, color: RGBColor | None = None) -> None:
    p = d.add_paragraph()
    r = p.add_run(etiqueta + " ")
    r.bold = True
    if color:
        r.font.color.rgb = color
    p.add_run(texto)


def campo(bruto: str, emoji: str) -> str:
    m = re.search(rf"{emoji}[^\n:]*:\**\s*(.+)", bruto)
    return re.sub(r"[*_`]", "", m.group(1)).strip() if m else ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("banco")
    ap.add_argument("--marca", default="")
    ap.add_argument("--salida", default="")
    o = ap.parse_args()
    ruta = Path(o.banco)
    texto = ruta.read_text(encoding="utf-8")
    anuncios = partir(texto)
    if not anuncios:
        print("No encontré anuncios en", ruta)
        return 1
    salida = Path(o.salida) if o.salida else ruta.parent
    salida.mkdir(parents=True, exist_ok=True)
    marca = o.marca or ruta.stem.replace("banco-anuncios-", "").replace("-", " ").title()
    naranja, gris = RGBColor(0xD9, 0x6B, 0x00), RGBColor(0x66, 0x66, 0x66)

    # ── 1. COMPLETO ──
    d = base(f"Banco de anuncios · {marca}")
    cabecera = texto.split("## ANUNCIO")[0]
    for parrafo in cabecera.splitlines():
        t = re.sub(r"[*_`#>|]", "", parrafo).strip()
        if t and not set(t) <= set("-: "):
            d.add_paragraph(t)
    for a in anuncios:
        d.add_heading(f"Anuncio Nº {a['n']} — {a['titulo']}", level=1)
        v = campo(a["bruto"], "🎥")
        if v:
            linea(d, "🎥 Quién lo graba / segundo 0:", v, gris)
        for extra, nombre in (("🎬", "🎬 Texto en pantalla:"), ("⏱️", "⏱️ Open loop:")):
            t = campo(a["bruto"], extra)
            if t:
                linea(d, nombre, t, gris)
        d.add_paragraph().add_run("🪝 GANCHOS").bold = True
        for g in a["ganchos"]:
            linea(d, f"{g['id']} {g['etiqueta']}:", g["texto"])
        q = campo(a["bruto"], "🎯")
        if q:
            linea(d, "🎯 Queda claro:", q, gris)
        if a["elementos"]:
            linea(d, "🧱 Elementos:", a["elementos"], gris)
        linea(d, "[CUERPO]", a["cuerpo"], naranja)
        linea(d, "[CTA]", a["cta"], naranja)
    f1 = salida / f"{ruta.stem}-COMPLETO.docx"
    d.save(f1)

    # ── 2. PARA GRABAR ──
    d = base(f"Anuncios para grabar · {marca}")
    d.add_paragraph().add_run("INSTRUCCIONES").bold = True
    for i in INSTRUCCIONES:
        d.add_paragraph(i, style="List Bullet")
    for a in anuncios:
        corto = re.split(r"\s·\s", a["titulo"])[0]
        d.add_heading(f"Anuncio Nº {a['n']} — {corto}", level=1)
        v = campo(a["bruto"], "🎥")
        if v:
            linea(d, "Quién lo graba:", v, gris)
        d.add_paragraph().add_run("GANCHOS (grabar todos)").bold = True
        for k, g in enumerate(a["ganchos"], 1):
            linea(d, f"Gancho {k}:", g["texto"])
        linea(d, "CUERPO:", a["cuerpo"], naranja)
        linea(d, "CTA:", a["cta"], naranja)
    f2 = salida / f"{ruta.stem}-PARA-GRABAR.docx"
    d.save(f2)
    print(f"{f1}\n{f2}\n{len(anuncios)} anuncios")
    return 0


if __name__ == "__main__":
    sys.exit(main())
