"""
Planificador: del plan de canal + radar → calendario de piezas (largos en series, Shorts derivados y del radar, en vivos, comunidad).

    python -m fabrica.planificar --perfil equilibrate_es            # usa fechas del plan
    python -m fabrica.planificar --perfil equilibrate_es --desde 2026-11-06 --hasta 2026-12-31

Salida: planes/<perfil>.json (lo lee la pestaña Plan de la página). Cada pieza nace en estado "planificado";
la cola de producción toma las piezas aprobadas.
"""
import argparse, datetime as dt, json, math
from .comun import cargar_env, ROOT, claude, ESTILO_GERMANCHO, canal_de, perfil as cargar_perfil, guardar_json, MOCK

PLANES = ROOT / "planes"
EJES = {"equilibrate": "Amor (pareja, amor propio, familia, vínculos, emociones)", "mitribu": "Dinero", "soyintegral": "Salud"}


def radar_top(perfil_id, n=40):
    p = ROOT / "data" / f"{perfil_id}.json"
    if not p.exists():
        return []
    d = json.loads(p.read_text())
    return [{"video_id": v["video_id"], "titulo": v["titulo"], "vistas": v["vistas"], "ratio": v["ratio_vistas_subs"], "canal": v["canal"], "dias": v["dias"], "subnicho": v.get("subnicho", "")}
            for v in d["videos"][:n]]


def disenar(perfil, plan, n_series, n_shorts_radar, top):
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
        sr = claude(ESTILO_GERMANCHO, user, mock=mock, max_tokens=5000)
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
    extra = claude(ESTILO_GERMANCHO, user, mock=mock, max_tokens=5000)
    return {"series": series, "shorts_radar": extra.get("shorts_radar", []), "vivos": extra.get("vivos", []), "comunidad": extra.get("comunidad", [])}


def calendario(perfil, plan, diseno, desde, hasta):
    """Reparte las piezas en fechas según la cadencia del plan."""
    dias = [desde + dt.timedelta(days=i) for i in range((hasta - desde).days + 1)]
    largos = [dict(c, serie=s["nombre"], serie_i=si) for si, s in enumerate(diseno["series"]) for c in s["capitulos"]]
    shorts_der = [dict(sh, serie=s["nombre"], capitulo=c["n"], capitulo_titulo=c["titulo"]) for s in diseno["series"] for c in s["capitulos"] for sh in c["shorts"]]
    shorts_radar = list(diseno.get("shorts_radar", []))
    vivos = list(diseno.get("vivos", [])); comunidad = list(diseno.get("comunidad", []))
    piezas, k = [], 0
    li = si_der = si_rad = vi = ci = 0
    for d in dias:
        wd = d.weekday()
        if wd in plan["dias_largos"] and li < len(largos):
            c = largos[li]; li += 1; k += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-L", "fecha": d.isoformat(), "hora": plan["hora_largos"], "tipo": "largo", "serie": c["serie"], "capitulo": c["n"],
                           "titulo": c["titulo"], "subtema": c.get("subtema", ""), "referencia_video_id": c.get("referencia_video_id", ""), "minutos": plan["minutos_largo"], "estado": "planificado"})
        if wd in plan["dias_shorts"]:
            # alternar: 2 derivados del largo más reciente, 1 del radar
            fuente = None
            if (k + si_der) % 3 != 2 and si_der < len(shorts_der):
                fuente = shorts_der[si_der]; si_der += 1; tipo_src = "derivado"
            elif si_rad < len(shorts_radar):
                fuente = shorts_radar[si_rad]; si_rad += 1; tipo_src = "radar"
            elif si_der < len(shorts_der):
                fuente = shorts_der[si_der]; si_der += 1; tipo_src = "derivado"
            if fuente:
                piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-S", "fecha": d.isoformat(), "hora": plan["hora_shorts"], "tipo": "short", "origen": tipo_src,
                               "serie": fuente.get("serie", ""), "capitulo": fuente.get("capitulo", ""), "titulo": fuente["titulo"], "gancho": fuente.get("gancho", ""),
                               "referencia_video_id": fuente.get("referencia_video_id", ""), "estado": "planificado"})
        if wd in plan.get("dias_vivos", []) and vivos:
            v = vivos[vi % len(vivos)]; vi += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-V", "fecha": d.isoformat(), "hora": plan["hora_vivos"], "tipo": "vivo", "titulo": v["titulo"],
                           "pregunta_abierta": v.get("pregunta_abierta", ""), "reto_colectivo": v.get("reto_colectivo", ""), "minutos": plan["duracion_vivo_min"], "estado": "planificado"})
        if comunidad and plan.get("comunidad_semana", 0) and wd in [0, 3, 5][: plan["comunidad_semana"]]:
            c = comunidad[ci % len(comunidad)]; ci += 1
            piezas.append({"id": f"{perfil['id']}-{d:%Y%m%d}-C", "fecha": d.isoformat(), "hora": "09:00", "tipo": "comunidad", "titulo": c["texto"], "subtipo": c.get("tipo", ""), "estado": "planificado"})
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
    n_shorts_radar = max(n_shorts - n_largos * 3, 4)
    top = radar_top(a.perfil)
    print(f"=== Plan {a.perfil} [{plan['modo']}] {desde} → {hasta}: {n_largos} largos en {n_series} series, {n_shorts} shorts, {len(top)} referencias del radar")
    diseno = disenar(p, plan, n_series, n_shorts_radar, top)
    piezas = calendario(p, plan, diseno, desde, hasta)
    out = {"perfil": a.perfil, "canal": p["canal"], "plan": plan, "desde": desde.isoformat(), "hasta": hasta.isoformat(), "generado": dt.datetime.now().isoformat(timespec="seconds"),
           "series": diseno["series"], "vivos": diseno.get("vivos", []), "comunidad": diseno.get("comunidad", []), "piezas": piezas, "proyeccion": proyeccion(plan, piezas, desde, hasta)}
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
