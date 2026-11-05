"""Ficha de replicación (ADN) de un video de referencia: transcripción + metadatos → análisis con Claude."""
import json, os, re
import requests
from .comun import claude, MOCK

API = "https://www.googleapis.com/youtube/v3/"


def metadatos(video_id):
    if MOCK:
        return {"titulo": "La gente sigue pobre por esto", "descripcion": "#mentalidad #hábitos", "canal": "Canal demo",
                "vistas": 156516, "likes": 2000, "comentarios": 120, "publicado": "2026-11-01", "miniatura": "", "duracion": "PT58S", "tags": []}
    key = os.environ.get("YOUTUBE_API_KEY")
    r = requests.get(API + "videos", params=dict(part="snippet,statistics,contentDetails", id=video_id, key=key), timeout=30).json()
    it = (r.get("items") or [None])[0]
    if not it:
        raise SystemExit(f"Video no encontrado: {video_id}")
    sn, st = it["snippet"], it.get("statistics", {})
    th = sn.get("thumbnails", {})
    return {"titulo": sn["title"], "descripcion": sn.get("description", ""), "canal": sn["channelTitle"],
            "vistas": int(st.get("viewCount", 0)), "likes": int(st.get("likeCount", 0) or 0), "comentarios": int(st.get("commentCount", 0) or 0),
            "publicado": sn["publishedAt"][:10], "miniatura": (th.get("maxres") or th.get("high") or th.get("default") or {}).get("url", ""),
            "duracion": it["contentDetails"]["duration"], "tags": sn.get("tags") or []}


def transcripcion(video_id, idioma="es"):
    if MOCK:
        return "¿Sabes por qué la gente sigue pobre? No es por falta de dinero. Es por tres hábitos que repite todos los días sin darse cuenta..."
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        api = YouTubeTranscriptApi()
        try:
            t = api.fetch(video_id, languages=[idioma, "es", "en"])
        except Exception:
            lista = api.list(video_id)
            t = next(iter(lista)).fetch()
        return " ".join(s.text for s in t)
    except Exception as e:
        return ""


def ficha(video_id=None, tema=None, idioma="es"):
    """Devuelve la ficha de replicación. Si no hay video_id, construye una ficha mínima a partir del tema."""
    if video_id:
        meta = metadatos(video_id)
        trans = transcripcion(video_id, idioma)
        fuente = {"video_id": video_id, "url": f"https://www.youtube.com/watch?v={video_id}", **meta, "transcripcion_chars": len(trans)}
        user = f"""Analiza este video viral de YouTube y extrae su ADN para replicar su ESTRUCTURA (no su contenido).

TÍTULO: {meta['titulo']}
CANAL: {meta['canal']} · VISTAS: {meta['vistas']} · DURACIÓN: {meta['duracion']}
DESCRIPCIÓN: {meta['descripcion'][:800]}
TAGS: {', '.join(meta['tags'][:20])}
TRANSCRIPCIÓN: {trans[:6000] if trans else '(no disponible; infiere del título y la descripción)'}

Responde SOLO con JSON con estas claves:
{{"tema_central": "...", "promesa_del_titulo": "...", "gancho_primeros_segundos": "...", "tipo_de_gancho": "pregunta|dato|contradiccion|historia|lista",
 "estructura": [{{"bloque": "gancho|contexto|punto 1|...|cierre", "segundos_aprox": 0, "funcion": "..."}}],
 "ritmo": "frases por idea, velocidad, pausas", "tono": "...", "cta_final": "...", "formula_del_titulo": "patrón reutilizable, ej. 'N señales de que X'",
 "titulo_con_numero": true, "palabras_clave": ["..."], "emocion_dominante": "alegria|miedo|ira|tristeza|asco|sorpresa",
 "formula_miniatura": {{"rostro": "sí/no y emoción", "texto": "nº de palabras y estilo", "objeto": "...", "color_dominante": "..."}},
 "por_que_funciona": "2 frases", "riesgos_a_evitar": ["copiar frases", "..."]}}"""
    else:
        fuente = {"tema": tema}
        user = f"""No hay video de referencia. Construye la ficha de ADN ideal para un Short viral sobre el tema: "{tema}" en {idioma}.
Usa las fórmulas que mejor funcionan en YouTube para ese tipo de tema (gancho de contradicción o pregunta, lista corta, cierre con reto).
Responde SOLO con el mismo JSON de claves: tema_central, promesa_del_titulo, gancho_primeros_segundos, tipo_de_gancho, estructura, ritmo, tono,
cta_final, formula_del_titulo, titulo_con_numero, palabras_clave, emocion_dominante, formula_miniatura, por_que_funciona, riesgos_a_evitar."""
    mock = {"tema_central": "hábitos que mantienen a la gente pobre", "promesa_del_titulo": "descubrir la causa oculta", "gancho_primeros_segundos": "No es falta de dinero.",
            "tipo_de_gancho": "contradiccion", "estructura": [{"bloque": "gancho", "segundos_aprox": 3, "funcion": "romper creencia"}, {"bloque": "punto 1", "segundos_aprox": 12, "funcion": ""},
            {"bloque": "punto 2", "segundos_aprox": 12, "funcion": ""}, {"bloque": "punto 3", "segundos_aprox": 12, "funcion": ""}, {"bloque": "cierre", "segundos_aprox": 8, "funcion": "reto"}],
            "ritmo": "rápido, una idea por frase", "tono": "directo", "cta_final": "comenta", "formula_del_titulo": "la gente sigue X por esto", "titulo_con_numero": False,
            "palabras_clave": ["dinero", "hábitos", "mentalidad"], "emocion_dominante": "sorpresa",
            "formula_miniatura": {"rostro": "sí, sorpresa", "texto": "3 palabras", "objeto": "moneda", "color_dominante": "amarillo"}, "por_que_funciona": "Contradice una creencia común.", "riesgos_a_evitar": ["copiar frases"]}
    analisis = claude("Eres un analista de contenido viral de YouTube. Respondes solo JSON válido.", user, mock=mock)
    return {"fuente": fuente, "adn": analisis}
