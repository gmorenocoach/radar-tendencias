"""
Informe de competencia por CANAL (no por video): para los 5 canales con más virales del radar, cómo publican y qué venden,
y un plan de réplica para nosotros.

    python -m fabrica.competencia --perfil equilibrate_es [--n 5]
    python -m fabrica.competencia --todos

Cuota: ≈ 3 unidades por canal. Salida: data/competencia_<perfil>.json (pestaña Canales de la página).
"""
import argparse, collections, datetime as dt, json, os, re, statistics, sys
import requests
from .comun import cargar_env, ROOT, claude, estilo, canal_de, perfil as cargar_perfil, guardar_json, MOCK

sys.path.insert(0, str(ROOT))
from radar import segundos, detectar_promocion, tiene_numero  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/"
DATA = ROOT / "data"
DIAS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]


def get(recurso, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    r = requests.get(API + recurso, params=params, timeout=30)
    if r.status_code == 404:
        return {"items": []}
    r.raise_for_status()
    return r.json()


def ultimos_videos(canal_id, n=30):
    if MOCK:
        return [{"id": f"v{i}", "titulo": f"5 señales de que {i}", "descripcion": "clase gratuita en wa.me/123", "tags": [], "publicado": f"2026-10-{(i % 28) + 1:02d}T19:00:00Z",
                 "vistas": 1000 * (i + 1), "likes": 50, "comentarios": 5, "duracion_s": 900 if i % 3 else 50, "miniatura": ""} for i in range(n)]
    r = get("channels", part="snippet,statistics,contentDetails,brandingSettings", id=canal_id)
    it = (r.get("items") or [None])[0]
    if not it:
        return []
    up = it["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = [x["snippet"]["resourceId"]["videoId"] for x in get("playlistItems", part="snippet", playlistId=up, maxResults=n).get("items", [])]
    out = []
    if ids:
        for v in get("videos", part="snippet,statistics,contentDetails", id=",".join(ids)).get("items", []):
            sn, st = v["snippet"], v.get("statistics", {})
            th = sn.get("thumbnails", {})
            out.append({"id": v["id"], "titulo": sn["title"], "descripcion": sn.get("description", ""), "tags": sn.get("tags") or [], "publicado": sn["publishedAt"],
                        "vistas": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0) or 0), "comentarios": int(st.get("commentCount", 0) or 0),
                        "duracion_s": segundos(v["contentDetails"]["duration"]), "miniatura": (th.get("maxres") or th.get("high") or {}).get("url", "")})
    return out


def perfil_canal(c, vids):
    """Métricas de publicación de un canal a partir de sus últimos videos."""
    if not vids:
        return {}
    fechas = sorted(dt.datetime.fromisoformat(v["publicado"].replace("Z", "+00:00")) for v in vids)
    semanas = max((fechas[-1] - fechas[0]).days / 7, 1)
    shorts = [v for v in vids if v["duracion_s"] <= 180]; largos = [v for v in vids if v["duracion_s"] > 180]
    horas = collections.Counter((f.hour - 5) % 24 for f in fechas)       # hora Bogotá
    dias = collections.Counter(DIAS[f.weekday()] for f in fechas)
    promos = [detectar_promocion(v["titulo"], v["descripcion"], v["tags"]) for v in vids]
    top = sorted(vids, key=lambda v: -v["vistas"])[:5]
    med = statistics.median(v["vistas"] for v in vids)
    return {"videos_analizados": len(vids), "videos_por_semana": round(len(vids) / semanas, 1), "pct_shorts": round(100 * len(shorts) / len(vids)),
            "duracion_media_largos_min": round(statistics.mean(v["duracion_s"] for v in largos) / 60, 1) if largos else 0,
            "duracion_media_shorts_s": round(statistics.mean(v["duracion_s"] for v in shorts)) if shorts else 0,
            "mediana_vistas": med, "vistas_top": top[0]["vistas"], "outlier_top": round(top[0]["vistas"] / med, 1) if med else 0,
            "engagement_medio": round(statistics.mean((v["likes"] + v["comentarios"]) / max(v["vistas"], 1) for v in vids), 4),
            "horas_publicacion": [f"{h:02d}:00" for h, _ in horas.most_common(3)], "dias_publicacion": [d for d, _ in dias.most_common(3)],
            "pct_titulos_con_numero": round(100 * sum(tiene_numero(v["titulo"]) for v in vids) / len(vids)),
            "pct_videos_con_oferta": round(100 * sum(p["promociona"] for p in promos) / len(vids)),
            "ofertas": sorted({t for p in promos for t in p["tipos"]}), "plataformas": sorted({t for p in promos for t in p["plataformas"]}),
            "top5": [{"titulo": v["titulo"], "vistas": v["vistas"], "duracion_s": v["duracion_s"], "url": f"https://www.youtube.com/watch?v={v['id']}", "miniatura": v["miniatura"]} for v in top],
            "titulos": [v["titulo"] for v in vids]}


def informe(perfil_id, n=5):
    p = cargar_perfil(perfil_id); canal = canal_de(perfil_id)
    radar = json.loads((DATA / f"{perfil_id}.json").read_text()) if (DATA / f"{perfil_id}.json").exists() else {"videos": [], "canales": []}
    canales = sorted(radar.get("canales", []), key=lambda c: (-c.get("n_virales", 0), -c.get("mediana_vistas_recientes", 0)))[:n]
    if MOCK and not canales:
        canales = [{"canal_id": "UCx", "canal": "Canal demo", "suscriptores": 5000, "pais": "MX", "n_virales": 4}]
    fichas = []
    for c in canales:
        vids = ultimos_videos(c["canal_id"])
        f = {"canal_id": c["canal_id"], "canal": c["canal"], "url": f"https://www.youtube.com/channel/{c['canal_id']}", "suscriptores": c.get("suscriptores"), "pais": c.get("pais", ""),
             "n_virales_radar": c.get("n_virales", 0), **perfil_canal(c, vids)}
        fichas.append(f)
        print(f"  {c['canal']}: {f.get('videos_por_semana')} v/sem · {f.get('pct_shorts')} % shorts · mediana {f.get('mediana_vistas')} · oferta {f.get('pct_videos_con_oferta')} %")
    resumen = [{k: f.get(k) for k in ("canal", "suscriptores", "videos_por_semana", "pct_shorts", "duracion_media_largos_min", "mediana_vistas", "outlier_top", "engagement_medio",
                                       "horas_publicacion", "dias_publicacion", "pct_titulos_con_numero", "pct_videos_con_oferta", "ofertas", "plataformas")} | {"titulos": f.get("titulos", [])[:20]} for f in fichas]
    user = f"""Canal nuestro: {p['canal']} ({p['idioma']}). Informe de {len(fichas)} canales competidores del nicho (métricas reales de sus últimos 30 videos):
{json.dumps(resumen, ensure_ascii=False)}

Entrega un análisis comparativo accionable: (1) fórmulas de título que repiten (con 3 ejemplos reales y la plantilla), (2) qué formato y cadencia les funciona,
(3) qué venden y cómo cierran, (4) qué NO está haciendo nadie (hueco), (5) plan de réplica para nosotros en 5 acciones concretas para las próximas 2 semanas,
(6) 6 títulos nuevos para nosotros con esas plantillas (sin copiar).
REGLAS DE FORMATO: dentro de los textos usa comillas angulares «» o ninguna, NUNCA comillas dobles " (rompen el JSON). Textos cortos: cita ≤ 15 palabras, gancho ≤ 20 palabras, plantilla ≤ 12 palabras. Devuelve el JSON completo con TODAS las claves pedidas. Responde SOLO JSON:
{{"formulas_titulo": [{{"plantilla": "..", "ejemplos": ["..", "..", ".."]}}], "formato_y_cadencia": "..", "como_venden": "..", "hueco": "..",
 "plan_replica": ["..", "..", "..", "..", ".."], "titulos_propuestos": [{{"titulo": "..", "formato": "short|largo"}}]}}"""
    mock = {"formulas_titulo": [{"plantilla": "N señales de que X", "ejemplos": ["5 señales de que 1"]}], "formato_y_cadencia": "largos de 15 min, 3/sem", "como_venden": "WhatsApp",
            "hueco": "nadie usa personaje", "plan_replica": ["a", "b", "c", "d", "e"], "titulos_propuestos": [{"titulo": "3 señales de que te quedas por costumbre", "formato": "short"}]}
    an = claude(estilo(canal), user, mock=mock, max_tokens=6000)
    if not all(k in an for k in ("formulas_titulo", "plan_replica", "titulos_propuestos")):
        print(f"  ! análisis incompleto ({list(an)}); reintentando")
        an = claude(estilo(canal), user + "\n\nTu intento anterior quedó incompleto o con JSON roto. Textos cortos, sin comillas dobles dentro de los textos, y TODAS las claves.", mock=mock, max_tokens=6000)
    out = {"perfil": perfil_id, "canal": p["canal"], "generado": dt.datetime.now().isoformat(timespec="seconds"), "canales": fichas, "analisis": an}
    for f in fichas:
        f.pop("titulos", None)
    guardar_json(DATA / f"competencia_{perfil_id}.json", out)
    print(f"  → data/competencia_{perfil_id}.json")


def main():
    cargar_env()
    ap = argparse.ArgumentParser(); ap.add_argument("--perfil", default=""); ap.add_argument("--todos", action="store_true"); ap.add_argument("--n", type=int, default=5)
    a = ap.parse_args()
    perfiles = [a.perfil] if a.perfil else ([q["id"] for q in json.loads((ROOT / "config/perfiles.json").read_text())["perfiles"] if q["id"].endswith("_es")] if a.todos else [])
    if not perfiles:
        sys.exit("Indica --perfil o --todos")
    for pid in perfiles:
        print(f"=== Competencia {pid}")
        try:
            informe(pid, a.n)
        except Exception as e:
            print(f"  ! {pid}: {e}")


if __name__ == "__main__":
    main()
