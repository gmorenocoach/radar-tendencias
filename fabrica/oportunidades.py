"""
Radar de oportunidades: lo que la gente PREGUNTA en los comentarios (de los virales del nicho y de nuestro propio canal) → temas para producir.

    python -m fabrica.oportunidades --perfil equilibrate_es            # 20 virales del radar + nuestros últimos 15 videos
    python -m fabrica.oportunidades --todos

Cuota: 1 unidad por video (commentThreads) + 2 por nuestro canal. Salida: data/oportunidades_<perfil>.json (lo lee la página, pestaña Radar).
"""
import argparse, collections, datetime as dt, json, os, re, sys
import requests
from .comun import cargar_env, ROOT, claude, estilo, canal_de, perfil as cargar_perfil, guardar_json, MOCK

API = "https://www.googleapis.com/youtube/v3/"
DATA = ROOT / "data"
RUIDO = re.compile(r"^(gracias|amén|amen|hermoso|excelente|bendiciones|saludos|like|❤+|🙏+|👏+)[!. ]*$", re.I)


def get(recurso, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    r = requests.get(API + recurso, params=params, timeout=30)
    if r.status_code in (403, 404):
        return {"items": []}          # comentarios desactivados o cuota: seguir con el resto
    r.raise_for_status()
    return r.json()


def comentarios(video_id, n=100):
    if MOCK:
        return [{"texto": f"¿Y si mi pareja no quiere hablar del tema? ({video_id})", "likes": 12}, {"texto": "¿Cómo sé si es amor o costumbre?", "likes": 30},
                {"texto": "Gracias, hermoso video", "likes": 2}, {"texto": "¿Esto aplica también con los hijos adultos?", "likes": 8}]
    out = []
    r = get("commentThreads", part="snippet", videoId=video_id, maxResults=min(n, 100), order="relevance", textFormat="plainText")
    for it in r.get("items", []):
        s = it["snippet"]["topLevelComment"]["snippet"]
        t = (s.get("textDisplay") or "").strip()
        if len(t) < 12 or RUIDO.match(t):
            continue
        out.append({"texto": t[:400], "likes": int(s.get("likeCount", 0)), "respuestas": int(it["snippet"].get("totalReplyCount", 0))})
    return out


def canal_id_por_handle(handle):
    if MOCK or not handle:
        return ""
    r = get("channels", part="id", forHandle=handle.lstrip("@"))
    return ((r.get("items") or [{}])[0]).get("id", "")


def videos_del_canal(canal_id, n=15):
    if MOCK or not canal_id:
        return [{"video_id": "propio1", "titulo": "Nuestro video 1"}]
    r = get("channels", part="contentDetails", id=canal_id)
    up = (((r.get("items") or [{}])[0]).get("contentDetails", {}).get("relatedPlaylists", {}) or {}).get("uploads", "")
    if not up:
        return []
    r = get("playlistItems", part="snippet", playlistId=up, maxResults=n)
    return [{"video_id": it["snippet"]["resourceId"]["videoId"], "titulo": it["snippet"]["title"]} for it in r.get("items", [])]


def analizar(perfil_id, n_virales=20, n_propios=15):
    p = cargar_perfil(perfil_id); canal = canal_de(perfil_id)
    radar = json.loads((DATA / f"{perfil_id}.json").read_text()) if (DATA / f"{perfil_id}.json").exists() else {"videos": []}
    fuentes = []
    for v in radar["videos"][:n_virales]:
        cs = comentarios(v["video_id"])
        fuentes.append({"origen": "viral", "video_id": v["video_id"], "titulo": v["titulo"], "canal": v["canal"], "vistas": v["vistas"], "n": len(cs), "comentarios": cs[:40]})
    propio = canal_id_por_handle(p.get("handle", "")) or p.get("canal_id", "")
    for v in videos_del_canal(propio, n_propios):
        cs = comentarios(v["video_id"])
        fuentes.append({"origen": "propio", "video_id": v["video_id"], "titulo": v["titulo"], "canal": p["canal"], "n": len(cs), "comentarios": cs[:40]})
    total = sum(f["n"] for f in fuentes)
    print(f"  {len(fuentes)} videos · {total} comentarios útiles")
    # muestra para Claude: los más votados primero, con el título del video de donde vienen
    muestra = sorted(((c["likes"], f["titulo"][:60], c["texto"], f["origen"]) for f in fuentes for c in f["comentarios"]), reverse=True)[:220]
    user = f"""Canal: {p['canal']} · Idioma: {p['idioma']}. Estos son comentarios reales (likes · video · texto · origen) de videos virales del nicho y de nuestro canal:
{json.dumps([{"likes": l, "video": t, "texto": x, "origen": o} for l, t, x, o in muestra], ensure_ascii=False)}

Tarea: encuentra lo que la gente PREGUNTA o PIDE (dudas, objeciones, situaciones concretas), no los elogios. Agrupa en 8–12 temas.
Para cada tema: cuántos comentarios lo tocan (aprox.), una cita textual corta, y una propuesta de Short de Germancho (título ≤ 60 caracteres con fórmula probada, gancho de 1 frase, reto de hoy).
Marca "formato": "short" o "largo" según lo que amerite, y "urgencia": alta si se repite mucho o viene de nuestro propio canal.
Responde SOLO JSON: {{"temas": [{{"tema": "..", "menciones": 0, "cita": "..", "origen": "viral|propio|ambos", "titulo": "..", "gancho": "..", "reto": "..", "formato": "short|largo", "urgencia": "alta|media|baja"}}],
 "objeciones_a_la_oferta": ["lo que la gente dice que le impide actuar"], "respuestas_sugeridas": [{{"a": "tipo de comentario frecuente", "respuesta": "respuesta corta de Germancho (≤ 40 palabras)"}}]}}"""
    mock = {"temas": [{"tema": "amor o costumbre", "menciones": 14, "cita": "¿Cómo sé si es amor o costumbre?", "origen": "ambos", "titulo": "3 señales de que es costumbre, no amor", "gancho": "Si no sabes si es amor o costumbre, mira esto.", "reto": "Escribe qué extrañarías.", "formato": "short", "urgencia": "alta"}],
            "objeciones_a_la_oferta": ["no tengo tiempo"], "respuestas_sugeridas": [{"a": "¿Y si mi pareja no quiere?", "respuesta": "Empieza por ti: el reto es tuyo, no de los dos."}]}
    res = claude(estilo(canal), user, mock=mock, max_tokens=5000)
    out = {"perfil": perfil_id, "canal": p["canal"], "generado": dt.datetime.now().isoformat(timespec="seconds"), "videos_leidos": len(fuentes), "comentarios_leidos": total,
           "temas": res.get("temas", []), "objeciones_a_la_oferta": res.get("objeciones_a_la_oferta", []), "respuestas_sugeridas": res.get("respuestas_sugeridas", []),
           "fuentes": [{k: f[k] for k in ("origen", "video_id", "titulo", "n")} for f in fuentes]}
    guardar_json(DATA / f"oportunidades_{perfil_id}.json", out)
    print(f"  {len(out['temas'])} temas → data/oportunidades_{perfil_id}.json")
    return out


def main():
    cargar_env()
    ap = argparse.ArgumentParser(); ap.add_argument("--perfil", default=""); ap.add_argument("--todos", action="store_true")
    a = ap.parse_args()
    perfiles = [a.perfil] if a.perfil else ([q["id"] for q in json.loads((ROOT / "config/perfiles.json").read_text())["perfiles"] if q["id"].endswith("_es") and not q["id"].startswith("mercado")] if a.todos else [])
    if not perfiles:
        sys.exit("Indica --perfil o --todos")
    for pid in perfiles:
        print(f"=== Oportunidades {pid}")
        try:
            analizar(pid)
        except Exception as e:
            print(f"  ! {pid}: {e}")


if __name__ == "__main__":
    main()
