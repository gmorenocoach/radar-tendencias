"""Utilidades compartidas de la fábrica: configuración, llamadas a Claude, modo simulado."""
import json, os, re, time, unicodedata
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "producciones"
MOCK = os.environ.get("FABRICA_MOCK") == "1"
PAGES_BASE = os.environ.get("PAGES_BASE", "https://gmorenocoach.github.io/radar-tendencias")

CANAL_COLOR = {  # color del buzo/tenis/objeto por canal (guía de Germancho)
    "equilibrate": ("coral", "#E8705F"),
    "mitribu": ("mustard yellow", "#D4A017"),
    "soyintegral": ("forest green", "#2E8B57"),
}
EMOCION_COLOR = {"alegria": "#F4E4A1", "miedo": "#B9A6C9", "ira": "#E9A08F", "tristeza": "#A9B9D6", "asco": "#B8CDB0", "sorpresa": "#F2C6C2", "sereno": "#E8E2D6"}
POSES = {  # pose del libro → archivo de referencia
    "saludando": "p036_saludando.png", "brazos_abiertos": "p076_brazos_abiertos.png", "letrero": "p040_letrero_felicidad.png",
    "senalando": "p026_senalando_paciencia.png", "salto_sorpresa": "p186_salto_sorpresa.png", "triste_acostado": "p145_tristeza_acostado.png",
    "escalera": "p096_escalera.png", "butaco_tazas": "p032_butaco_tazas.png", "agachado": "p082_agachado.png",
    "cambio": "p180_cambio.png", "aburrido": "p131_aburrido.png", "acostado_ira": "p120_acostado_ira.png",
}


def cargar_env():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def slug(texto, n=50):
    t = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    t = re.sub(r"[^a-zA-Z0-9]+", "-", t).strip("-").lower()
    return t[:n] or "produccion"


def canal_de(perfil_id):
    return perfil_id.split("_")[0]


def perfil(perfil_id):
    perfiles = json.loads((ROOT / "config/perfiles.json").read_text())["perfiles"]
    for p in perfiles:
        if p["id"] == perfil_id:
            return p
    raise SystemExit(f"Perfil desconocido: {perfil_id}")


def guardar_json(path, data):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1))


# ----------------------------------------------------------------------------
# Claude
# ----------------------------------------------------------------------------
def claude(system, user, max_tokens=4000, json_out=True, mock=None):
    """Llama a Claude y devuelve texto o JSON. En modo simulado devuelve `mock`."""
    if MOCK:
        return mock
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Falta ANTHROPIC_API_KEY")
    body = {"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-5"), "max_tokens": max_tokens,
            "system": system, "messages": [{"role": "user", "content": user}]}
    for intento in range(3):
        r = requests.post("https://api.anthropic.com/v1/messages", json=body, timeout=180,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        if r.status_code == 200:
            texto = "".join(b.get("text", "") for b in r.json()["content"])
            if not json_out:
                return texto
            m = re.search(r"\{.*\}", texto, re.S)
            return json.loads(m.group(0) if m else texto)
        if r.status_code in (429, 500, 529):
            time.sleep(5 * (intento + 1))
            continue
        raise RuntimeError(f"Claude {r.status_code}: {r.text[:300]}")
    raise RuntimeError("Claude: sin respuesta tras reintentos")


ESTILO_GERMANCHO = """Eres el guionista de "Germancho", el personaje de los libros de Germán Alonso Moreno (coach ontológico, "El Barista del Ser",
autor de "Café con Propósito" y "Vuelve M&3#d@ este libro"). Germancho habla en segunda persona, cercano, directo, con humor suave y
sin moralizar. Usa frases cortas, imágenes cotidianas (café, cuaderno, escalera, taza) y siempre termina con un "Reto de hoy":
una acción concreta de menos de 5 minutos que el espectador puede hacer ya y comentar. Nunca copia frases del video de referencia:
replica la estructura, el gancho y el ritmo, con contenido y punto de vista propios. Español neutro latinoamericano, tuteo.
Evita afirmaciones médicas o financieras absolutas; cuando el tema lo requiera, sugiere consultar a un profesional en una frase."""
