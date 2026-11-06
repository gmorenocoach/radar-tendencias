"""
Recopilaciones: une varias producciones del MISMO canal en un video largo 16:9 (costo cero: solo ensamblaje).

    python -m fabrica.recopilar --perfil equilibrate_es --tipo short --titulo "5 verdades para soltar sin romperte"
    python -m fabrica.recopilar --perfil equilibrate_es --serie "El Café Frío" --titulo "El Café Frío: la serie completa"
    python -m fabrica.recopilar --perfil equilibrate_es --ids id1,id2,id3 --titulo "..."

Shorts (9:16) se montan sobre fondo desenfocado en 16:9. Entre piezas va una tarjeta con el título. Capítulos con tiempos en la descripción.
"""
import argparse, datetime as dt, json, os, shutil, subprocess, sys
from PIL import Image, ImageDraw
from .comun import cargar_env, OUT, ROOT, slug, perfil as cargar_perfil, canal_de, guardar_json, CANAL_COLOR, MOCK
from . import imagenes
from .indice import main as reconstruir_indice

W, H, FPS = 1920, 1080, 30


def tarjeta(titulo, subtitulo, canal, path, segundos=2.5):
    _, hexc = CANAL_COLOR[canal]
    im = Image.new("RGB", (W, H), "#F7F3EA"); dr = ImageDraw.Draw(im)
    dr.rectangle((0, 0, 28, H), fill=hexc)
    m = ROOT / "assets/germancho" / f"maestro_{canal}.png"
    if m.exists():
        g = imagenes._recortar_personaje(Image.open(m).convert("RGB")); gb = g.getbbox()
        if gb:
            g = g.crop(gb); esc = (H * 0.85) / g.height; g = g.resize((int(g.width * esc), int(g.height * esc)))
            im.paste(g, (W - g.width - 60, H - g.height), g)
    f = imagenes._font_manuscrita(int(H * 0.11)); f2 = imagenes._font(int(H * 0.045), bold=False)
    palabras = titulo.split(); lineas, actual = [], ""
    for w in palabras:
        p = (actual + " " + w).strip()
        if dr.textlength(p, font=f) <= W * 0.55 or not actual:
            actual = p
        else:
            lineas.append(actual); actual = w
    lineas.append(actual)
    y = int(H * 0.22)
    for l in lineas[:4]:
        dr.text((90, y), l, font=f, fill="#1b1410"); y += int(H * 0.125)
    if subtitulo:
        dr.text((90, y + 10), subtitulo, font=f2, fill=hexc)
    png = path + ".png"; im.save(png)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", png, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-t", str(segundos),
                    "-vf", f"scale={W}:{H},format=yuv420p", "-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-shortest", path], check=True)
    return path


def normalizar(src, dst):
    """Cualquier video → 1920x1080 30fps AAC estéreo. Vertical → fondo desenfocado."""
    p = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "csv=p=0", src], capture_output=True, text=True).stdout.strip().split(",")
    w, h = int(p[0]), int(p[1])
    if h > w:
        vf = (f"split[a][b];[a]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=20:5[bg];"
              f"[b]scale=-2:{H}[fg];[bg][fg]overlay=(W-w)/2:0,format=yuv420p")
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-filter_complex", vf]
    else:
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", f"scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,format=yuv420p"]
    cmd += ["-r", str(FPS), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "160k", dst]
    subprocess.run(cmd, check=True)
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", dst], capture_output=True, text=True).stdout.strip())


def fmt_ts(s):
    s = int(s); return f"{s // 60}:{s % 60:02d}"


def main():
    cargar_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", required=True); ap.add_argument("--titulo", required=True)
    ap.add_argument("--ids", default=""); ap.add_argument("--serie", default=""); ap.add_argument("--tipo", default="", choices=["", "short", "largo"])
    ap.add_argument("--max", type=int, default=8)
    a = ap.parse_args()
    p = cargar_perfil(a.perfil); canal = canal_de(p["id"])
    idx = json.loads((OUT / "index.json").read_text())["producciones"]
    cand = [x for x in idx if x["perfil"] == a.perfil and x.get("formato", "short") != "recopilacion"]
    if a.ids:
        ids = a.ids.split(","); cand = [x for x in cand if x["id"] in ids]; cand.sort(key=lambda x: ids.index(x["id"]))
    else:
        if a.tipo:
            cand = [x for x in cand if x.get("formato", "short") == a.tipo]
        if a.serie:
            cand = [x for x in cand if a.serie.lower() in (x.get("serie", "") + " " + x.get("titulo", "")).lower()]
        cand.sort(key=lambda x: x["fecha"])
    cand = [x for x in cand if (OUT / x["archivos"]["video"]).exists()][: a.max]
    if len(cand) < 2:
        sys.exit("Se necesitan al menos 2 producciones con video disponible en el repositorio")
    nombre = f"{dt.date.today():%Y%m%d}-{p['id']}-recopilacion-{slug(a.titulo, 40)}"
    d = OUT / nombre; work = d / "_tmp"; work.mkdir(parents=True, exist_ok=True)
    print(f"=== Recopilación · {p['canal']} · {len(cand)} piezas → «{a.titulo}»")
    partes, capitulos, t = [], [], 0.0
    partes.append(tarjeta(a.titulo, p["canal"], canal, str(work / "intro.mp4"), 3.0)); t += 3.0
    for i, x in enumerate(cand, 1):
        partes.append(tarjeta(x["titulo"], f"{i} de {len(cand)}", canal, str(work / f"card{i:02d}.mp4"), 2.0))
        capitulos.append({"n": i, "titulo": x["titulo"], "inicio_s": round(t, 1), "produccion_id": x["id"]}); t += 2.0
        dst = str(work / f"p{i:02d}.mp4"); dur = normalizar(str(OUT / x["archivos"]["video"]), dst); partes.append(dst); t += dur
        print(f"  {i}. {x['titulo'][:60]} ({dur:.0f} s)")
    lista = work / "lista.txt"; lista.write_text("".join(f"file '{os.path.abspath(q)}'\n" for q in partes))
    out = str(d / "largo.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", str(lista), "-c", "copy", "-movflags", "+faststart", out], check=True)
    shutil.rmtree(work, ignore_errors=True)
    tam = os.path.getsize(out) / 1e6
    # miniaturas (sin IA: rostro + versión clara simple con tarjeta)
    textos = [a.titulo, " ".join(a.titulo.split()[:3])]
    imagenes.miniatura_rostro(canal, "alegria", textos, str(d / "miniatura_16x9"), "16:9")
    tarjeta_img = Image.open(str(d / "miniatura_16x9_rostro.jpg")) if (d / "miniatura_16x9_rostro.jpg").exists() else None
    if tarjeta_img: tarjeta_img.save(str(d / "miniatura_16x9.jpg"), quality=92); tarjeta_img.save(str(d / "miniatura.jpg"), quality=92)
    cap_txt = "\n".join(f"{fmt_ts(c['inicio_s'])} {c['titulo']}" for c in capitulos)
    cfg = json.loads((ROOT / "config/perfiles.json").read_text()); enlaces = cfg.get("_enlaces", {})
    cta = "\n".join(l for l in (p.get("cta") or "").split("\n") if l.strip())
    for k, v in enlaces.items():
        cta = cta.replace("{" + k + "}", v)
    cta = "\n".join(l for l in cta.split("\n") if "{ENLACE_" not in l)
    meta = {"id": nombre, "perfil": p["id"], "canal": p["canal"], "formato": "recopilacion", "fecha": dt.datetime.now().isoformat(timespec="seconds"),
            "titulo": a.titulo, "titulos_alternativos": [], "descripcion": f"{a.titulo}. Germancho reúne en un solo video {len(cand)} piezas para verlas seguidas.\n\nCapítulos:\n{cap_txt}" + ("\n\n" + cta if cta else "") + "\n\n#germancho #cafeconproposito",
            "hashtags": ["#germancho"], "reto_de_hoy": "", "duracion_s": round(t, 1), "tamano_mb": round(tam, 1), "capitulos": capitulos, "fuente": {"recopila": [x["id"] for x in cand]},
            "estado": "pendiente_aprobacion", "video_en_repositorio": tam < 90, "nota": "" if tam < 90 else "El MP4 supera 90 MB: descárgalo desde el artefacto del workflow.",
            "archivos": {"video": f"{nombre}/largo.mp4", "miniatura": f"{nombre}/miniatura.jpg", "miniatura_16x9": f"{nombre}/miniatura_16x9.jpg", "guion": "", "ficha": "",
                         "miniaturas": [f"{nombre}/{x}" for x in sorted(os.listdir(d)) if x.startswith("miniatura") and x.endswith(".jpg")]},
            "divulgacion_ia": "Marcar 'contenido alterado o sintético' al subir (voz e imágenes generadas con IA)."}
    guardar_json(d / "metadata.json", meta); reconstruir_indice()
    print(f"\nListo → {nombre}/largo.mp4 ({tam:.0f} MB, {t / 60:.1f} min)")


if __name__ == "__main__":
    main()
