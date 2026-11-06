"""Escenas con Germancho vía fal.ai (edición con imagen de referencia del libro) y miniatura."""
import os, shutil, textwrap
import requests
from PIL import Image, ImageDraw, ImageFont, ImageOps
from .comun import MOCK, ROOT, PAGES_BASE, POSES, CANAL_COLOR, EMOCION_COLOR

FAL_MODEL = os.environ.get("FAL_MODEL", "fal-ai/flux-pro/kontext/max")   # edición guiada por imagen de referencia
FAL_FALLBACK = "fal-ai/flux/dev"

PROMPT_BASE = ("This is Germancho, a hand-drawn scribbly ink character. PRESERVE EXACTLY his design: the head is a flat INVERTED TRIANGLE "
               "(wide at the top, pointed chin) with spiky scribbled hair on the top edge, two friendly open oval eyes drawn as outlines with a small dot pupil (NOT solid black eyes), a gentle smile, no nose, no ears; "
               "very long thin neck, stick-thin body, extremely long wire legs, twig hands with long fingers; loose multi-stroke pen lines. Do NOT redesign "
               "the face or head shape, do NOT make it a skull, alien or realistic head. "
               "Change ONLY his clothes and the scene: he wears a {color} hoodie (hood down) and {color} high-top sneakers with white soles; "
               "expression: {emocion}; {accion}; the {objeto} is drawn in {color}. Everything else is black ink on a plain flat off-white paper background. "
               "No dark background, no shading gradients, no signature, no watermark, no text, no extra colors. "
               "Vertical 9:16 composition, character large and centered, children's-book sketch illustration.")
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


POSE_EN = {"saludando": "standing and waving", "brazos_abiertos": "arms wide open", "letrero": "holding up a blank sign board",
           "senalando": "pointing forward with one long finger", "salto_sorpresa": "jumping with arms up", "triste_acostado": "lying on the floor, sad",
           "escalera": "climbing a tall ladder", "butaco_tazas": "sitting on a wooden stool", "agachado": "bent over looking down",
           "cambio": "arms stretched sideways", "aburrido": "slumped, bored", "acostado_ira": "lying down, annoyed"}


def maestro(canal):
    """Imagen maestra del canal (Germancho con buzo del color). Si no existe, se usa la pose del libro."""
    p = ROOT / "assets/germancho" / f"maestro_{canal}.png"
    return f"{PAGES_BASE}/assets/germancho/maestro_{canal}.png" if p.exists() else None


def generar_escena(escena, canal, path):
    color_en, _ = CANAL_COLOR[canal]
    pose = escena.get("pose", "saludando")
    if MOCK:
        _placeholder(pose, path)
        return "mock"
    prompt = PROMPT_BASE.format(color=color_en, emocion=EMOCION_EN.get(escena.get("emocion", "sereno"), "calm"),
                                accion=f"{POSE_EN.get(pose, '')}; {escena.get('prompt_visual', '')}", objeto=escena.get("objeto", "object"))
    prompt += " Absolutely no written words, letters, labels or captions anywhere in the image."
    ref_url = maestro(canal) or f"{PAGES_BASE}/assets/germancho/{POSES[pose]}"
    if maestro(canal):
        prompt = prompt.replace("This is Germancho, a hand-drawn scribbly ink character. PRESERVE EXACTLY his design:",
                                "This is Germancho. Keep this SAME character identical (same head, hair, face, proportions, line style, hoodie and sneakers) and only change his pose, expression and the object:")
    try:
        res = _fal(FAL_MODEL, {"prompt": prompt, "image_url": ref_url, "aspect_ratio": "9:16", "output_format": "png", "safety_tolerance": "2"})
    except Exception as e:
        print(f"  ! kontext falló ({e}); usando texto→imagen")
        res = _fal(FAL_FALLBACK, {"prompt": prompt, "image_size": "portrait_16_9", "num_inference_steps": 28, "output_format": "png"})
    _descargar(res["images"][0]["url"], path)
    # control de calidad: fondo oscuro → regenerar una vez insistiendo en papel blanco
    from PIL import ImageStat
    brillo = ImageStat.Stat(Image.open(path).convert("L")).mean[0]
    if brillo < 170:
        print(f"  ! escena oscura (brillo {brillo:.0f}); regenerando con fondo blanco")
        prompt2 = prompt + " IMPORTANT: the background must be plain bright white/off-white paper with nothing dark; no night scene, no black areas, no smoke."
        try:
            res = _fal(FAL_MODEL, {"prompt": prompt2, "image_url": ref_url, "aspect_ratio": "9:16", "output_format": "png", "safety_tolerance": "2"})
            _descargar(res["images"][0]["url"], path)
        except Exception as e:
            print(f"  ! reintento falló: {e}")
    return prompt


def _font(size, bold=True):
    for p in ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]:
        if os.path.exists(p):
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _font_manuscrita(size):
    for n in ["PermanentMarker-Regular.ttf", "CaveatBrush-Regular.ttf", "PatrickHandSC-Regular.ttf"]:
        p = ROOT / "assets/fonts" / n
        if p.exists() and p.stat().st_size > 1000:
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                pass
    return _font(size)


def imagen_miniatura(canal, emocion, objeto, path, aspecto="16:9"):
    """Imagen dedicada para miniatura: Germancho en primer plano, expresión exagerada, objeto en color del canal, fondo blanco hueso."""
    color_en, _ = CANAL_COLOR[canal]
    if MOCK:
        _placeholder("salto_sorpresa", path, 1920 if aspecto == "16:9" else 1080, 1080 if aspecto == "16:9" else 1920); return
    prompt = (f"This is Germancho. Keep this SAME character identical (head, hair, face, line style, {color_en} hoodie). YouTube thumbnail composition: "
              f"close-up of his head and shoulders filling the {'right' if aspecto == '16:9' else 'lower'} 60% of the frame, looking at the camera, exaggerated {EMOCION_EN.get(emocion, 'surprised')} "
              f"expression with very large expressive eyes and mouth, holding a {objeto} drawn in {color_en} near his face. Plain off-white paper background, "
              f"lots of empty space on the {'left' if aspecto == '16:9' else 'top'} for text. No text, no letters, no signature, no dark background, bold clean ink lines.")
    res = _fal(FAL_MODEL, {"prompt": prompt, "image_url": maestro(canal), "aspect_ratio": aspecto, "output_format": "png", "safety_tolerance": "2"})
    _descargar(res["images"][0]["url"], path)


def _rasgado(dr, W, H):
    pts = [(W, H - int(H * 0.22)), (W - int(W * 0.04), H - int(H * 0.18)), (W - int(W * 0.08), H - int(H * 0.13)), (W - int(W * 0.05), H - int(H * 0.08)),
           (W - int(W * 0.1), H - int(H * 0.035)), (W - int(W * 0.07), H), (W, H)]
    dr.polygon(pts, fill="#2B2420")


def miniatura_pro(canal, emocion, objeto, textos, out_base, aspecto="16:9"):
    """Miniatura final: imagen dedicada + mancha pastel + texto manuscrito (una palabra en color del canal) + esquina rasgada. Una salida por texto (variantes A/B)."""
    W, H = (1280, 720) if aspecto == "16:9" else (1080, 1920)
    _, hexc = CANAL_COLOR[canal]
    base_png = out_base + f"_base_{aspecto.replace(':', 'x')}.png"
    imagen_miniatura(canal, emocion, objeto, base_png, aspecto)
    per = Image.open(base_png).convert("RGB").resize((W, H))
    salidas = []
    for i, texto in enumerate([t for t in textos if t][:2]):
        im = Image.new("RGB", (W, H), "#F7F3EA")
        mancha = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if aspecto == "16:9":
            ImageDraw.Draw(mancha).ellipse((W * 0.42, -H * 0.1, W * 1.05, H * 0.95), fill=EMOCION_COLOR.get(emocion, "#E8E2D6") + "66")
        else:
            ImageDraw.Draw(mancha).ellipse((-W * 0.1, H * 0.38, W * 1.1, H * 1.02), fill=EMOCION_COLOR.get(emocion, "#E8E2D6") + "66")
        im.paste(mancha, (0, 0), mancha)
        # personaje con fondo blanco → transparente
        px = per.convert("RGBA"); datos = [(r, g, b, 0) if r > 232 and g > 226 and b > 214 else (r, g, b, 255) for r, g, b, a in px.getdata()]; px.putdata(datos)
        im.paste(px, (0, 0), px)
        dr = ImageDraw.Draw(im)
        palabras = texto.upper().split()[:4]
        if aspecto == "16:9":
            size = int(H * 0.19); maxw = int(W * 0.46); x0, y0 = int(W * 0.045), int(H * 0.16)
        else:
            size = int(W * 0.16); maxw = int(W * 0.9); x0, y0 = int(W * 0.05), int(H * 0.07)
        f = _font_manuscrita(size)
        # envolver por ancho
        lineas, actual = [], ""
        for w in palabras:
            prueba = (actual + " " + w).strip()
            if dr.textlength(prueba, font=f) <= maxw or not actual:
                actual = prueba
            else:
                lineas.append(actual); actual = w
        lineas.append(actual)
        destacada = palabras[-1]
        y = y0
        for linea in lineas:
            x = x0
            for w in linea.split(" "):
                col = hexc if w == destacada else "#1b1410"
                dr.text((x + 6, y + 6), w, font=f, fill="#F7F3EA")  # halo
                dr.text((x, y), w, font=f, fill=col, stroke_width=3, stroke_fill="#F7F3EA")
                x += dr.textlength(w + " ", font=f)
            y += int(size * 1.08)
        _rasgado(dr, W, H)
        out = out_base + ("" if i == 0 else "_b") + (".jpg" if aspecto == "16:9" else "_9x16.jpg")
        im.save(out, quality=92); salidas.append(out)
    return salidas


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
