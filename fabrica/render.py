"""Render del Short: imágenes con movimiento suave (Ken Burns) + voz + subtítulos palabra a palabra → MP4 1080x1920."""
import os, subprocess
from .comun import CANAL_COLOR

FPS = 30


def _ass_color(hexc):  # '#RRGGBB' → '&H00BBGGRR'
    r, g, b = hexc[1:3], hexc[3:5], hexc[5:7]
    return f"&H00{b}{g}{r}".upper()


def _ts(t):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def subtitulos_ass(palabras, canal, path, por_linea=3):
    """Grupos de 3 palabras; la palabra que suena se pinta del color del canal (karaoke \\k)."""
    _, hexc = CANAL_COLOR[canal]
    cab = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Sub,DejaVu Sans,78,{_ass_color(hexc)},&H00FFFFFF,&H00201A16,&H80000000,-1,0,0,0,100,100,0,0,1,5,2,2,60,60,560,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lineas = []
    for i in range(0, len(palabras), por_linea):
        grupo = palabras[i:i + por_linea]
        ini, fin = grupo[0]["s"], grupo[-1]["e"]
        partes = []
        for p in grupo:
            cs = max(int(round((p["e"] - p["s"]) * 100)), 1)
            partes.append(f"{{\\k{cs}}}{p['w'].upper()}")
        lineas.append(f"Dialogue: 0,{_ts(ini)},{_ts(fin)},Sub,,0,0,0,,{' '.join(partes)}")
    open(path, "w", encoding="utf-8").write(cab + "\n".join(lineas) + "\n")
    return path


def clip_escena(img, dur, out, w=1080, h=1920, zoom_in=True):
    frames = max(int(dur * FPS), 1)
    z = f"min(zoom+0.0009,1.12)" if zoom_in else f"if(eq(on,1),1.12,max(zoom-0.0009,1.0))"
    vf = (f"scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
          f"zoompan=z='{z}':d={frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={FPS},format=yuv420p")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", img, "-vf", vf, "-t", f"{dur:.3f}", "-r", str(FPS),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", out], check=True)
    return out


def ensamblar(escenas_png, limites, mp3, ass, out_mp4, work):
    os.makedirs(work, exist_ok=True)
    clips = []
    for i, (png, lim) in enumerate(zip(escenas_png, limites)):
        dur = max(lim["fin"] - lim["inicio"], 0.8)
        clips.append(clip_escena(png, dur, os.path.join(work, f"clip{i:02d}.mp4"), zoom_in=(i % 2 == 0)))
    lista = os.path.join(work, "lista.txt")
    open(lista, "w").write("".join(f"file '{os.path.abspath(c)}'\n" for c in clips))
    video = os.path.join(work, "video.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", video], check=True)
    ass_esc = os.path.abspath(ass).replace("\\", "/").replace(":", "\\:")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-i", mp3, "-vf", f"ass='{ass_esc}'",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", out_mp4], check=True)
    return out_mp4
