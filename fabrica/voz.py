"""Voz con ElevenLabs (con marcas de tiempo por carácter → palabras) para subtítulos sincronizados."""
import base64, json, os, subprocess
import requests
from .comun import MOCK

API = "https://api.elevenlabs.io/v1"


def elegir_voz(nombre_pref=None, idioma="es"):
    key = os.environ["ELEVENLABS_API_KEY"]
    voces = requests.get(f"{API}/voices", headers={"xi-api-key": key}, timeout=30).json().get("voices", [])
    if nombre_pref:
        for v in voces:
            if v["name"].lower() == nombre_pref.lower():
                return v["voice_id"]
    for v in voces:  # preferir voces etiquetadas en el idioma
        if (v.get("labels") or {}).get("language", "").startswith(idioma):
            return v["voice_id"]
    return voces[0]["voice_id"] if voces else "pNInz6obpgDQGcFmaJgB"


def _palabras_desde_alineacion(texto, chars, starts, ends):
    palabras, actual, ini = [], "", None
    for c, s, e in zip(chars, starts, ends):
        if c.isspace():
            if actual:
                palabras.append({"w": actual, "s": ini, "e": e})
                actual, ini = "", None
        else:
            if ini is None:
                ini = s
            actual += c
            fin = e
    if actual:
        palabras.append({"w": actual, "s": ini, "e": fin})
    return palabras


def sintetizar(escenas, out_dir, voz_nombre=None, idioma="es", velocidad=1.0, voz_id=None):
    """Genera voz.mp3 y devuelve lista de palabras con tiempos y los límites de cada escena."""
    os.makedirs(out_dir, exist_ok=True)
    mp3 = os.path.join(out_dir, "voz.mp3")
    texto = " ".join(e["texto"].strip() for e in escenas)
    if MOCK:
        # audio silencioso con duración estimada (2.6 palabras/seg) y tiempos sintéticos
        palabras_txt = texto.split()
        dur = max(len(palabras_txt) / 2.6, 5)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "anullsrc=r=44100:cl=mono", "-t", f"{dur:.2f}", "-q:a", "9", mp3], check=True)
        paso = dur / len(palabras_txt)
        palabras = [{"w": w, "s": i * paso, "e": (i + 1) * paso} for i, w in enumerate(palabras_txt)]
    else:
        key = os.environ["ELEVENLABS_API_KEY"]
        voice_id = voz_id or elegir_voz(voz_nombre, idioma)
        body = {"text": texto, "model_id": "eleven_multilingual_v2",
                "voice_settings": {"stability": 0.45, "similarity_boost": 0.8, "style": 0.35, "speed": velocidad}}
        r = requests.post(f"{API}/text-to-speech/{voice_id}/with-timestamps", json=body, timeout=300,
                          headers={"xi-api-key": key, "content-type": "application/json"})
        if r.status_code != 200:
            raise RuntimeError(f"ElevenLabs {r.status_code}: {r.text[:300]}")
        data = r.json()
        open(mp3, "wb").write(base64.b64decode(data["audio_base64"]))
        al = data.get("alignment") or data.get("normalized_alignment")
        palabras = _palabras_desde_alineacion(texto, al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"])
        dur = palabras[-1]["e"] if palabras else 0
    # límites de escena por conteo de palabras
    limites, idx = [], 0
    for e in escenas:
        n = len(e["texto"].split())
        trozo = palabras[idx: idx + n]
        if trozo:
            limites.append({"n": e.get("n", len(limites) + 1), "inicio": trozo[0]["s"], "fin": trozo[-1]["e"]})
        idx += n
    if limites:
        limites[-1]["fin"] = dur + 0.4
        for i in range(len(limites) - 1):   # sin huecos entre escenas
            limites[i]["fin"] = limites[i + 1]["inicio"]
    json.dump({"palabras": palabras, "escenas": limites, "duracion": dur}, open(os.path.join(out_dir, "voz.json"), "w"), ensure_ascii=False)
    return mp3, palabras, limites, dur
