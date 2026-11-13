"""Verificador de un banco de anuncios (Markdown con la plantilla de la skill anuncios-meta).

Mide lo que se puede medir con regla, para que el jefe solo gaste criterio en lo que lo necesita:
duración real por palabras, 4 ganchos con llamada, elementos del cuerpo, CTA, palabras prohibidas y la
cobertura del marco de Diego en el banco completo (11 elementos, 3 llamadas, 5 niveles de conciencia).

Uso:
  python -X utf8 verificar_banco.py banco.md [--ciudad "Ciudad de México"] [--cta "agenda tu consulta"]
         [--prohibido "gratis,precio"] [--mezcla "13,10,7"] [--parcial] [--json salida.json]

  --parcial   el archivo es una tanda (no el banco completo): no exige la cobertura del banco.
Sale con código 1 si hay algún ❌.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

PPM = 187  # palabras por minuto, medido con la voz de Diego
MIN_S, MAX_S = 35, 120   # corto 0:35–1:00 · medio 1:00–1:30 · largo 1:30–2:00

ELEMENTOS = {  # los 11 del marco de Diego → cómo reconocerlos en la línea "🧱 Cuerpo (elementos)"
    "resultado soñado": r"so[ñn]ad",
    "pesadilla": r"pesadilla",
    "causa de fracasos": r"causa|fracaso",
    "prueba de pares": r"pares",
    "garantía / mejor oportunidad": r"garant|mejor oportunidad",
    "riesgos": r"riesgo",
    "tiempo del método actual": r"tiempo",
    "velocidad": r"velocidad",
    "esfuerzo y sacrificio": r"esfuerzo|sacrificio",
    "facilidad": r"facilidad",
    "el cuándo": r"cu[aá]ndo",
}
NIVELES = {  # el orden importa: primero el más específico
    "inconsciente del problema": r"inconsciente",
    "consciente del problema": r"consciente del problema",
    "consciente de la solución": r"consciente de la soluci[oó]n|\bsoluci[oó]n\b",
    "consciente del producto": r"consciente del producto|\bproducto\b",
    "consciente de la marca": r"consciente de la marca|\bmarca\b",
}
LLAMADAS = {"E": "etiqueta", "P": "pregunta afirmativa", "S": "si-entonces"}
ANGULOS_DOLOR = {  # de qué habla el gancho: va después del «·» en el paréntesis → (pregunta · fracaso)
    "dolor": r"dolor", "problema": r"problema", "miedo": r"miedo", "fracaso": r"fracas|tropiez",
    "obstáculo": r"obst[aá]culo", "consecuencia": r"consecuencia",
}
ANGULOS_OTROS = {"sueño": r"sue[ñn]o|deseo", "libre": r"libre"}
ARRANQUES_DEPENDIENTES = (
    "eso ", "esto ", "esa ", "ese ", "y ", "pero ", "porque ", "por eso", "exacto", "sí,", "si,", "suena ", "así es",
    "pues ", "claro", "no,", "tampoco", "también ", "lo sé", "te entiendo", "es que ",
)
SUENA_A_IA = (
    "incómod", "fascinante", "sumérgete", "sumergirte", "vertiginoso", "es importante señalar", "cabe destacar",
    "en el mundo de", "descubre el poder", "potencia tu", "desbloquea", "revolucionari", "sin precedentes",
    "en resumen", "en conclusión", "un viaje", "tapiz",
)


def _numero_hablado(n: int) -> int:
    """Cuántas palabras se DICEN al leer un número: 197 → ciento noventa y siete = 4."""
    if n >= 1000:
        return (_numero_hablado(n // 1000) if n // 1000 > 1 else 0) + 1 + (_numero_hablado(n % 1000) if n % 1000 else 0)
    if n >= 100:
        return 1 + (_numero_hablado(n % 100) if n % 100 else 0)
    if n > 30 and n % 10:
        return 3
    return 1


def palabras(s: str) -> int:
    total = 0
    for t in re.findall(r"[\wáéíóúüñÁÉÍÓÚÜÑ$%]+", s):
        d = re.sub(r"[$%.,]", "", t)
        total += _numero_hablado(int(d)) if d.isdigit() else 1
    return total


def limpiar(s: str) -> str:
    s = re.sub(r"\([^)]{0,80}\)", " ", s)        # acotaciones: (el espejo habla)
    return re.sub(r"[*_`>«»]", "", s).strip()


def mmss(seg: float) -> str:
    return f"{int(seg // 60)}:{int(round(seg % 60)):02d}"


def partir(texto: str) -> list[dict]:
    bloques = re.split(r"\n(?=#{1,4}\s*(?:⭐\s*)?ANUNCIO\s+N)", texto)
    anuncios = []
    for b in bloques:
        m = re.match(r"#{1,4}\s*(?:⭐\s*)?ANUNCIO\s+N\S*\s*(\d+)(.*)", b)
        if not m:
            continue
        titulo = m.group(2).strip(" —-·")
        ganchos = []
        for g in re.finditer(r"^[ \t]*[-*•]?[ \t]*\**\s*(Principal|V\d)\b\s*(\[[EPS—\-]\])?\s*(\([^)\n]*\))?\s*\**\s*:\s*\**\s*(.+)$",
                             b, flags=re.M):
            etiqueta = (g.group(2) or "") + (g.group(3) or "")
            llamada = None
            mt = re.search(r"\[([EPS])\]", etiqueta)
            if mt:
                llamada = mt.group(1)
            elif re.search(r"etiqueta", etiqueta, re.I):
                llamada = "E"
            elif re.search(r"pregunta afirmativa", etiqueta, re.I):
                llamada = "P"
            elif re.search(r"si[\s,…-]*entonces", etiqueta, re.I):
                llamada = "S"
            partes = (g.group(3) or "").strip("()").split("·")
            formula = partes[0].strip().lower()
            angulo = None
            if len(partes) > 1:
                for trozo in partes[1:]:  # el ángulo va después de la fórmula; puede seguirle una marca (· NUEVO)
                    angulo = next((k for k, rx in {**ANGULOS_DOLOR, **ANGULOS_OTROS}.items()
                                   if re.search(rx, trozo, re.I)), None)
                    if angulo:
                        break
            ganchos.append({"id": g.group(1), "etiqueta": etiqueta, "llamada": llamada, "formula": formula,
                            "angulo": angulo, "texto": limpiar(g.group(4))})
        mc = re.search(r"\[CUERPO\]\**\s*(.*?)(?=\n\s*\**\[CTA\])", b, flags=re.S)
        mt = re.search(r"\[CTA\]\**\s*(.*?)(?=\n\s*(?:#|---|\*\*[🎬🎥⏱️🧱🪝])|\Z)", b, flags=re.S)
        me = re.search(r"Cuerpo \(elementos\)\s*:?\**\s*:?\s*(.+)", b)
        anuncios.append({
            "n": int(m.group(1)), "titulo": titulo, "bruto": b, "ganchos": ganchos,
            "cuerpo": limpiar(mc.group(1)) if mc else "", "cta": limpiar(mt.group(1)) if mt else "",
            "elementos": me.group(1).strip() if me else "",
            "visual": bool(re.search(r"🎥", b)), "testear": "🧪" in b or "TESTEAR" in b.upper(),
        })
    return anuncios


def revisar(a: dict, o) -> tuple[list[str], list[str], dict]:
    err, av = [], []
    g = a["ganchos"]
    # ── ganchos ──
    if len(g) != 4:
        err.append(f"tiene {len(g)} ganchos (deben ser 4: Principal, V1, V2, V3)")
    con_llamada = [x for x in g if x["llamada"]]
    if g and len(con_llamada) < 2:
        err.append(f"solo {len(con_llamada)} gancho(s) con llamada marcada [E]/[P]/[S] (mínimo 2 de 4)")
    # ── ángulos: mínimo 2 de dolor + 1 de sueño (+1 libre) y 4 fórmulas distintas ──
    sin_angulo = [x["id"] for x in g if not x["angulo"]]
    if sin_angulo:
        err.append(f"gancho(s) {', '.join(sin_angulo)} sin ángulo marcado: va así → (fórmula · dolor|problema|miedo|"
                   "fracaso|obstáculo|consecuencia|sueño|libre)")
    elif g:
        de_dolor = [x["angulo"] for x in g if x["angulo"] in ANGULOS_DOLOR]
        if len(de_dolor) < 2:
            err.append(f"solo {len(de_dolor)} gancho(s) con ángulo de dolor (mínimo 2 de 4)")
        elif len(set(de_dolor)) == 1:
            av.append(f"los ganchos de dolor son todos «{de_dolor[0]}»: rotar (dolor, problema, miedo, fracaso, "
                      "obstáculo, consecuencia)")
        if not any(x["angulo"] == "sueño" for x in g):
            err.append("ningún gancho con ángulo de sueño (mínimo 1 de 4)")
        if len(g) == 4 and not any(x["angulo"] == "libre" for x in g) and len(de_dolor) + sum(x["angulo"] == "sueño" for x in g) == 4:
            av.append("ningún gancho libre: la regla es mínimo 2 de dolor, 1 de sueño y 1 libre")
    formulas_ad = [x["formula"] for x in g if x["formula"]]
    if len(formulas_ad) != len(set(formulas_ad)):
        av.append("hay fórmulas repetidas entre los 4 ganchos: cada uno debe usar una fórmula distinta")
    for i, x in enumerate(g):
        if palabras(x["texto"]) > 32:
            av.append(f"gancho {x['id']} tiene {palabras(x['texto'])} palabras: Diego borra los ganchos largos (ideal: menos de 25)")
        if o.producto and o.producto.lower() in x["texto"].lower():
            av.append(f"gancho {x['id']} nombra «{o.producto}»: la gente no sabe qué es; solo vale si el mismo gancho lo "
                      "amarra al problema que resuelve («…y por qué es la solución para tu problema de…»)")
        for j in o.jerga:
            if j in x["texto"].lower():
                err.append(f"gancho {x['id']} usa «{j}»: la gente no conoce esa palabra (el gancho no da por sabido el producto)")
        for y in g[i + 1:]:
            if difflib.SequenceMatcher(a=x["texto"].lower(), b=y["texto"].lower()).ratio() > 0.72:
                av.append(f"ganchos {x['id']} y {y['id']} son casi iguales: no sirven para test A/B")
    # ── cuerpo y empalme ──
    if not a["cuerpo"]:
        err.append("no encuentro el [CUERPO]")
    else:
        primera = a["cuerpo"].lstrip("“\"'¡¿ ")
        if primera[:1].islower():
            err.append("el cuerpo arranca en minúscula: es la continuación de UN gancho y no empalma con los otros 3")
        elif primera.lower().startswith(ARRANQUES_DEPENDIENTES):
            av.append(f"el cuerpo arranca con «{' '.join(primera.split()[:4])}…»: revisar que empalme con los 4 ganchos")
    # ── duración ──
    datos = {}
    if g and a["cuerpo"] and a["cta"]:
        base = palabras(a["cuerpo"]) + palabras(a["cta"])
        totales = [base + palabras(x["texto"]) for x in g]
        lo, hi = min(totales) / PPM * 60, max(totales) / PPM * 60
        datos = {"palabras_min": min(totales), "palabras_max": max(totales), "seg_min": round(lo), "seg_max": round(hi)}
        if hi > MAX_S and not a["testear"]:
            err.append(f"dura {mmss(hi)} con el gancho más largo: pasa de 2:00 y no está marcado 🧪 TESTEAR")
        if lo < MIN_S:
            err.append(f"dura {mmss(lo)} con el gancho más corto ({min(totales)} palabras): menos de 0:35")
        medio = (lo + hi) / 2
        datos["banda"] = "corto" if medio < 60 else "medio" if medio < 90 else "largo"
        mb = re.search(r"\b(corto|medio|largo)\b", a["titulo"], re.I)
        if mb and mb.group(1).lower() != datos["banda"] and min(abs(medio - 60), abs(medio - 90)) > 5:
            err.append(f"el encabezado dice {mb.group(1)} y por palabras es {datos['banda']} ({mmss(medio)})")
        md = re.search(r"~\s*(\d):(\d\d)", a["titulo"])
        if md:
            dicho = int(md.group(1)) * 60 + int(md.group(2))
            real = (lo + hi) / 2
            if abs(dicho - real) > 12:
                av.append(f"el encabezado dice ~{mmss(dicho)} y por palabras da ~{mmss(real)}")
        else:
            av.append("el encabezado no trae la duración (~m:ss)")
    # ── elementos ──
    if not a["elementos"]:
        err.append("falta la línea 🧱 Cuerpo (elementos)")
    else:
        usados = [k for k, rx in ELEMENTOS.items() if re.search(rx, a["elementos"], re.I)]
        datos["elementos"] = usados
        total = len([p for p in re.split(r"\s*\+\s*", a["elementos"]) if p.strip()])
        if "resultado soñado" not in usados:
            err.append("no usa Resultado soñado (va casi siempre)")
        if "pesadilla" not in usados:
            av.append("no usa Pesadilla (va casi siempre: que sea a propósito)")
        seg = (datos.get("seg_min", 0) + datos.get("seg_max", 0)) / 2  # con el promedio: 1 s de un gancho no cambia la exigencia
        minimo = 3 if seg < 60 else 4 if seg < 80 else 5 if seg < 100 else 6
        if total < minimo:
            err.append(f"solo {total} elementos/gatillos para {mmss(seg)}: con esa duración caben al menos {minimo}")
    for j in o.jerga:
        if j in a["cuerpo"].lower():
            av.append(f"el cuerpo usa «{j}»: solo vale si la misma frase lo explica con palabras de la gente")
    # ── la oferta en claro: línea 🎯 con qué es, para qué sirve (beneficios) y qué pasa si no ──
    mq = re.search(r"🎯[^\n:]*:\**\s*(.+)", a["bruto"])
    seg_q = (datos.get("seg_min", 0) + datos.get("seg_max", 0)) / 2
    pide_q = 3 if seg_q < 60 else 4 if seg_q < 90 else 5
    if not mq:
        err.append("falta la línea 🎯 Queda claro (qué es | sirve para: a; b; c | si no lo haces: …)")
    else:
        partes_q = [x.strip() for x in mq.group(1).split("|")]
        que_es = next((x for x in partes_q if re.match(r"qu[eé] es", x, re.I)), "")
        sirve = next((x for x in partes_q if re.match(r"sirve para|beneficios", x, re.I)), "")
        si_no = next((x for x in partes_q if re.match(r"si no", x, re.I)), "")
        n_ben = len([b for b in re.split(r";", sirve.split(":", 1)[-1]) if b.strip()]) if sirve else 0
        datos["beneficios_declarados"] = n_ben
        if len(que_es.split(":", 1)[-1].strip()) < 15:
            err.append("🎯 no dice qué es el producto")
        if n_ben < pide_q:
            err.append(f"🎯 solo declara {n_ben} beneficio(s): con esa duración el cuerpo debe dar al menos {pide_q}")
        if len(si_no.split(":", 1)[-1].strip()) < 15:
            err.append("🎯 no dice qué pasa si no lo hace (la consecuencia / qué previene)")
    # ── el cuerpo nombra el producto y toca los beneficios de la ficha ──
    cuerpo_cta = (a["cuerpo"] + " " + a["cta"]).lower()
    if o.producto and a["cuerpo"] and o.producto.lower() not in cuerpo_cta:
        err.append(f"el cuerpo no nombra el producto «{o.producto}»")
    if o.beneficios and a["cuerpo"]:
        tocados = [b for b in o.beneficios if any(alt.strip() in cuerpo_cta for alt in b.split("|"))]
        seg_b = (datos.get("seg_min", 0) + datos.get("seg_max", 0)) / 2
        pide = 3 if seg_b < 60 else 4 if seg_b < 90 else 5
        datos["beneficios"] = tocados
        if len(tocados) < pide:
            err.append(f"el cuerpo solo toca {len(tocados)} beneficio(s) de la ficha ({', '.join(tocados) or 'ninguno'}); "
                       f"con esa duración van al menos {pide}: no queda claro para qué sirve")
    # ── CTA ──
    if not a["cta"]:
        err.append("no encuentro el [CTA]")
    else:
        if not re.search(r"\bpara que\b|\bpara no\b|\by así\b|\bpara dejar\b|\bpara volver\b", a["cta"], re.I):
            err.append("el CTA no cierra con el dolor o el sueño («…para que…»)")
        if o.ciudad and o.ciudad.lower() not in a["cta"].lower():
            err.append(f"el CTA no nombra la ciudad «{o.ciudad}»")
        if o.cta and o.cta.lower() not in a["cta"].lower():
            err.append(f"el CTA no usa la acción del cliente «{o.cta}»")
    # ── quién graba / visual ──
    if not a["visual"]:
        err.append("falta la línea 🎥 (quién lo graba y qué se ve en el segundo 0)")
    # ── palabras ──
    hablado = " ".join([x["texto"] for x in g] + [a["cuerpo"], a["cta"]]).lower()
    for p in o.prohibido:
        if re.search(rf"\b{re.escape(p.lower())}", hablado):
            err.append(f"dice «{p}», que el cliente pidió NO decir")
    for p in SUENA_A_IA:
        if p in hablado:
            av.append(f"suena a IA: «{p}»")
    datos["llamadas"] = [x["llamada"] for x in g if x["llamada"]]
    datos["angulos"] = [x["angulo"] for x in g if x["angulo"]]
    datos["angulo_principal"] = g[0]["angulo"] if g else None
    datos["nivel"] = next((k for k, rx in NIVELES.items() if re.search(rx, a["titulo"], re.I)), None)
    return err, av, datos


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("banco")
    ap.add_argument("--ciudad", default="")
    ap.add_argument("--cta", default="", help="fragmento exacto de la acción que debe decir el CTA")
    ap.add_argument("--prohibido", default="", help="palabras que el cliente pidió no decir, separadas por coma")
    ap.add_argument("--permitir-cortos", action="store_true", help="(ya no hace falta: los cortos van siempre)")
    ap.add_argument("--mezcla", default="", help="cortos,medios,largos que debe traer el banco, p. ej. 13,10,7")
    ap.add_argument("--parcial", action="store_true", help="es una tanda: no exigir la cobertura del banco")
    ap.add_argument("--producto", default="", help="nombre del producto: cada cuerpo debe nombrarlo")
    ap.add_argument("--jerga", default="", help="palabras técnicas del glosario: prohibidas en ganchos, aviso en cuerpos")
    ap.add_argument("--niveles-flexibles", action="store_true", help="no exigir los 5 niveles de conciencia (público que no conoce el producto)")
    ap.add_argument("--beneficios", default="", help="palabras clave de los beneficios de la ficha, separadas por coma")
    ap.add_argument("--json", default="")
    o = ap.parse_args()
    o.prohibido = [p.strip() for p in o.prohibido.split(",") if p.strip()]
    o.beneficios = [p.strip().lower() for p in o.beneficios.split(",") if p.strip()]
    o.jerga = [p.strip().lower() for p in o.jerga.split(",") if p.strip()]

    anuncios = partir(Path(o.banco).read_text(encoding="utf-8"))
    if not anuncios:
        print("❌ No encontré ningún anuncio con el encabezado «## ANUNCIO Nº X — …».")
        return 1

    print(f"VERIFICADOR · {Path(o.banco).name} · {len(anuncios)} anuncios · {PPM} palabras/min · de 0:35 a 2:00\n")
    n_err = 0
    resumen, cuenta_el, cuenta_ll, cuenta_niv, formulas = [], {k: 0 for k in ELEMENTOS}, {k: 0 for k in LLAMADAS}, {k: 0 for k in NIVELES}, {}
    cuenta_ang = {k: 0 for k in {**ANGULOS_DOLOR, **ANGULOS_OTROS}}
    principales = {"dolor": 0, "sueño": 0, "libre": 0}
    for a in anuncios:
        err, av, d = revisar(a, o)
        n_err += len(err)
        dur = f"{mmss(d['seg_min'])}–{mmss(d['seg_max'])}" if "seg_min" in d else "?"
        print(f"{'❌' if err else '⚠️' if av else '✅'} Nº {a['n']:>2} · {dur} · {a['titulo'][:70]}")
        for e in err:
            print(f"      ❌ {e}")
        for w in av:
            print(f"      ⚠️ {w}")
        for k in d.get("elementos", []):
            cuenta_el[k] += 1
        for k in set(d.get("llamadas", [])):
            cuenta_ll[k] += 1
        for k in d.get("angulos", []):
            cuenta_ang[k] += 1
        ap_ = d.get("angulo_principal")
        if ap_:
            principales["dolor" if ap_ in ANGULOS_DOLOR else ap_] += 1
        if d.get("nivel"):
            cuenta_niv[d["nivel"]] += 1
        if a["ganchos"]:
            f = a["ganchos"][0]["formula"]
            formulas[f] = formulas.get(f, 0) + 1
        resumen.append({"n": a["n"], "titulo": a["titulo"], "errores": err, "avisos": av, **d})

    # ── mezcla de duraciones ──
    bandas = [r.get("banda") for r in resumen if r.get("banda")]
    mezcla = [bandas.count(b) for b in ("corto", "medio", "largo")]
    print(f"\nMEZCLA: {mezcla[0]} cortos (0:35–1:00) · {mezcla[1]} medios (1:00–1:30) · {mezcla[2]} largos (1:30–2:00)")
    if o.mezcla:
        pedida = [int(x) for x in re.findall(r"\d+", o.mezcla)][:3]
        if pedida != mezcla:
            n_err += 1
            print(f"  ❌ se pidió {pedida[0]} cortos · {pedida[1]} medios · {pedida[2]} largos")

    # ── repetidos entre anuncios ──
    print()
    for i, a in enumerate(anuncios):
        for b in anuncios[i + 1:]:
            if a["ganchos"] and b["ganchos"]:
                r = difflib.SequenceMatcher(a=a["ganchos"][0]["texto"].lower(), b=b["ganchos"][0]["texto"].lower()).ratio()
                if r > 0.7:
                    print(f"⚠️ Nº {a['n']} y Nº {b['n']} abren casi igual: ¿son el mismo anuncio?")

    # ── cobertura del banco ──
    N = len(anuncios)
    if not o.parcial:
        print("COBERTURA DEL MARCO DE DIEGO")
        minimo = max(2, round(N * 0.1))
        for k, c in cuenta_el.items():
            mal = c < (1 if k in ("resultado soñado", "pesadilla") else minimo)
            n_err += mal
            print(f"  {'❌' if mal else '✅'} {k:<30} {c:>2} de {N}" + (f"   (mínimo {minimo})" if mal else ""))
        for k, nombre in LLAMADAS.items():
            mal = cuenta_ll[k] < minimo
            n_err += mal
            print(f"  {'❌' if mal else '✅'} llamada [{k}] {nombre:<19} en {cuenta_ll[k]:>2} anuncios" + (f"   (mínimo {minimo})" if mal else ""))
        total_ang = sum(cuenta_ang.values()) or 1
        for k in ANGULOS_DOLOR:
            mal = cuenta_ang[k] < minimo
            n_err += mal
            print(f"  {'❌' if mal else '✅'} ángulo de dolor: {k:<18} {cuenta_ang[k]:>3} ganchos" + (f"   (mínimo {minimo})" if mal else ""))
        dolor_total = sum(cuenta_ang[k] for k in ANGULOS_DOLOR)
        print(f"  ·  ganchos por ángulo: dolor {dolor_total} ({dolor_total / total_ang:.0%}) · sueño {cuenta_ang['sueño']} "
              f"({cuenta_ang['sueño'] / total_ang:.0%}) · libre {cuenta_ang['libre']} ({cuenta_ang['libre'] / total_ang:.0%})")
        print(f"  ·  gancho principal: dolor {principales['dolor']} · sueño {principales['sueño']} · libre {principales['libre']}")
        for k, c in cuenta_niv.items():
            mal = c == 0 and N >= 10 and not o.niveles_flexibles
            n_err += mal
            print(f"  {'❌' if mal else '✅'} nivel: {k:<27} {c:>2}")
        repetidas = {f: c for f, c in formulas.items() if f and c > max(3, N // 6)}
        for f, c in repetidas.items():
            print(f"  ⚠️ la fórmula «{f}» abre {c} anuncios: rotar más")
    print(f"\n{'❌ ' + str(n_err) + ' cosa(s) por arreglar antes de pasarlo al jefe.' if n_err else '✅ Pasa la regla. Ahora le toca al jefe (criterio).'}")
    if o.json:
        Path(o.json).write_text(json.dumps({"anuncios": resumen, "elementos": cuenta_el, "llamadas": cuenta_ll,
                                            "niveles": cuenta_niv, "errores": n_err}, ensure_ascii=False, indent=1),
                                encoding="utf-8")
    return 1 if n_err else 0


if __name__ == "__main__":
    sys.exit(main())
