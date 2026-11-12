"""
Banco de historias reales para el formato «historia» (Shorts narrativos con giro, al estilo de «Un rey condenó a un hombre a tomar café…»).

    python -m fabrica.historias --eje amor --n 20          # añade 20 historias al banco del eje
    python -m fabrica.historias --todos                    # 20 por eje
    python -m fabrica.historias --listar [--eje salud]

Solo hechos documentados (historia, ciencia, biografías, experimentos famosos). Cada historia trae fuente y nivel de certeza;
el planificador usa únicamente las de certeza alta no usadas. Salida: config/historias.json
"""
import argparse, datetime as dt, json, re, sys, unicodedata
from .comun import ROOT, claude, estilo, guardar_json, MOCK

BANCO = ROOT / "config/historias.json"
EJES = {"amor": "amor, pareja, familia, vínculos, amor propio (canal Equilíbrate)", "dinero": "dinero, hábitos financieros, trabajo, decisiones económicas (canal Mi Tribu)",
        "salud": "salud, cuerpo, sueño, estrés, hábitos, medicina (canal Soy Integral)"}
CANAL_EJE = {"equilibrate": "amor", "mitribu": "dinero", "soyintegral": "salud"}


def cargar():
    return json.loads(BANCO.read_text()) if BANCO.exists() else {"historias": []}


def _clave(t):
    t = unicodedata.normalize("NFKD", t).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", t)[:40]


def generar(eje, n=20):
    """Genera en lotes de 5 (respuestas más cortas y JSON más fiable)."""
    total = 0
    while total < n:
        total += _generar_lote(eje, min(5, n - total))
    return total


def _generar_lote(eje, n=5):
    banco = cargar()
    existentes = [h["titulo"] for h in banco["historias"] if h["eje"] == eje]
    user = f"""Necesito {n} HISTORIAS REALES Y DOCUMENTADAS para Shorts narrativos de 45–60 segundos del eje «{EJES[eje]}».
Modelo que funciona (nuestro Short más visto): «Un rey condenó a un hombre a tomar café… hasta morir»: Gustavo III de Suecia, dos gemelos condenados,
uno café y otro té, los médicos y el rey murieron antes, y el primero en morir no fue el del café. Premisa absurda → contexto → desarrollo → tensión → giro → pregunta binaria.

Reglas estrictas:
- Solo hechos ampliamente documentados (historia, ciencia, experimentos famosos, biografías, récords, casos judiciales célebres). Si dudas de un dato, NO incluyas la historia.
- Prohibido inventar nombres, cifras o fechas. Si un dato es aproximado, dilo («hacia 1920», «según la leyenda»).
- Nada de personas vivas privadas ni de tragedias recientes. Nada de historias ya en esta lista: {existentes[:40]}.
- Al menos la mitad deben poder empezar con un café, una taza, una mesa o una cocina (es la marca); las demás terminan en una reflexión del eje.
- El giro debe invertir una expectativa, y la pregunta final debe ser binaria (A o B) para que la gente comente.
Dentro de los textos usa comillas angulares «» o ninguna, NUNCA comillas dobles. Responde SOLO JSON:
{{"historias": [{{"titulo": "título trabajado ≤ 60 caracteres con la fórmula [figura] + [acción extrema] + … + giro insinuado",
  "hecho": "la historia en 4–6 frases con quién, cuándo, dónde y qué pasó, en orden: premisa, contexto, desarrollo, tensión, giro",
  "giro": "una frase", "fuente": "obra, artículo de Wikipedia o institución donde se documenta", "certeza": "alta|media",
  "conexion_eje": "la reflexión de una frase que la une al eje (sin moralizar)", "gancho": "primera frase hablada (≤ 15 palabras)",
  "pregunta_binaria": "¿A o B?", "broll": ["3 consultas en inglés de 2–4 palabras para metraje de archivo"]}}]}}"""
    mock = {"historias": [{"titulo": "El rey que condenó a un hombre a tomar café… hasta morir", "hecho": "Gustavo III de Suecia…", "giro": "no murió primero el del café", "fuente": "Wikipedia: Gustav III of Sweden coffee experiment",
                           "certeza": "alta", "conexion_eje": "lo que creemos veneno a veces es compañía", "gancho": "Un rey condenó a un hombre a tomar café hasta morir.", "pregunta_binaria": "¿Café o té?", "broll": ["old castle hall", "coffee cup steam", "antique book"]}]}
    try:
        r = claude(estilo(None), user, mock=mock, max_tokens=8000, pensar=6000)
    except RuntimeError as e:
        print(f"  ! lote fallido: {str(e)[:120]}"); return n
    nuevas = 0
    claves = {_clave(h["titulo"]) for h in banco["historias"]}
    for h in r.get("historias", []):
        if not h.get("titulo") or _clave(h["titulo"]) in claves:
            continue
        h.setdefault("certeza", "media"); h.setdefault("fuente", ""); h.setdefault("giro", ""); h.setdefault("broll", [])
        h.update({"id": f"{eje}-{_clave(h['titulo'])[:24]}", "eje": eje, "usada": False, "creada": dt.date.today().isoformat()})
        banco["historias"].append(h); claves.add(_clave(h["titulo"])); nuevas += 1
    guardar_json(BANCO, banco)
    print(f"  {eje}: {nuevas} historias nuevas (total {sum(1 for h in banco['historias'] if h['eje'] == eje)}) → config/historias.json")
    return max(nuevas, 1)


def disponibles(canal, n=1):
    eje = CANAL_EJE.get(canal, canal)
    hs = [h for h in cargar()["historias"] if h["eje"] == eje and not h.get("usada") and h.get("certeza") == "alta"]
    return hs[:n]


def marcar_usada(hid, produccion=""):
    banco = cargar()
    for h in banco["historias"]:
        if h["id"] == hid:
            h["usada"] = True; h["produccion"] = produccion
    guardar_json(BANCO, banco)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--eje", default=""); ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--todos", action="store_true"); ap.add_argument("--listar", action="store_true")
    a = ap.parse_args()
    if a.listar:
        for h in cargar()["historias"]:
            if not a.eje or h["eje"] == a.eje:
                print(f"[{h['eje']}] {'✓' if h.get('usada') else ' '} {h.get('certeza', '?'):5} {h['titulo']}  ({h.get('fuente', '')})")
        return
    ejes = list(EJES) if a.todos else ([a.eje] if a.eje in EJES else [])
    if not ejes:
        sys.exit("Indica --eje amor|dinero|salud, --todos o --listar")
    for e in ejes:
        print(f"=== Historias {e}")
        generar(e, a.n)


if __name__ == "__main__":
    main()
