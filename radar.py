#!/usr/bin/env python3
"""
Radar de tendencias — Fase 1
Detecta videos virales recientes publicados por canales pequeños (1k–100k subs)
que ya tienen una fórmula probada (≥ 3 videos virales), por nicho, idioma y formato.

Uso:
    YOUTUBE_API_KEY=AIza... python radar.py                # todos los perfiles
    YOUTUBE_API_KEY=AIza... python radar.py equilibrate_es # un perfil
    python radar.py --dry-run                              # sin llamadas reales (prueba)

Salida: data/<perfil>.json, data/index.json, data/cache_canales.json
Cuota: ~100 unidades por búsqueda + ~2 por canal analizado. Presupuesto diario: 10.000.
"""
import json, os, re, sys, time, math, statistics, datetime as dt
from pathlib import Path

import requests

try:
    from langdetect import detect_langs, DetectorFactory
    DetectorFactory.seed = 0
    HAVE_LANGDETECT = True
except Exception:
    HAVE_LANGDETECT = False

ROOT = Path(__file__).parent
DATA = ROOT / "data"
API = "https://www.googleapis.com/youtube/v3/"
PRESUPUESTO_CUOTA = int(os.environ.get("RADAR_CUOTA_MAX", "9000"))
CACHE_CANAL_DIAS = 7
HOY = dt.datetime.now(dt.timezone.utc)

# ----------------------------------------------------------------------------
# Cliente de la API con contador de cuota
# ----------------------------------------------------------------------------
class YouTube:
    COSTOS = {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}

    def __init__(self, key, log=print):
        self.key, self.cuota, self.log = key, 0, log
        self.agotado = False
        self.s = requests.Session()
        self.s.headers["User-Agent"] = "radar-tendencias/1.0"   # sesión limpia, sin cookies

    def get(self, recurso, **params):
        if self.agotado:
            return None
        costo = self.COSTOS[recurso]
        if self.cuota + costo > PRESUPUESTO_CUOTA:
            self.log(f"  ! presupuesto de cuota alcanzado ({self.cuota}); deteniendo llamadas")
            self.agotado = True
            return None
        params["key"] = self.key
        for intento in range(3):
            r = self.s.get(API + recurso, params=params, timeout=30)
            if r.status_code == 200:
                self.cuota += costo
                return r.json()
            err = r.json().get("error", {}) if r.headers.get("content-type", "").startswith("application/json") else {}
            razon = (err.get("errors") or [{}])[0].get("reason", "")
            if razon in ("quotaExceeded", "dailyLimitExceeded"):
                self.log("  ! cuota diaria de YouTube agotada")
                self.agotado = True
                return None
            if r.status_code == 404:                      # recurso inexistente (lista de subidas borrada, etc.)
                self.cuota += costo
                return {"items": []}
            if r.status_code == 429:                      # límite de velocidad: esperar y reintentar
                time.sleep(10 * (intento + 1))
                continue
            if r.status_code in (403, 400):
                raise RuntimeError(f"API {recurso} {r.status_code}: {err.get('message', r.text[:200])}")
            time.sleep(2 * (intento + 1))
        self.log(f"  ! {recurso} falló tras reintentos ({r.status_code}); se omite")
        return None


# ----------------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------------
DUR_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")

def segundos(iso):
    m = DUR_RE.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s

def fecha(iso):
    return dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))

def dias_desde(iso):
    return max((HOY - fecha(iso)).total_seconds() / 86400, 0.25)

def idioma_coincide(texto, snippet_lang, idioma):
    """True si el video parece estar en `idioma`. Lenient: solo rechaza cuando está seguro."""
    if snippet_lang:
        return snippet_lang.lower().startswith(idioma)
    if not HAVE_LANGDETECT or len(texto) < 20:
        return True
    try:
        top = detect_langs(texto)[0]
        return top.lang == idioma or top.prob < 0.90
    except Exception:
        return True

PROMO_PATRONES = [
    ("curso", r"\bcursos?\b|\bmasterclass\b|\bclase gratuita\b|\bworkshop\b|\btaller\b|\bprograma\b|\bformaci[oó]n\b|\bcourse\b|\bbootcamp\b"),
    ("mentoria", r"\bmentor[ií]as?\b|\bmentoring\b|\bcoaching\b|\bacompañamiento\b|\bsesi[oó]n 1 a 1\b|\bllamada gratuita\b|\bagenda(r)? (tu|una) (llamada|sesi[oó]n|cita)\b|\bbook a call\b"),
    ("comunidad", r"\bcomunidad\b|\bmembres[ií]a\b|\bpatreon\b|\bskool\b|\bdiscord\b|\btelegram\b|\bgrupo (privado|vip)\b|\bmembership\b"),
    ("libro", r"\bmi libro\b|\bebook\b|\be-book\b|\bgu[ií]a gratuita\b|\bpdf gratis\b|\bmy book\b"),
]
PROMO_PLATAFORMAS = ["hotmart", "kajabi", "teachable", "thinkific", "udemy", "domestika", "calendly", "wa.me", "whatsapp", "linktr.ee", "beacons.ai", "stan.store", "gumroad", "skool.com", "systeme.io", "clickfunnels", "typeform", "mailchimp", "manychat"]

def detectar_promocion(titulo, descripcion, tags):
    """Detecta si el video empuja una oferta (curso, mentoría, comunidad, libro) y por qué plataforma."""
    texto = " ".join([titulo, descripcion or "", " ".join(tags or [])]).lower()
    tipos = [t for t, rx in PROMO_PATRONES if re.search(rx, texto)]
    plataformas = [pl for pl in PROMO_PLATAFORMAS if pl in texto]
    cta = bool(re.search(r"link en (la )?(descripci[oó]n|bio|comentarios)|enlace en|inscr[ií]bete|reg[ií]strate|cupos? limitados?|descuento|precio|\$\s?\d|usd|link in (bio|description)|sign up|enroll", texto))
    return {"promociona": bool(tipos or plataformas), "tipos": tipos, "plataformas": plataformas, "cta": cta}

def relevancia(texto, palabras, excluir):
    """Nº de palabras clave del nicho presentes; -1 si aparece un término excluido."""
    t = texto.lower()
    if any(e.lower() in t for e in excluir):
        return -1
    return sum(1 for k in palabras if k.lower() in t)

def tiene_numero(titulo):
    return bool(re.search(r"\b\d{1,4}\b", titulo))

def chunks(xs, n=50):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]

def miniatura(snippet):
    t = snippet.get("thumbnails", {})
    for k in ("maxres", "standard", "high", "medium", "default"):
        if k in t:
            return t[k]["url"]
    return ""


# ----------------------------------------------------------------------------
# Núcleo del radar
# ----------------------------------------------------------------------------
class Radar:
    def __init__(self, yt, nichos, cache, log=print):
        self.yt, self.nichos, self.cache, self.log = yt, nichos, cache, log

    # --- 1. Búsqueda de candidatos --------------------------------------------
    def consultas(self, perfil):
        """Rota las semillas día a día para cubrir todo el nicho con pocas búsquedas."""
        nicho = self.nichos[perfil["nicho"]]
        semillas = []
        for sid in perfil["subnichos"]:
            sub = nicho["subnichos"].get(sid)
            if not sub:
                continue
            for q in sub["semillas"].get(perfil["idioma"], []):
                semillas.append((sid, q))
        if not semillas:
            return []
        offset = HOY.toordinal() % len(semillas)
        rotadas = semillas[offset:] + semillas[:offset]
        regiones = perfil.get("regiones") or [None]
        out = []
        for i, (sid, q) in enumerate(rotadas[: perfil.get("max_busquedas", 12)]):
            out.append((sid, q, regiones[i % len(regiones)]))
        return out

    def buscar(self, perfil):
        desde = (HOY - dt.timedelta(days=perfil["dias"])).strftime("%Y-%m-%dT%H:%M:%SZ")
        formato = perfil["formato"]
        encontrados = {}  # video_id -> (subnicho, consulta, region)
        for sid, q, region in self.consultas(perfil):
            params = dict(part="snippet", q=q, type="video", maxResults=50, order="viewCount",
                          publishedAfter=desde, relevanceLanguage=perfil["idioma"],
                          safeSearch="none")
            if region:
                params["regionCode"] = region
            # medium = 4–20 min, long = >20 min, short = <4 min (los Shorts se filtran luego por ≤60 s)
            params["videoDuration"] = "short" if formato == "shorts" else ("long" if HOY.toordinal() % 3 == 0 else "medium")
            res = self.yt.get("search", **params)
            time.sleep(0.5)
            if res is None:
                break
            n = 0
            for it in res.get("items", []):
                vid = it["id"].get("videoId")
                if vid and vid not in encontrados:
                    encontrados[vid] = (sid, q, region)
                    n += 1
            self.log(f"  búsqueda '{q}' [{region}] → {n} nuevos")
        return encontrados

    # --- 2. Detalles de videos ----------------------------------------------
    def videos(self, ids):
        out = {}
        for lote in chunks(list(ids)):
            res = self.yt.get("videos", part="snippet,statistics,contentDetails", id=",".join(lote), maxResults=50)
            if res is None:
                break
            for v in res.get("items", []):
                out[v["id"]] = v
        return out

    def ficha_video(self, v, subs, mediana):
        sn, st = v["snippet"], v.get("statistics", {})
        vistas = int(st.get("viewCount", 0))
        likes = int(st.get("likeCount", 0) or 0)
        coment = int(st.get("commentCount", 0) or 0)
        d = dias_desde(sn["publishedAt"])
        ratio = vistas / subs if subs else 0
        outlier = vistas / mediana if mediana else 0
        vpd = vistas / d
        return {
            "video_id": v["id"],
            "url": f"https://www.youtube.com/watch?v={v['id']}",
            "titulo": sn["title"],
            "canal_id": sn["channelId"],
            "canal": sn["channelTitle"],
            "publicado": sn["publishedAt"][:10],
            "dias": round(d, 1),
            "duracion_s": segundos(v.get("contentDetails", {}).get("duration")),
            "vistas": vistas,
            "likes": likes,
            "comentarios": coment,
            "ratio_vistas_subs": round(ratio, 1),
            "vistas_por_dia": round(vpd),
            "engagement": round((likes + coment) / vistas, 4) if vistas else 0,
            "outlier_canal": round(outlier, 1),
            "score": round(ratio * math.log10(1 + vpd), 1),
            "titulo_con_numero": tiene_numero(sn["title"]),
            "miniatura": miniatura(sn),
            "tags": (sn.get("tags") or [])[:15],
            "idioma_declarado": sn.get("defaultAudioLanguage") or sn.get("defaultLanguage") or "",
            "promocion": detectar_promocion(sn["title"], sn.get("description", ""), sn.get("tags")),
        }

    # --- 3. Canales -----------------------------------------------------------
    def canales(self, ids):
        out = {}
        for lote in chunks(list(ids)):
            res = self.yt.get("channels", part="snippet,statistics,contentDetails", id=",".join(lote), maxResults=50)
            if res is None:
                break
            for c in res.get("items", []):
                out[c["id"]] = c
        return out

    def analizar_canal(self, c, perfil):
        """Trae los últimos 25 videos del canal y cuenta cuántos son virales. Usa caché de 7 días."""
        cid = c["id"]
        cache = self.cache.get(cid)
        if cache and (HOY - fecha(cache["analizado"])).days < CACHE_CANAL_DIAS and cache.get("ratio_viral") == perfil["ratio_viral"]:
            return cache
        st = c.get("statistics", {})
        subs = int(st.get("subscriberCount", 0) or 0)
        uploads = c.get("contentDetails", {}).get("relatedPlaylists", {}).get("uploads")
        if not uploads:
            return None
        pl = self.yt.get("playlistItems", part="contentDetails", playlistId=uploads, maxResults=25)
        if pl is None:
            return None
        ids = [i["contentDetails"]["videoId"] for i in pl.get("items", [])]
        vids = self.videos(ids)
        if not vids:
            return None
        vistas = [int(v.get("statistics", {}).get("viewCount", 0)) for v in vids.values()]
        mediana = statistics.median(vistas) if vistas else 0
        fichas = [self.ficha_video(v, subs, mediana) for v in vids.values()]
        virales = [f for f in fichas if f["ratio_vistas_subs"] >= perfil["ratio_viral"] and (mediana == 0 or f["outlier_canal"] >= 3)]
        fechas = sorted(f["publicado"] for f in fichas)
        dias_rango = max((fecha(fechas[-1] + "T00:00:00Z") - fecha(fechas[0] + "T00:00:00Z")).days, 1) if len(fechas) > 1 else 30
        info = {
            "canal_id": cid,
            "canal": c["snippet"]["title"],
            "url": f"https://www.youtube.com/channel/{cid}",
            "pais": c["snippet"].get("country", ""),
            "suscriptores": subs,
            "videos_totales": int(st.get("videoCount", 0) or 0),
            "vistas_totales": int(st.get("viewCount", 0) or 0),
            "creado": c["snippet"].get("publishedAt", "")[:10],
            "mediana_vistas_recientes": round(mediana),
            "videos_por_semana": round(len(fichas) / dias_rango * 7, 1),
            "pct_shorts": round(sum(1 for f in fichas if f["duracion_s"] <= 60) / len(fichas), 2),
            "duracion_media_s": round(sum(f["duracion_s"] for f in fichas) / len(fichas)),
            "n_virales": len(virales),
            "virales": sorted(virales, key=lambda f: -f["score"])[:10],
            "ratio_viral": perfil["ratio_viral"],
            "analizado": HOY.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.cache[cid] = info
        return info

    # --- 4. Orquestación por perfil -------------------------------------------
    def correr(self, perfil):
        self.log(f"\n=== Perfil {perfil['id']} ({perfil['canal']}) — {perfil['nicho']} / {perfil['idioma']} / {perfil['formato']}")
        cuota0 = self.yt.cuota
        encontrados = self.buscar(perfil)
        self.log(f"  candidatos por búsqueda: {len(encontrados)}")
        detalles = self.videos(encontrados.keys())

        # filtro de formato, idioma y relevancia con el nicho
        nicho = self.nichos[perfil["nicho"]]
        palabras = nicho.get("palabras_clave", {}).get(perfil["idioma"], [])
        excluir = nicho.get("excluir", {}).get(perfil["idioma"], [])
        descartados_relevancia = 0
        validos = {}
        for vid, v in detalles.items():
            dur = segundos(v["contentDetails"]["duration"])
            if perfil["formato"] == "shorts" and dur > 60:
                continue
            if perfil["formato"] == "largo" and dur < 240:
                continue
            sn = v["snippet"]
            if not idioma_coincide(sn["title"] + ". " + sn.get("description", "")[:300],
                                   sn.get("defaultAudioLanguage") or sn.get("defaultLanguage"), perfil["idioma"]):
                continue
            texto = sn["title"] + " " + sn.get("description", "")[:500] + " " + " ".join(sn.get("tags") or [])
            rel = relevancia(texto, palabras, excluir)
            if palabras and rel < 1:
                descartados_relevancia += 1
                continue
            v["_relevancia"] = rel
            validos[vid] = v
        self.log(f"  tras filtro formato+idioma+relevancia: {len(validos)} (descartados por relevancia: {descartados_relevancia})")

        # canales en rango de suscriptores
        canales = self.canales({v["snippet"]["channelId"] for v in validos.values()})
        en_rango = {}
        for cid, c in canales.items():
            st = c.get("statistics", {})
            if st.get("hiddenSubscriberCount"):
                continue
            subs = int(st.get("subscriberCount", 0) or 0)
            if perfil["min_subs"] <= subs <= perfil["max_subs"]:
                en_rango[cid] = c
        self.log(f"  canales en rango {perfil['min_subs']}–{perfil['max_subs']}: {len(en_rango)} de {len(canales)}")

        # canales con fórmula probada (≥ N virales)
        aprobados = {}
        for cid, c in en_rango.items():
            info = self.analizar_canal(c, perfil)
            if info and info["n_virales"] >= perfil["min_virales_canal"]:
                aprobados[cid] = info
            if self.yt.agotado:
                break
        self.log(f"  canales con ≥{perfil['min_virales_canal']} virales: {len(aprobados)}")

        # videos finales: los encontrados por búsqueda cuyo canal fue aprobado y que son virales
        videos = []
        vistos = set()
        for vid, v in validos.items():
            cid = v["snippet"]["channelId"]
            if cid not in aprobados:
                continue
            info = aprobados[cid]
            f = self.ficha_video(v, info["suscriptores"], info["mediana_vistas_recientes"])
            if f["ratio_vistas_subs"] < perfil["ratio_viral"]:
                continue
            sid, q, region = encontrados[vid]
            f.update(subnicho=sid, consulta=q, region=region, origen="busqueda", relevancia=v.get("_relevancia", 0),
                     fuerte=f["engagement"] >= perfil.get("min_engagement", 0.04),
                     canal_subs=info["suscriptores"], canal_n_virales=info["n_virales"])
            videos.append(f); vistos.add(vid)
        # + los otros virales recientes de esos canales (dentro de la ventana de días)
        for cid, info in aprobados.items():
            for f in info["virales"]:
                if f["video_id"] in vistos or f["dias"] > perfil["dias"]:
                    continue
                dur = f["duracion_s"]
                if (perfil["formato"] == "shorts" and dur > 60) or (perfil["formato"] == "largo" and dur < 240):
                    continue
                texto = f["titulo"] + " " + " ".join(f.get("tags") or [])
                rel = relevancia(texto, palabras, excluir)
                if palabras and rel < 1:
                    continue
                g = dict(f, subnicho="", consulta="", region="", origen="canal", relevancia=rel,
                         fuerte=f["engagement"] >= perfil.get("min_engagement", 0.04),
                         canal_subs=info["suscriptores"], canal_n_virales=info["n_virales"])
                videos.append(g); vistos.add(f["video_id"])

        videos.sort(key=lambda f: -f["score"])
        canales_out = sorted(({k: v for k, v in i.items() if k != "virales"} for i in aprobados.values()),
                             key=lambda c: -c["n_virales"])
        return {
            "perfil": perfil,
            "generado": HOY.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "cuota_usada": self.yt.cuota - cuota0,
            "resumen": {"candidatos": len(encontrados), "validos": len(validos), "descartados_relevancia": descartados_relevancia,
                        "canales_en_rango": len(en_rango), "canales_aprobados": len(aprobados), "videos": len(videos),
                        "con_promocion": sum(1 for f in videos if f["promocion"]["promociona"]),
                        "fuertes": sum(1 for f in videos if f.get("fuerte"))},
            "videos": videos,
            "canales": canales_out,
        }


# ----------------------------------------------------------------------------
def main(argv):
    dry = "--dry-run" in argv
    ids = [a for a in argv if not a.startswith("--")]
    nichos = json.loads((ROOT / "config/nichos.json").read_text())["nichos"]
    perfiles = json.loads((ROOT / "config/perfiles.json").read_text())["perfiles"]
    if ids:
        perfiles = [p for p in perfiles if p["id"] in ids]
    DATA.mkdir(exist_ok=True)
    cache_path = DATA / "cache_canales.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}

    if dry:
        from tests.fake_api import FakeYouTube
        yt = FakeYouTube()
    else:
        key = os.environ.get("YOUTUBE_API_KEY")
        if not key:
            sys.exit("Falta YOUTUBE_API_KEY (variable de entorno o archivo .env)")
        yt = YouTube(key)

    radar = Radar(yt, nichos, cache)
    indice = {"actualizado": HOY.strftime("%Y-%m-%dT%H:%M:%SZ"), "perfiles": []}
    idx_path = DATA / "index.json"
    if idx_path.exists():
        prev = json.loads(idx_path.read_text()).get("perfiles", [])
        indice["perfiles"] = [p for p in prev if p["id"] not in {q["id"] for q in perfiles}]
    for p in perfiles:
        try:
            res = radar.correr(p)
        except RuntimeError as e:
            print(f"  ! error en {p['id']}: {e}")
            continue
        (DATA / f"{p['id']}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
        indice["perfiles"].append({"id": p["id"], "canal": p["canal"], "nicho": nichos[p["nicho"]]["nombre"],
                                   "idioma": p["idioma"], "formato": p["formato"], "generado": res["generado"],
                                   "videos": len(res["videos"]), "canales": len(res["canales"])})
        if yt.agotado:
            print("  cuota agotada; los perfiles restantes se correrán mañana")
            break
    indice["perfiles"].sort(key=lambda x: x["id"])
    indice["cuota_usada_hoy"] = yt.cuota
    idx_path.write_text(json.dumps(indice, ensure_ascii=False, indent=1))
    # caché: limpiar entradas viejas
    cache = {k: v for k, v in cache.items() if (HOY - fecha(v["analizado"])).days < 30}
    cache_path.write_text(json.dumps(cache, ensure_ascii=False))
    print(f"\nListo. Cuota usada: {yt.cuota} unidades. Archivos en {DATA}/")


if __name__ == "__main__":
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
    main(sys.argv[1:])
