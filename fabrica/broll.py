"""
Modo B-roll: metraje de archivo gratuito (Pexels) por escena + Germancho narrando en una esquina + subtítulos.
Sin imágenes generadas: el costo del video es solo la voz.

Proveedores: PEXELS_API_KEY (pexels.com/api) y/o PIXABAY_API_KEY (pixabay.com/api/docs, la clave aparece al iniciar sesión).
Se prueba Pexels y luego Pixabay. Sin claves, cada escena usa un fondo del color del canal
con Germancho al centro (el video se produce igual, más sobrio).
Música opcional: deja MP3 en assets/musica/<canal>/ (biblioteca de audio de YouTube) y se mezcla al 10 %.
"""
import glob, hashlib, os, random, subprocess
import requests
from PIL import Image, ImageDraw
from .comun import ROOT, CANAL_COLOR, MOCK
from .render import FPS

CACHE = ROOT / ".cache_broll"
PALABRAS_RUIDO = {"germancho", "character", "cartoon", "triangle", "head", "hoodie", "sneakers", "mascot", "illustration"}


def _limpiar_query(q):
    """Las escenas traen prompts del personaje; para archivo real quitamos lo que describe a Germancho."""
    toks = [t for t in q.replace(",", " ").split() if t.lower() not in PALABRAS_RUIDO]
    return " ".join(toks[:6]) or "coffee cup table"


def _descargar(url, dest):
    if not dest.exists():
        with requests.get(url, stream=True, timeout=120) as d:
            d.raise_for_status()
            with open(dest, "wb") as fh:
                for ch in d.iter_content(1 << 16):
                    fh.write(ch)
    return str(dest)


def _pixabay(q, orientacion, dur_min):
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return None
    r = requests.get("https://pixabay.com/api/videos/", params={"key": key, "q": q, "per_page": 20, "safesearch": "true", "video_type": "film"}, timeout=30)
    if r.status_code != 200:
        print(f"  ! pixabay {r.status_code}: {r.text[:120]}"); return None
    hits = r.json().get("hits", [])
    def ok(h):
        v = h.get("videos", {}).get("medium") or h.get("videos", {}).get("small") or {}
        w, hh = v.get("width") or 0, v.get("height") or 0
        return w and hh and ((hh > w) == (orientacion == "portrait"))
    cand = [h for h in hits if ok(h) and h.get("duration", 0) >= dur_min] or [h for h in hits if ok(h)] or hits
    if not cand:
        return None
    h = random.choice(cand[:5]); v = h["videos"].get("medium") or h["videos"].get("small") or h["videos"].get("large")
    return _descargar(v["url"], CACHE / (hashlib.md5(v["url"].encode()).hexdigest()[:16] + ".mp4"))


def buscar_clip(query, orientacion="portrait", dur_min=3.0):
    """Devuelve la ruta local de un clip de archivo (Pexels o Pixabay) para la consulta, o None."""
    if MOCK or not (os.environ.get("PEXELS_API_KEY") or os.environ.get("PIXABAY_API_KEY")):
        return None
    CACHE.mkdir(exist_ok=True)
    q = _limpiar_query(query)
    try:
        c = _pexels(q, orientacion, dur_min)
        if c:
            return c
        return _pixabay(q, orientacion, dur_min)
    except Exception as e:
        print(f"  ! b-roll ({q}): {e}"); return None


def _pexels(q, orientacion, dur_min):
    key = os.environ.get("PEXELS_API_KEY")
    if not key:
        return None
    try:
        r = requests.get("https://api.pexels.com/videos/search", params={"query": q, "orientation": orientacion, "per_page": 8, "size": "medium"},
                         headers={"Authorization": key}, timeout=30)
        if r.status_code != 200:
            print(f"  ! pexels {r.status_code}: {r.text[:120]}"); return None
        vids = [v for v in r.json().get("videos", []) if v.get("duration", 0) >= dur_min] or r.json().get("videos", [])
        if not vids:
            return None
        v = random.choice(vids[:4])
        # archivo más liviano que cubra la resolución objetivo
        objetivo = 1080 if orientacion == "portrait" else 1280
        files = sorted(v["video_files"], key=lambda f: (f.get("width") or 0) * (f.get("height") or 0))
        ok = [f for f in files if (f.get("width") or 0) >= objetivo * 0.9 and f.get("file_type", "").endswith("mp4")] or [f for f in files if f.get("file_type", "").endswith("mp4")]
        f = ok[0] if ok else files[-1]
        return _descargar(f["link"], CACHE / (hashlib.md5(f["link"].encode()).hexdigest()[:16] + ".mp4"))
    except Exception as e:
        print(f"  ! pexels ({q}): {e}"); return None


def fondo_plano(canal, path, w, h):
    """Fondo oscuro con un degradado del color del canal (cuando no hay clip)."""
    _, hexc = CANAL_COLOR[canal]
    im = Image.new("RGB", (w, h), "#141210"); dr = ImageDraw.Draw(im)
    r, g, b = int(hexc[1:3], 16), int(hexc[3:5], 16), int(hexc[5:7], 16)
    for y in range(h):
        k = (y / h) ** 2 * 0.28
        dr.line([(0, y), (w, y)], fill=(int(20 + r * k), int(18 + g * k), int(16 + b * k)))
    im.save(path); return path


def clip_broll(src, dur, out, w, h):
    """Recorta/escala el clip a la escena (silencioso, 30 fps); si es corto, lo repite."""
    vf = f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={FPS},format=yuv420p,eq=brightness=-0.06:saturation=0.9"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-stream_loop", "-1", "-i", src, "-t", f"{dur:.3f}", "-an", "-vf", vf,
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out], check=True)
    return out


def germancho_png(canal, work, alto):
    """Recorte de la imagen maestra del canal (sin fondo crema) a la altura pedida."""
    from .imagenes import _recortar_personaje
    m = ROOT / "assets/germancho" / f"maestro_{canal}.png"
    if not m.exists():
        return None
    g = _recortar_personaje(Image.open(m).convert("RGB")); bb = g.getbbox()
    if not bb:
        return None
    g = g.crop(bb); esc = alto / g.height; g = g.resize((int(g.width * esc), int(alto)))
    p = os.path.join(work, "germancho.png"); g.save(p); return p


def musica_de(canal):
    ms = glob.glob(str(ROOT / "assets/musica" / canal / "*.mp3")) + glob.glob(str(ROOT / "assets/musica/*.mp3"))
    return random.choice(ms) if ms else None


def ensamblar(escenas, limites, mp3, ass, out_mp4, work, canal, w=1080, h=1920, con_germancho=True, musica=None):
    """escenas: lista de dicts con 'broll' (consulta) o 'prompt_visual'. Produce el MP4 con b-roll + Germancho + subtítulos."""
    os.makedirs(work, exist_ok=True)
    orient = "portrait" if h > w else "landscape"
    clips = []
    for i, (e, lim) in enumerate(zip(escenas, limites)):
        dur = max(lim["fin"] - lim["inicio"], 0.8)
        q = e.get("broll") or e.get("prompt_visual") or "coffee"
        src = buscar_clip(q, orient, dur)
        out = os.path.join(work, f"clip{i:03d}.mp4")
        if src:
            clip_broll(src, dur, out, w, h); e["broll_fuente"] = os.path.basename(src)
        else:
            from .render import clip_escena
            fondo = fondo_plano(canal, os.path.join(work, f"fondo{i:03d}.png"), w, h)
            clip_escena(fondo, dur, out, w=w, h=h, zoom_in=(i % 2 == 0)); e["broll_fuente"] = "fondo"
        clips.append(out)
    lista = os.path.join(work, "lista.txt")
    open(lista, "w").write("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
    video = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", video], check=True)
    ass_esc = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")
    g = germancho_png(canal, work, int(h * (0.20 if orient == "portrait" else 0.40))) if con_germancho else None
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", mp3]
    fc = []
    vin = "[0:v]"
    if g:
        cmd += ["-i", g]
        pos = "x=W*0.03:y=H-h-H*0.03" if orient == "portrait" else "x=W-w-W*0.02:y=H-h"
        fc.append(f"[0:v][2:v]overlay={pos}[v0]"); vin = "[v0]"
    fc.append(f"{vin}ass='{ass_esc}'[v]")
    if musica:
        cmd += ["-stream_loop", "-1", "-i", musica]
        fc.append(f"[{3 if g else 2}:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=3[a]")
        amap = "[a]"
    else:
        amap = "1:a"
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", amap, "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    return out_mp4
