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
def claude(system, user, max_tokens=4000, json_out=True, mock=None, _intento=0, pensar=0):
    """Llama a Claude y devuelve texto o JSON. En modo simulado devuelve `mock`. Si el JSON no es válido, reintenta una vez."""
    if MOCK:
        return mock
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise SystemExit("Falta ANTHROPIC_API_KEY")
    body = {"model": os.environ.get("CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": max_tokens,
            "system": system, "messages": [{"role": "user", "content": user}]}
    if pensar:   # razonamiento acotado: el modelo puede pensar, pero siempre queda espacio para la respuesta
        body["thinking"] = {"type": "enabled", "budget_tokens": int(pensar)}; body["max_tokens"] = max(max_tokens, int(pensar) + 6000)
    for intento in range(3):
        r = requests.post("https://api.anthropic.com/v1/messages", json=body, timeout=180,
                          headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        if r.status_code == 200:
            rj = r.json()
            texto = "".join(b.get("text", "") for b in rj.get("content", []))
            if not texto.strip():
                print(f"  ! Claude devolvió texto vacío (stop_reason={rj.get('stop_reason')}); reintentando con más espacio")
                if _intento < 2:
                    return claude(system, user, max_tokens * 2, json_out, mock, _intento=_intento + 1, pensar=(pensar or 4000))
                raise RuntimeError("Claude: respuesta vacía tras reintentos")
            if not json_out:
                return texto
            try:
                return parsear_json(texto)
            except RuntimeError as e:
                if _intento < 2:
                    print(f"  ! respuesta no JSON ({texto[:120]!r}); reintentando ({_intento + 1})")
                    return claude(system, user + "\n\nRESPONDE ÚNICAMENTE con el objeto JSON pedido, sin texto antes ni después, sin bloques de código. Escapa las comillas dentro de los textos.",
                                  max_tokens, json_out, mock, _intento=_intento + 1, pensar=pensar)
                raise
        if r.status_code in (429, 500, 529):
            time.sleep(5 * (intento + 1))
            continue
        raise RuntimeError(f"Claude {r.status_code}: {r.text[:300]}")
    raise RuntimeError("Claude: sin respuesta tras reintentos")


def parsear_json(texto):
    """Extrae y repara el JSON de la respuesta (comillas sin escapar, comas finales, texto alrededor)."""
    m = re.search(r"\{.*\}", texto, re.S)
    bruto = m.group(0) if m else texto
    try:
        return json.loads(bruto)
    except json.JSONDecodeError:
        pass
    try:
        from json_repair import repair_json
        return json.loads(repair_json(bruto))
    except Exception as e:
        raise RuntimeError(f"JSON inválido de Claude: {e}\n{bruto[:500]}")


# ----------------------------------------------------------------------------
# Cerebro de marca (config/marca.json)
# ----------------------------------------------------------------------------
def marca():
    p = ROOT / "config/marca.json"
    return json.loads(p.read_text()) if p.exists() else {}


def enlaces():
    try:
        return json.loads((ROOT / "config/perfiles.json").read_text()).get("_enlaces", {})
    except Exception:
        return {}


def nivel_para(canal, tipo_contenido):
    m = marca()
    return m.get("nivel_por_canal", {}).get(canal, {}).get(tipo_contenido) or m.get("tipos_contenido", {}).get(tipo_contenido, {}).get("nivel", "club")


def oferta(nivel):
    """Oferta del nivel con su CTA resuelto. Devuelve {} si el nivel no existe; cta vacío si falta el enlace."""
    o = dict(marca().get("ofertas", {}).get(nivel) or {})
    if not o:
        return {}
    en = enlaces()
    cta = o.get("cta", "")
    for k, v in en.items():
        cta = cta.replace("{" + k + "}", v or "")
    o["enlace_resuelto"] = en.get(o.get("enlace", ""), "")
    o["cta_resuelto"] = "" if ("{ENLACE_" in cta or not o["enlace_resuelto"]) else cta
    o["nivel"] = nivel
    return o


def estilo(canal=None):
    """ESTILO_GERMANCHO + cerebro de marca (voz, palabras, posiciones del canal)."""
    m = marca().get("voz", {})
    if not m:
        return ESTILO_GERMANCHO
    partes = [ESTILO_GERMANCHO, "\nCEREBRO DE MARCA:", m.get("quien", "")]
    if m.get("como_suena"):
        partes.append("Cómo suena: " + "; ".join(m["como_suena"]) + ".")
    if m.get("palabras_propias"):
        partes.append("Palabras propias (úsalas con naturalidad, no todas a la vez): " + ", ".join(m["palabras_propias"]) + ".")
    if m.get("palabras_prohibidas"):
        partes.append("Palabras y promesas PROHIBIDAS: " + ", ".join(m["palabras_prohibidas"]) + ".")
    if m.get("nunca"):
        partes.append("Nunca: " + "; ".join(m["nunca"]) + ".")
    pos = m.get("posiciones", {})
    eje = {"equilibrate": "amor", "mitribu": "dinero", "soyintegral": "salud"}.get(canal or "", "")
    if eje and pos.get(eje):
        partes.append(f"Posición del canal ({eje}): {pos[eje]}")
    return "\n".join(partes)


ESTILO_GERMANCHO = """Eres el guionista de "Germancho", el personaje de los libros de Germán Alonso Moreno (coach ontológico, "El Barista del Ser",
autor de "Café con Propósito" y "Vuelve M&3#d@ este libro"). Germancho habla en segunda persona, cercano, directo, con humor suave y
sin moralizar. Usa frases cortas, imágenes cotidianas (café, cuaderno, escalera, taza) y siempre termina con un "Reto de hoy":
una acción concreta de menos de 5 minutos que el espectador puede hacer ya y comentar. Nunca copia frases del video de referencia:
replica la estructura, el gancho y el ritmo, con contenido y punto de vista propios. Español neutro latinoamericano, tuteo.
Evita afirmaciones médicas o financieras absolutas; cuando el tema lo requiera, sugiere consultar a un profesional en una frase."""
