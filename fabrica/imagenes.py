"""Escenas con Germancho vía fal.ai (edición con imagen de referencia del libro) y miniatura."""
import os, shutil, textwrap
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .comun import MOCK, ROOT, PAGES_BASE, POSES, CANAL_COLOR, EMOCION_COLOR

FAL_MODEL = os.environ.get("FAL_MODEL", "fal-ai/flux-pro/kontext")   # edición guiada por imagen de referencia
FAL_FALLBACK = "fal-ai/flux/dev"

PROMPT_BASE = ("Keep this exact hand-drawn ink cartoon character and his scratchy pen-line style: inverted-triangle head, scribbled spiky hair, "
               "long thin neck, very long wire-thin legs, twig-like hands with long fingers, two black oval eyes. "
               "Change only: he wears a {color} hoodie with the hood down and {color} high-top sneakers with white soles; "
               "expression: {emocion}; {accion}; the {objeto} is drawn in {color}; everything else black ink on plain off-white paper; "
               "no text, no other colors, vertical 9:16 composition with the character large in frame, children's-book illustration.")
EMOCION_EN = {"alegria": "happy, big toothy grin", "miedo": "scared, wide eyes, raised brows", "ira": "angry, frowning brows", "tristeza": "sad, drooping eyes",
              "asco": "disgusted, tongue out", "sorpresa": "surprised, round eyes and open mouth", "sereno": "calm, soft smile"}


def _fal(model, payload):
    key = os.environ["FAL_KEY"]
    r = requests.post(f"https://fal.run/{model}", json=payload, timeout=300, headers={"Authorization": f"Key {key}", "Content-Type": "application/json"})
    if r.status_code != 200:
        raise RuntimeError(f"fal.ai {model} {r.status_code}: {r.text[:300]}")
    return r.json()


def _descargar(url, path):
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(path, "wb") as f:
            shutil.copyfileobj(r.raw, f)


def _placeholder(pose, path, w=1080, h=1920):
    """Modo simulado: pone la pose del libro sobre fondo blanco hueso en 9:16."""
    ref = Image.open(ROOT / "assets/germancho" / POSES[pose]).convert("RGB")
    lienzo = Image.new("RGB", (w, h), "#F7F3EA")
    ref.thumbnail((int(w * 0.85), int(h * 0.6)))
    lienzo.paste(ref, ((w - ref.width) // 2, (h - ref.height) // 2))
    lienzo.save(path)


def generar_escena(escena, canal, path):
    color_en, _ = CANAL_COLOR[canal]
    pose = escena.get("pose", "saludando")
    if MOCK:
        _placeholder(pose, path)
        return "mock"
    prompt = PROMPT_BASE.format(color=color_en, emocion=EMOCION_EN.get(escena.get("emocion", "sereno"), "calm"),
                                accion=escena.get("prompt_visual", ""), objeto=escena.get("objeto", "object"))
    ref_url = f"{PAGES_BASE}/assets/germancho/{POSES[pose]}"
    try:
        res = _fal(FAL_MODEL, {"prompt": prompt, "image_url": ref_url, "aspect_ratio": "9:16", "output_format": "png", "safety_tolerance": "2"})
    except Exception as e:
        print(f"  ! kontext falló ({e}); usando texto→imagen")
        res = _fal(FAL_FALLBACK, {"prompt": prompt, "image_size": "portrait_16_9", "num_inference_steps": 28, "output_format": "png"})
    _descargar(res["images"][0]["url"], path)
    return prompt


def _font(size, bold=True):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def miniatura(escena_png, texto, canal, emocion, out_path, size=(1080, 1920)):
    """Miniatura según la guía: fondo blanco hueso, Germancho grande, mancha pastel pequeña, 2–4 palabras, una en color del canal, esquina rasgada."""
    W, H = size
    _, hexc = CANAL_COLOR[canal]
    im = Image.new("RGB", (W, H), "#F7F3EA")
    dr = ImageDraw.Draw(im)
    # mancha de emoción
    mancha = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(mancha).ellipse((W * 0.15, H * 0.12, W * 0.85, H * 0.55), fill=EMOCION_COLOR.get(emocion, "#E8E2D6") + "AA")
    im.paste(mancha, (0, 0), mancha)
    # personaje
    per = Image.open(escena_png).convert("RGB")
    # recorte a lo que no es fondo para que quede grande
    gris = ImageOps.invert(per.convert("L")).point(lambda x: 255 if x > 25 else 0)
    bb = gris.getbbox() or (0, 0, per.width, per.height)
    per = per.crop(bb)
    escala = min(W * 0.95 / per.width, H * 0.62 / per.height)
    per = per.resize((int(per.width * escala), int(per.height * escala)))
    # fondo del recorte → transparente aproximado
    px = per.convert("RGBA")
    datos = [(r, g, b, 0) if r > 235 and g > 230 and b > 220 else (r, g, b, 255) for r, g, b, a in px.getdata()]
    px.putdata(datos)
    im.paste(px, ((W - px.width) // 2, int(H * 0.08)), px)
    # texto 2–4 palabras, una en color del canal
    palabras = texto.upper().split()[:4]
    f = _font(int(W * 0.17))
    y = int(H * 0.70)
    lineas = textwrap.wrap(" ".join(palabras), width=10) or [""]
    for i, linea in enumerate(lineas):
        ancho = dr.textlength(linea, font=f)
        x = (W - ancho) / 2
        for w in linea.split(" "):
            col = hexc if w == palabras[-1] else "#1b1410"
            dr.text((x, y), w, font=f, fill=col, stroke_width=6, stroke_fill="#F7F3EA")
            x += dr.textlength(w + " ", font=f)
        y += int(W * 0.19)
    # esquina rasgada (guiño al libro)
    dr.polygon([(W, H - 260), (W - 60, H - 210), (W - 110, H - 150), (W - 70, H - 90), (W - 130, H - 40), (W - 90, H), (W, H)], fill="#2B2420")
    im.save(out_path, quality=92)
    # versión 16:9
    horiz = Image.new("RGB", (1280, 720), "#F7F3EA")
    recorte = im.crop((0, int(H * 0.05), W, int(H * 0.05) + int(W * 720 / 1280 * 1.0)))
    recorte = recorte.resize((1280, 720))
    horiz.paste(recorte, (0, 0))
    horiz.save(out_path.replace(".jpg", "_16x9.jpg"), quality=92)
