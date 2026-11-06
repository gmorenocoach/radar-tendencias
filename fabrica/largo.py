"""
Motor de videos largos (8–20 min) con Germancho: guion por capítulos → ambientes → voz por capítulo → escenas → render 16:9.

    python -m fabrica.largo --perfil soyintegral_es --video_id XXXX --minutos 15
    python -m fabrica.largo --perfil soyintegral_es --tema "qué pasa en tu cuerpo si dejas el azúcar" --minutos 12
    FABRICA_MOCK=1 python -m fabrica.largo --perfil soyintegral_es --tema prueba --minutos 2

Salida: producciones/<fecha>-<perfil>-largo-<slug>/ {ficha.json, guion.json, capitulos/*.mp3, voz.mp3, escenas/*.png, largo.mp4, miniatura_16x9.jpg, metadata.json}
El MP4 largo NO se guarda en el repositorio (tamaño); queda como artefacto del workflow y, más adelante, se sube a YouTube.
"""
import argparse, base64, datetime as dt, json, os, re, shutil, subprocess, sys, time
import requests
from PIL import Image, ImageStat
from .comun import cargar_env, OUT, ROOT, PAGES_BASE, slug, perfil as cargar_perfil, canal_de, guardar_json, claude, ESTILO_GERMANCHO, MOCK, CANAL_COLOR, POSES
from . import adn, voz, imagenes, render
from .indice import main as reconstruir_indice

PALABRAS_POR_MIN = 165


def ambientes_de(canal):
    cfg = json.loads((ROOT / "config/ambientes.json").read_text())
    amb = dict(cfg["comunes"]); amb.update(cfg["por_canal"].get(canal, {}))
    return amb


# ----------------------------------------------------------------------------
# 1. Guion largo en dos pasos: estructura de capítulos → escenas por capítulo
# ----------------------------------------------------------------------------
def estructura(ficha, p, minutos, ambientes):
    canal = canal_de(p["id"])
    palabras = minutos * PALABRAS_POR_MIN
    user = f"""Canal: {p['canal']} · Idioma: {p['idioma']} · Video LARGO de {minutos} minutos (~{palabras} palabras habladas).
FICHA DE ADN del video de referencia (replica estructura y gancho, no el contenido):
{json.dumps(ficha['adn'], ensure_ascii=False)}

Diseña la estructura: gancho de 25–35 s que promete algo concreto y abre un bucle, 4–6 capítulos con mini-gancho al inicio de cada uno
(para que el espectador no se vaya), y un cierre de 40–60 s con resumen, Reto de hoy y CTA. Cada capítulo ocurre en UN ambiente de esta lista: {list(ambientes)}.
Responde SOLO JSON:
{{"titulo": "sin hashtags, máx 70 caracteres", "titulos_alternativos": ["..",".."], "promesa": "qué se lleva el espectador",
 "descripcion": "4–6 líneas con palabras clave, sin enlaces",
 "hashtags": ["#..", 5 a 8], "miniatura": {{"texto": "2–4 palabras", "emocion": "miedo|sorpresa|alegria|ira|tristeza|asco", "objeto": "...", "pose": "una de {list(POSES)}"}},
 "capitulos": [{{"n": 0, "titulo": "Gancho", "ambiente": "..", "palabras": 70, "objetivo": "..", "idea_clave": "≤ 6 palabras para pantalla"}},
               {{"n": 1, "titulo": "..", "ambiente": "..", "palabras": {palabras // 6}, "objetivo": "..", "idea_clave": ".."}}, "... hasta el cierre"],
 "reto_de_hoy": "acción concreta de < 5 minutos"}}"""
    mock = {"titulo": "Qué le pasa a tu cuerpo si dejas el azúcar 14 días", "titulos_alternativos": ["14 días sin azúcar: lo que nadie te cuenta"], "promesa": "entender los cambios reales",
            "descripcion": "Germancho te cuenta, día a día, qué cambia en tu cuerpo cuando dejas el azúcar.", "hashtags": ["#salud", "#azucar", "#habitos"],
            "miniatura": {"texto": "14 DÍAS SIN AZÚCAR", "emocion": "sorpresa", "objeto": "terrón de azúcar", "pose": "salto_sorpresa"},
            "capitulos": [{"n": 0, "titulo": "Gancho", "ambiente": "cocina", "palabras": 60, "objetivo": "abrir bucle", "idea_clave": "No es fuerza de voluntad"},
                          {"n": 1, "titulo": "Días 1–3", "ambiente": "cocina", "palabras": 90, "objetivo": "síntomas", "idea_clave": "El cerebro protesta"},
                          {"n": 2, "titulo": "Días 4–7", "ambiente": "consultorio", "palabras": 90, "objetivo": "energía", "idea_clave": "La energía se estabiliza"},
                          {"n": 3, "titulo": "Cierre", "ambiente": "cafeteria", "palabras": 60, "objetivo": "reto", "idea_clave": "Reto de hoy"}],
            "reto_de_hoy": "Lee la etiqueta de lo primero que comas mañana."}
    e = claude(ESTILO_GERMANCHO, user, mock=mock, max_tokens=4000)
    for c in e["capitulos"]:
        if c.get("ambiente") not in ambientes:
            c["ambiente"] = next(iter(ambientes))
    e["titulo"] = re.sub(r"\s*#\S+", "", e.get("titulo", "")).strip()
    return e


def escenas_capitulo(est, cap, p, anterior_resumen):
    user = f"""Video: «{est['titulo']}». Promesa: {est['promesa']}. Capítulo {cap['n']}: «{cap['titulo']}» · objetivo: {cap['objetivo']} · ambiente: {cap['ambiente']} · ~{cap['palabras']} palabras.
Lo dicho hasta ahora (resumen): {anterior_resumen or '(inicio del video)'}
Escribe el texto hablado de este capítulo dividido en escenas de 35–60 palabras (una idea por escena). Si es el capítulo 0, es el GANCHO: primera frase
que rompa una creencia o haga una pregunta incómoda, y promesa clara. Si es el último, cierra con resumen de 3 puntos, el Reto de hoy ({est['reto_de_hoy']})
y la invitación a comentar. Dentro de los textos no uses comillas dobles. Responde SOLO JSON:
{{"escenas": [{{"texto": "...", "emocion": "alegria|miedo|ira|tristeza|asco|sorpresa|sereno", "objeto": "objeto de apoyo", "pose": "una de {list(POSES)}",
               "prompt_visual": "english, short, what he does", "texto_en_pantalla": "≤ 6 palabras o vacío"}}], "resumen": "2 frases de lo dicho"}}"""
    mock = {"escenas": [{"texto": f"Texto de prueba del capítulo {cap['n']} escena uno con suficientes palabras para medir el tiempo de la voz y el ritmo general del video largo de prueba.", "emocion": "sereno", "objeto": "taza", "pose": "butaco_tazas", "prompt_visual": "holding a mug", "texto_en_pantalla": cap["idea_clave"]},
                        {"texto": f"Texto de prueba del capítulo {cap['n']} escena dos que continúa la idea anterior y añade un ejemplo cotidiano para sostener la atención del espectador.", "emocion": "alegria", "objeto": "cuaderno", "pose": "senalando", "prompt_visual": "pointing", "texto_en_pantalla": ""}],
            "resumen": "Se explicó la idea del capítulo."}
    r = claude(ESTILO_GERMANCHO, user, mock=mock, max_tokens=4000)
    for e in r["escenas"]:
        if e.get("pose") not in POSES:
            e["pose"] = "saludando"
    return r


# ----------------------------------------------------------------------------
# 2. Voz por capítulo (límite de caracteres por petición) y concatenación
# ----------------------------------------------------------------------------
def voz_capitulos(capitulos, out_dir, p):
    cap_dir = os.path.join(out_dir, "capitulos"); os.makedirs(cap_dir, exist_ok=True)
    palabras_total, limites_total, offset, archivos = [], [], 0.0, []
    for cap in capitulos:
        d = os.path.join(cap_dir, f"cap{cap['n']:02d}")
        mp3, palabras, limites, dur = voz.sintetizar(cap["escenas"], d, None, p["idioma"], voz_id=p.get("voz_id"))
        for w in palabras:
            palabras_total.append({"w": w["w"], "s": w["s"] + offset, "e": w["e"] + offset})
        for l in limites:
            limites_total.append({"n": len(limites_total) + 1, "inicio": l["inicio"] + offset, "fin": l["fin"] + offset})
        cap["inicio_s"] = round(offset, 1)
        archivos.append(mp3)
        offset += dur + 0.6
        cap["duracion_s"] = round(dur, 1)
    lista = os.path.join(cap_dir, "lista.txt")
    # pausa de 0,6 s entre capítulos
    sil = os.path.join(cap_dir, "sil.mp3")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", "0.6", "-q:a", "9", sil], check=True)
    with open(lista, "w") as f:
        for a in archivos:
            f.write(f"file '{os.path.abspath(a)}'\nfile '{os.path.abspath(sil)}'\n")
    out = os.path.join(out_dir, "voz.mp3")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c:a", "libmp3lame", "-q:a", "2", out], check=True)
    return out, palabras_total, limites_total, offset


# ----------------------------------------------------------------------------
# 3. Imágenes: base del capítulo (Germancho en el ambiente) → escenas derivadas
# ----------------------------------------------------------------------------
def imagen_base_capitulo(cap, canal, ambientes, path):
    color_en, _ = CANAL_COLOR[canal]
    if MOCK:
        imagenes._placeholder("saludando", path, 1920, 1080); return
    prompt = (f"This is Germancho. Keep this SAME character identical (head, hair, face, proportions, line style, {color_en} hoodie and sneakers). "
              f"Place him standing in {ambientes[cap['ambiente']]['prompt']}. Wide horizontal 16:9 composition, character on one side at about 60% of frame height, "
              f"plenty of clean space. Black ink on off-white paper; the only colors are the {color_en} of his clothes and small {color_en} accents. "
              "No text, no letters, no signature, no dark background.")
    res = imagenes._fal(imagenes.FAL_MODEL, {"prompt": prompt, "image_url": imagenes.maestro(canal), "aspect_ratio": "16:9", "output_format": "png", "safety_tolerance": "2"})
    imagenes._descargar(res["images"][0]["url"], path)


def imagen_escena_largo(esc, canal, base_url, path):
    color_en, _ = CANAL_COLOR[canal]
    if MOCK:
        imagenes._placeholder(esc.get("pose", "saludando"), path, 1920, 1080); return
    prompt = (f"Same character, same room and same drawing style as this image. Change only his pose and action: {imagenes.POSE_EN.get(esc.get('pose'), '')}; "
              f"{esc.get('prompt_visual', '')}; expression {imagenes.EMOCION_EN.get(esc.get('emocion', 'sereno'), 'calm')}; the {esc.get('objeto', 'object')} is drawn in {color_en}. "
              "Keep the horizontal 16:9 framing. No text, no letters, no labels, no signature, no dark background.")
    res = imagenes._fal(imagenes.FAL_MODEL, {"prompt": prompt, "image_url": base_url, "aspect_ratio": "16:9", "output_format": "png", "safety_tolerance": "2"})
    imagenes._descargar(res["images"][0]["url"], path)
    if ImageStat.Stat(Image.open(path).convert("L")).mean[0] < 170:
        res = imagenes._fal(imagenes.FAL_MODEL, {"prompt": prompt + " Bright white paper background only.", "image_url": base_url, "aspect_ratio": "16:9", "output_format": "png", "safety_tolerance": "2"})
        imagenes._descargar(res["images"][0]["url"], path)


def subir_temporal(path):
    """Las escenas derivadas necesitan una URL pública de la imagen base: se usa el almacenamiento de fal."""
    if MOCK:
        return "mock://" + path
    key = os.environ["FAL_KEY"]
    r = requests.post("https://rest.alpha.fal.ai/storage/upload/initiate", json={"file_name": os.path.basename(path), "content_type": "image/png"},
                      headers={"Authorization": f"Key {key}"}, timeout=60)
    if r.status_code == 200:
        j = r.json()
        with open(path, "rb") as f:
            requests.put(j["upload_url"], data=f, headers={"Content-Type": "image/png"}, timeout=120).raise_for_status()
        return j["file_url"]
    # alternativa: data URI (fal acepta imágenes en base64)
    b = base64.b64encode(open(path, "rb").read()).decode()
    return f"data:image/png;base64,{b}"


# ----------------------------------------------------------------------------
# 4. Render 16:9 con texto en pantalla, subtítulos discretos y música opcional
# ----------------------------------------------------------------------------
def ass_largo(palabras, textos_pantalla, canal, path):
    _, hexc = CANAL_COLOR[canal]
    col = render._ass_color(hexc)
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DejaVu Sans,46,{col},&H00FFFFFF,&H00201A16,&H80000000,-1,0,0,0,100,100,0,0,1,3,1,2,80,80,50,1
Style: Idea,DejaVu Sans,60,&H00201A16,&H00201A16,&H00F7F3EA,&H00F7F3EA,-1,0,0,0,100,100,0,0,3,14,0,7,70,70,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    for i in range(0, len(palabras), 4):
        g = palabras[i:i + 4]
        partes = [f"{{\\k{max(int(round((w['e'] - w['s']) * 100)), 1)}}}{w['w']}" for w in g]
        lineas.append(f"Dialogue: 0,{render._ts(g[0]['s'])},{render._ts(g[-1]['e'])},Sub,,0,0,0,,{' '.join(partes)}")
    for t in textos_pantalla:
        if t["texto"]:
            lineas.append(f"Dialogue: 1,{render._ts(t['inicio'])},{render._ts(min(t['fin'], t['inicio'] + 6))},Idea,,0,0,0,,{{\\fad(300,300)}}{t['texto'].upper()}")
    open(path, "w", encoding="utf-8").write(cab + "\n".join(lineas) + "\n")
    return path


def ensamblar_largo(pngs, limites, mp3, ass, out_mp4, work, musica=None):
    os.makedirs(work, exist_ok=True)
    clips = []
    for i, (png, lim) in enumerate(zip(pngs, limites)):
        dur = max(lim["fin"] - lim["inicio"], 1.0)
        clips.append(render.clip_escena(png, dur, os.path.join(work, f"clip{i:03d}.mp4"), w=1920, h=1080, zoom_in=(i % 2 == 0)))
    lista = os.path.join(work, "lista.txt")
    open(lista, "w").write("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
    video = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", video], check=True)
    ass_esc = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")
    cmd = ["ffmpeg", "-y", "-v", "error", "-i", video, "-i", mp3]
    if musica:
        cmd += ["-stream_loop", "-1", "-i", musica, "-filter_complex", "[2:a]volume=0.10[m];[1:a][m]amix=inputs=2:duration=first:dropout_transition=3[a]", "-map", "0:v", "-map", "[a]"]
    else:
        cmd += ["-map", "0:v", "-map", "1:a"]
    cmd += ["-vf", f"ass='{ass_esc}'", "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_mp4]
    subprocess.run(cmd, check=True)
    return out_mp4


def fmt_ts(s):
    s = int(s); return f"{s // 60}:{s % 60:02d}"


# ----------------------------------------------------------------------------
def main():
    cargar_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", required=True); ap.add_argument("--video_id", default=""); ap.add_argument("--tema", default="")
    ap.add_argument("--minutos", type=int, default=15)
    ap.add_argument("--economico", action="store_true", help="una imagen por capítulo (≈ 1/5 del costo); variedad por cámara y texto en pantalla")
    a = ap.parse_args()
    if not a.video_id and not a.tema:
        sys.exit("Indica --video_id o --tema")
    p = cargar_perfil(a.perfil); canal = canal_de(p["id"]); ambientes = ambientes_de(canal)
    t0 = time.time()
    print(f"=== Largo · {p['canal']} · {a.minutos} min · {'video ' + a.video_id if a.video_id else 'tema: ' + a.tema}{' · ECONÓMICO' if a.economico else ''}{' · MOCK' if MOCK else ''}")

    f = adn.ficha(a.video_id or None, a.tema or None, p["idioma"])
    est = estructura(f, p, a.minutos, ambientes)
    nombre = f"{dt.date.today():%Y%m%d}-{p['id']}-largo-{slug(est['titulo'], 40)}"
    d = OUT / nombre; (d / "escenas").mkdir(parents=True, exist_ok=True)
    guardar_json(d / "ficha.json", f)
    print(f"  Estructura: «{est['titulo']}» · {len(est['capitulos'])} capítulos")

    resumen = ""
    for cap in est["capitulos"]:
        r = escenas_capitulo(est, cap, p, resumen)
        cap["escenas"] = r["escenas"]; resumen = (resumen + " " + r.get("resumen", "")).strip()[-1200:]
        print(f"  Cap {cap['n']} «{cap['titulo']}» [{cap['ambiente']}]: {len(cap['escenas'])} escenas, {sum(len(e['texto'].split()) for e in cap['escenas'])} palabras")
    est["palabras"] = sum(len(e["texto"].split()) for c in est["capitulos"] for e in c["escenas"])
    guardar_json(d / "guion.json", est)

    mp3, palabras, limites, dur = voz_capitulos(est["capitulos"], str(d), p)
    print(f"  Voz: {dur / 60:.1f} min · {len(palabras)} palabras")

    pngs, textos = [], []
    k = 0
    for cap in est["capitulos"]:
        base = str(d / "escenas" / f"cap{cap['n']:02d}_base.png")
        imagen_base_capitulo(cap, canal, ambientes, base)
        base_url = subir_temporal(base) if not a.economico else ""
        for j, esc in enumerate(cap["escenas"]):
            png = str(d / "escenas" / f"cap{cap['n']:02d}_e{j + 1:02d}.png")
            if j == 0 or a.economico:
                shutil.copy(base, png)
            else:
                imagen_escena_largo(esc, canal, base_url, png)
            pngs.append(png)
            lim = limites[k] if k < len(limites) else {"inicio": 0, "fin": 1}
            texto_pantalla = esc.get("texto_en_pantalla", "") or (cap.get("idea_clave", "") if j == 0 else "")
            if a.economico and not texto_pantalla:
                texto_pantalla = " ".join(esc["texto"].split()[:6]) + "…"
            textos.append({"texto": texto_pantalla, "inicio": lim["inicio"], "fin": lim["fin"]})
            k += 1
        print(f"  Imágenes cap {cap['n']}: {len(cap['escenas'])}")

    m = est["miniatura"]
    textos_mini = [m["texto"]] + [t for t in est.get("titulos_alternativos", []) if len(t.split()) <= 5][:1]
    try:
        imagenes.miniatura_pro(canal, m.get("emocion", "sorpresa"), m.get("objeto", "taza"), textos_mini, str(d / "miniatura"), "16:9")
        os.replace(str(d / "miniatura.jpg"), str(d / "miniatura_16x9.jpg"))
        if os.path.exists(str(d / "miniatura_b.jpg")):
            os.replace(str(d / "miniatura_b.jpg"), str(d / "miniatura_16x9_b.jpg"))
        shutil.copy(str(d / "miniatura_16x9.jpg"), str(d / "miniatura.jpg"))
    except Exception as e:
        print(f"  ! miniatura pro falló ({e}); usando versión básica")
        imagenes.miniatura(pngs[0], m["texto"], canal, m.get("emocion", "sorpresa"), str(d / "miniatura.jpg"))
    musica = next((str(x) for x in (ROOT / "assets/musica").glob("*.mp3")), None) if (ROOT / "assets/musica").exists() else None
    ass = ass_largo(palabras, textos, canal, str(d / "subtitulos.ass"))
    mp4 = ensamblar_largo(pngs, limites[: len(pngs)], mp3, ass, str(d / "largo.mp4"), str(d / "_tmp"), musica)
    shutil.rmtree(d / "_tmp", ignore_errors=True)
    tam = os.path.getsize(mp4) / 1e6

    capitulos_txt = "\n".join(f"{fmt_ts(c['inicio_s'])} {c['titulo']}" for c in est["capitulos"])
    cfg = json.loads((ROOT / "config/perfiles.json").read_text()); enlaces = cfg.get("_enlaces", {})
    cta = "\n".join(l for l in (p.get("cta") or "").split("\n") if l.strip() and all(("{" + k + "}") not in l or v for k, v in enlaces.items()))
    for k_, v_ in enlaces.items():
        cta = cta.replace("{" + k_ + "}", v_)
    cta = "\n".join(l for l in cta.split("\n") if "{ENLACE_" not in l)
    meta = {"id": nombre, "perfil": p["id"], "canal": p["canal"], "formato": "largo", "modo": "economico" if a.economico else "completo", "fecha": dt.datetime.now().isoformat(timespec="seconds"),
            "titulo": est["titulo"], "titulos_alternativos": est.get("titulos_alternativos", []),
            "descripcion": est["descripcion"] + "\n\nCapítulos:\n" + capitulos_txt + ("\n\n" + cta if cta else "") + "\n\n" + " ".join(est["hashtags"]),
            "hashtags": est["hashtags"], "reto_de_hoy": est.get("reto_de_hoy", ""), "duracion_s": round(dur, 1), "tamano_mb": round(tam, 1),
            "capitulos": [{"n": c["n"], "titulo": c["titulo"], "inicio_s": c["inicio_s"], "ambiente": c["ambiente"]} for c in est["capitulos"]],
            "fuente": f["fuente"], "estado": "pendiente_aprobacion",
            "archivos": {"video": f"{nombre}/largo.mp4", "miniatura": f"{nombre}/miniatura.jpg", "miniatura_16x9": f"{nombre}/miniatura_16x9.jpg", "guion": f"{nombre}/guion.json", "ficha": f"{nombre}/ficha.json"},
            "video_en_repositorio": tam < 90, "nota": "" if tam < 90 else "El MP4 supera el límite de GitHub: descárgalo desde el artefacto del workflow (Actions → esta corrida → Artifacts).",
            "divulgacion_ia": "Marcar 'contenido alterado o sintético' al subir (voz e imágenes generadas con IA)."}
    guardar_json(d / "metadata.json", meta)
    reconstruir_indice()
    print(f"\nListo en {(time.time() - t0) / 60:.1f} min → {nombre}/largo.mp4 ({tam:.0f} MB, {dur / 60:.1f} min)")


if __name__ == "__main__":
    main()
