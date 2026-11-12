"""
Planificador: del plan de canal + radar → calendario de piezas (largos en series, Shorts derivados y del radar, en vivos, comunidad).

    python -m fabrica.planificar --perfil equilibrate_es            # usa fechas del plan
    python -m fabrica.planificar --perfil equilibrate_es --desde 2026-11-06 --hasta 2026-12-31

Salida: planes/<perfil>.json (lo lee la pestaña Plan de la página). Cada pieza nace en estado "planificado";
la cola de producción toma las piezas aprobadas.
"""
import argparse, datetime as dt, json, math
from .comun import cargar_env, ROOT, claude, estilo, marca, nivel_para, oferta, canal_de, perfil as cargar_perfil, guardar_json, MOCK
from . import historias as mod_historias

PLANES = ROOT / "planes"
EJES = {"equilibrate": "Amor (pareja, amor propio, familia, vínculos, emociones)", "mitribu": "Dinero", "soyintegral": "Salud"}


def radar_top(perfil_id, n=40):
    p = ROOT / "data" / f"{perfil_id}.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    return [{"video_id": v["video_id"], "titulo": v["titulo"], "vistas": v["vistas"], "ratio": v["ratio_vistas_subs"], "canal": v["canal"], "dias": v["dias"], "subnicho": v.get("subnicho", "")}
            for v in d["videos"][:n]]


def disenar(perfil, plan, n_series, n_shorts_radar, top, n_conversion=0, n_rostro=0):
    """Diseña en llamadas pequeñas: una por serie (6 capítulos + 3 shorts c/u), otra para shorts del radar, en vivos y comunidad."""
    canal = canal_de(perfil["id"])
    contexto = f"""Canal: {perfil['canal']} · Eje: {EJES[canal]} · Objetivo: {plan['objetivo']}
Videos virales recientes del nicho (canales de 1k–100k subs), para inspirar temas y fórmulas, NO copiar títulos:
{json.dumps(top[:25], ensure_ascii=False)}
Títulos con fórmula probada (número, contradicción, pregunta), sin hashtags, ≤ 70 caracteres. Dentro de los textos no uses comillas dobles."""
    series, usados = [], []
    for i in range(n_series):
        user = contexto + f"""

Diseña la SERIE {i + 1} de {n_series} de videos largos de {plan['minutos_largo']} min (6 capítulos) para acumular horas de visualización: tema madre con tensión
narrativa (el espectador quiere ver el siguiente); cada capítulo es un video que funciona solo. Debe ser distinta de estas series ya diseñadas: {usados or 'ninguna'}.
Para cada capítulo, 3 SHORTS derivados (gancho corto que lleva al largo). Responde SOLO JSON:
{{"nombre": "..", "tema_madre": "..", "promesa": "..", "capitulos": [{{"n": 1, "titulo": "..", "subtema": "..", "referencia_video_id": "video_id de la lista o vacío",
  "shorts": [{{"titulo": "..", "gancho": ".."}}, {{"titulo": "..", "gancho": ".."}}, {{"titulo": "..", "gancho": ".."}}]}}, "... hasta n=6"]}}"""
        mock = {"nombre": f"Serie {i + 1}", "tema_madre": "x", "promesa": "y", "capitulos": [{"n": k, "titulo": f"Capítulo {k} serie {i + 1}", "subtema": "", "referencia_video_id": "",
                "shorts": [{"titulo": f"Short {i + 1}.{k}.{j}", "gancho": ".."} for j in range(1, 4)]} for k in range(1, 7)]}
        sr = claude(estilo(canal), user, mock=mock, max_tokens=5000)
        sr["capitulos"] = sr.get("capitulos", [])[:6]
        for c in sr["capitulos"]:
            c["shorts"] = (c.get("shorts") or [])[:3]
        series.append(sr); usados.append(sr.get("nombre", f"serie {i + 1}"))
    user = contexto + f"""

Propón: (a) {n_shorts_radar} SHORTS sueltos basados en los temas virales de la lista (indica referencia_video_id de la lista); (b) {max(len(plan.get('dias_vivos', [])), 1) * 2} temas de EN VIVO
(formato: pregunta abierta + reto colectivo, 60–75 min, pensados para que la gente se quede y participe); (c) 6 publicaciones de comunidad (encuesta "Personaliza tu Germancho",
reto de la semana, pregunta). Responde SOLO JSON:
{{"shorts_radar": [{{"titulo": "..", "gancho": "..", "referencia_video_id": ".."}}], "vivos": [{{"titulo": "..", "pregunta_abierta": "..", "reto_colectivo": ".."}}],
 "comunidad": [{{"tipo": "encuesta|reto|pregunta", "texto": ".."}}]}}"""
    mock = {"shorts_radar": [{"titulo": f"Short radar {i}", "gancho": "..", "referencia_video_id": (top[i]["video_id"] if i < len(top) else "")} for i in range(n_shorts_radar)],
            "vivos": [{"titulo": "En vivo de prueba", "pregunta_abierta": "..", "reto_colectivo": ".."}] * 3, "comunidad": [{"tipo": "encuesta", "texto": "¿Con qué cara amaneció tu Germancho?"}] * 3}
    extra = claude(estilo(canal), user, mock=mock, max_tokens=5000)
    conv = {"conversion": [], "rostro": []}
    if n_conversion or n_rostro:
        of = oferta(nivel_para(canal, "conversion"))
        user = contexto + f"""

Piezas de CONVERSIÓN (10 % del contenido; la única con invitación explícita). Oferta del canal: {of.get('nombre', 'clase gratuita')}.
(a) {n_conversion} SHORTS de Germancho que invitan sin vender: formatos «qué pasa en la clase gratuita», «historia de alguien que hizo el reto 7 días», «cómo trabajo con la gente»,
    «3 preguntas que me hacen siempre». Cada uno con gancho y la invitación al final.
(b) {n_rostro} piezas con ROSTRO REAL (Germán a cámara, 60–90 s; él las graba, la fábrica las edita): tema, gancho de 1 frase, 3 ideas, cierre con invitación.
Responde SOLO JSON: {{"conversion": [{{"titulo": "..", "gancho": "..", "formato": ".."}}], "rostro": [{{"titulo": "..", "gancho": "..", "ideas": ["..", "..", ".."], "cierre": ".."}}]}}"""
        mock = {"conversion": [{"titulo": f"Conversión {i}", "gancho": "..", "formato": "clase"} for i in range(n_conversion)],
                "rostro": [{"titulo": f"Rostro {i}", "gancho": "..", "ideas": ["a", "b", "c"], "cierre": ".."} for i in range(n_rostro)]}
        conv = claude(estilo(canal), user, mock=mock, max_tokens=4000)
    return {"series": series, "shorts_radar": extra.get("shorts_radar", []), "vivos": extra.get("vivos", []), "comunidad": extra.get("comunidad", []),
            "conversion": conv.get("conversion", []), "rostro": conv.get("rostro", [])}


def calendario(perfil, plan, diseno, desde, hasta):
    """Reparte las piezas en fechas según la cadencia del plan."""
    dias = [desde + dt.timedelta(days=i) for i in range((hasta - desde).days + 1)]
    largos = [dict(c, serie=s["nombre"], serie_i=si) for si, s in enumerate(diseno["series"]) for c in s["capitulos"]]
    shorts_der = [dict(sh, serie=s["nombre"], capitulo=c["n"], capitulo_titulo=c["titulo"]) for s in diseno["series"] for c in s["capitulos"] for sh in c["shorts"]]
    shorts_radar = list(diseno.get("shorts_radar", []))
    vivos = list(diseno.get("vivos", [])); comunidad = list(diseno.get("comunidad", []))
    conversion = list(diseno.get("conversion", [])); rostro = list(diseno.get("rostro", []))
    canal = canal_de(perfil["id"])
    mezcla = marca().get("tipos_contenido", {}).get("mezcla", {"atraccion": 0.6, "nutricion": 0.3, "conversion": 0.1})
    conv_semana = max(1, round(plan["shorts_semana"] * mezcla.get("conversion", 0.1))) if conversion else 0
    quincenal = plan["shorts_semana"] < 5          # con pocos shorts, la conversión va cada dos semanas para no comerse la atracción
    dia_conv = sorted(plan["dias_shorts"])[-conv_semana:] if plan["dias_shorts"] else []   # últimos días de shorts de la semana → conversión
    dia_rostro = sorted(plan["dias_shorts"])[len(plan["dias_shorts"]) // 2] if (rostro and plan["dias_shorts"]) else None
    hist_semana = plan.get("historias_semana", 2 if plan["shorts_semana"] >= 7 else 1)
    banco = mod_historias.disponibles(canal, 999)
    dias_hist = sorted(plan["dias_shorts"])[:hist_semana] if (banco and plan["dias_shorts"]) else []   # primeros días de shorts → historia
    hi = 0
    piezas, k = [], 0
    li = si_der = si_rad = vi = ci = co = ro = 0
    for d in dias:
        wd = d.weekday()
        if wd in plan["dias_largos"] and li < len(largos):
            c = largos[li]; li += 1; k += 1
            tc = "atraccion" if c["n"] == 1 else "nutricion"
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-L", "fecha": d.isoformat(), "hora": plan["hora_largos"], "tipo": "largo", "serie": c["serie"], "capitulo": c["n"],
                           "titulo": c["titulo"], "subtema": c.get("subtema", ""), "referencia_video_id": c.get("referencia_video_id", ""), "minutos": plan["minutos_largo"],
                           "tipo_contenido": tc, "nivel": nivel_para(canal, tc), "estado": "planificado"})
        if wd in dias_hist and hi < len(banco):
            h = banco[hi]; hi += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-S", "fecha": d.isoformat(), "hora": plan["hora_shorts"], "tipo": "short", "origen": "historia", "historia_id": h["id"],
                           "titulo": h["titulo"], "gancho": h.get("gancho", ""), "fuente_historia": h.get("fuente", ""), "referencia_video_id": "",
                           "tipo_contenido": "atraccion", "nivel": nivel_para(canal, "atraccion"), "visual": "broll", "estado": "planificado"})
        elif wd in dia_conv and co < len(conversion) and not (quincenal and ((d - desde).days // 7) % 2):
            c = conversion[co]; co += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-S", "fecha": d.isoformat(), "hora": plan["hora_shorts"], "tipo": "short", "origen": "conversion",
                           "titulo": c["titulo"], "gancho": c.get("gancho", ""), "formato_conv": c.get("formato", ""), "referencia_video_id": "",
                           "tipo_contenido": "conversion", "nivel": nivel_para(canal, "conversion"), "estado": "planificado"})
        elif wd in plan["dias_shorts"]:
            # mezcla objetivo: ~60 % atracción (radar) / ~40 % nutrición (derivados de los largos), según config/marca.json
            fuente = None
            quiere_radar = si_rad < max(1, (si_rad + si_der + 1) * mezcla.get("atraccion", 0.6))
            if quiere_radar and si_rad < len(shorts_radar):
                fuente = shorts_radar[si_rad]; si_rad += 1; tipo_src = "radar"
            elif si_der < len(shorts_der):
                fuente = shorts_der[si_der]; si_der += 1; tipo_src = "derivado"
            elif si_rad < len(shorts_radar):
                fuente = shorts_radar[si_rad]; si_rad += 1; tipo_src = "radar"
            if fuente:
                tc = "atraccion" if tipo_src == "radar" else "nutricion"
                piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-S", "fecha": d.isoformat(), "hora": plan["hora_shorts"], "tipo": "short", "origen": tipo_src,
                               "serie": fuente.get("serie", ""), "capitulo": fuente.get("capitulo", ""), "titulo": fuente["titulo"], "gancho": fuente.get("gancho", ""),
                               "referencia_video_id": fuente.get("referencia_video_id", ""), "tipo_contenido": tc, "nivel": nivel_para(canal, tc), "estado": "planificado"})
        if wd == dia_rostro and ro < len(rostro):
            r = rostro[ro]; ro += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-R", "fecha": d.isoformat(), "hora": plan["hora_shorts"], "tipo": "rostro", "titulo": r["titulo"], "gancho": r.get("gancho", ""),
                           "ideas": r.get("ideas", []), "cierre": r.get("cierre", ""), "tipo_contenido": "conversion", "nivel": nivel_para(canal, "conversion"),
                           "nota": "La graba Germán a cámara (60–90 s, vertical); la fábrica pone subtítulos, miniatura y CTA.", "estado": "planificado"})
        if wd in plan.get("dias_vivos", []) and vivos:
            v = vivos[vi % len(vivos)]; vi += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-V", "fecha": d.isoformat(), "hora": plan["hora_vivos"], "tipo": "vivo", "titulo": v["titulo"],
                           "pregunta_abierta": v.get("pregunta_abierta", ""), "reto_colectivo": v.get("reto_colectivo", ""), "minutos": plan["duracion_vivo_min"],
                           "tipo_contenido": "nutricion", "nivel": nivel_para(canal, "nutricion"), "estado": "planificado"})
        if comunidad and plan.get("comunidad_semana", 0) and wd in [0, 3, 5][: plan["comunidad_semana"]]:
            c = comunidad[ci % len(comunidad)]; ci += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-C", "fecha": d.isoformat(), "hora": "09:00", "tipo": "comunidad", "titulo": c["texto"], "subtipo": c.get("tipo", ""), "tipo_contenido": "nutricion", "estado": "planificado"})
    return piezas


def proyeccion(plan, piezas, desde, hasta):
    """Estimación simple de horas y suscriptores al final del periodo (supuestos declarados)."""
    sem = max((hasta - desde).days / 7, 1)
    n_l = sum(1 for p in piezas if p["tipo"] == "largo"); n_s = sum(1 for p in piezas if p["tipo"] == "short"); n_v = sum(1 for p in piezas if p["tipo"] == "vivo")
    sup = {"vistas_largo_promedio": 700, "retencion_largo": 0.35, "minutos_largo": plan["minutos_largo"], "espectadores_vivo_promedio": 35, "minutos_vivo": plan["duracion_vivo_min"],
           "repeticion_vivo_vistas": 150, "vistas_short_promedio": 3500, "conversion_subs_short": 0.006, "conversion_subs_largo": 0.03}
    h_largos = n_l * sup["vistas_largo_promedio"] * sup["retencion_largo"] * sup["minutos_largo"] / 60
    h_vivos = n_v * (sup["espectadores_vivo_promedio"] * sup["minutos_vivo"] + sup["repeticion_vivo_vistas"] * sup["minutos_vivo"] * 0.3) / 60
    subs = plan.get("subs_actuales", 0) + n_s * sup["vistas_short_promedio"] * sup["conversion_subs_short"] + n_l * sup["vistas_largo_promedio"] * sup["conversion_subs_largo"]
    return {"semanas": round(sem, 1), "largos": n_l, "shorts": n_s, "vivos": n_v, "horas_estimadas": round(plan.get("horas_actuales", 0) + h_largos + h_vivos),
            "horas_de_largos": round(h_largos), "horas_de_vivos": round(h_vivos), "subs_estimados": round(subs), "supuestos": sup,
            "nota": "Estimación con supuestos conservadores; se recalibra cada semana con datos reales del tablero."}


def main():
    cargar_env()
    ap = argparse.ArgumentParser(); ap.add_argument("--perfil", required=True); ap.add_argument("--desde", default=""); ap.add_argument("--hasta", default="")
    a = ap.parse_args()
    p = cargar_perfil(a.perfil)
    plan = json.loads((ROOT / "config/planes.json").read_text())["planes"][a.perfil]
    desde = dt.date.fromisoformat(a.desde or plan["desde"]); hasta = dt.date.fromisoformat(a.hasta or plan["hasta"])
    semanas = max((hasta - desde).days / 7, 1)
    n_largos = round(plan["largos_semana"] * semanas)
    n_series = max(math.ceil(n_largos / 6), 1)
    n_shorts = round(plan["shorts_semana"] * semanas)
    n_shorts_radar = max(round(n_shorts * 0.6), 4)
    top = radar_top(a.perfil)
    mezcla = marca().get("tipos_contenido", {}).get("mezcla", {})
    n_conv = round(max(1, round(plan["shorts_semana"] * mezcla.get("conversion", 0.1))) * semanas / (1 if plan["shorts_semana"] >= 5 else 2)) if plan["shorts_semana"] else 0
    n_rostro = round(semanas) if plan.get("rostro_semana", 1) else 0
    print(f"=== Plan {a.perfil} [{plan['modo']}] {desde} → {hasta}: {n_largos} largos en {n_series} series, {n_shorts} shorts ({n_conv} de conversión), {n_rostro} piezas con rostro, {len(top)} referencias del radar")
    diseno = disenar(p, plan, n_series, n_shorts_radar, top, n_conv, n_rostro)
    piezas = calendario(p, plan, diseno, desde, hasta)
    out = {"perfil": a.perfil, "canal": p["canal"], "plan": plan, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "generado": dt.datetime.now().isoformat(timespec="seconds"),
           "series": diseno["series"], "vivos": diseno.get("vivos", []), "comunidad": diseno.get("comunidad", []), "conversion": diseno.get("conversion", []), "rostro": diseno.get("rostro", []),
           "mezcla": {t: sum(1 for x in piezas if x.get("tipo_contenido") == t) for t in ("atraccion", "nutricion", "conversion")},
           "piezas": piezas, "proyeccion": proyeccion(plan, piezas, desde, hasta)}
    PLANES.mkdir(exist_ok=True)
    guardar_json(PLANES / f"{a.perfil}.json", out)
    idx = {"planes": [json.loads(f.read_text()) | {"piezas": None, "series": None} for f in sorted(PLANES.glob("*.json")) if f.name != "index.json"]}
    for q in idx["planes"]:
        q.pop("piezas", None); q.pop("series", None)
    guardar_json(PLANES / "index.json", idx)
    pr = out["proyeccion"]
    print(f"  piezas: {len(piezas)} · estimación al {hasta}: {pr['horas_estimadas']} h, {pr['subs_estimados']} subs")


if __name__ == "__main__":
    main()
