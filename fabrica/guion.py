"""Guion de Short (45–60 s) en escenas, con la voz de Germancho, a partir de la ficha de ADN y el perfil del canal."""
import json, re
from .comun import claude, estilo, oferta, nivel_para, POSES, CANAL_COLOR, canal_de, MOCK

EJES = {"equilibrate": "Amor (pareja, amor propio, familia, vínculos)", "mitribu": "Dinero (mentalidad financiera, ingresos, hábitos con el dinero)",
        "soyintegral": "Salud (hábitos, cuerpo, sueño, estrés, bienestar laboral)"}


def guion(ficha, perfil, formato="shorts", tipo_contenido="atraccion", nivel=""):
    canal = canal_de(perfil["id"])
    adn = ficha["adn"]
    nivel = nivel or nivel_para(canal, tipo_contenido)
    of = oferta(nivel)
    cierre = of.get("linea_hablada", "") if (of.get("enlace_resuelto") or MOCK) else ""
    instr_cta = (f"TIPO DE CONTENIDO: {tipo_contenido}. " +
                 (f"Después del Reto, UNA frase de invitación suave (no venta): «{cierre}»." if tipo_contenido == "conversion" and cierre
                  else "No menciones productos ni mentorías; solo el reto y la suscripción."))
    if formato == "historia":
        return guion_historia(ficha, perfil, tipo_contenido, nivel)
    largo = "45–58 segundos (120–150 palabras habladas)" if formato == "shorts" else "8–10 minutos (1.200–1.500 palabras)"
    n_escenas = "6 a 8" if formato == "shorts" else "20 a 30"
    user = f"""Canal: {perfil['canal']} · Eje: {EJES[canal]} · Idioma: {perfil['idioma']} · Formato: {formato} ({largo}).

FICHA DE ADN DEL VIDEO DE REFERENCIA (replica estructura y gancho, NO el contenido literal):
{json.dumps(adn, ensure_ascii=False)}

Escribe el guion de Germancho en {n_escenas} escenas. Cada escena: una o dos frases habladas, una emoción del personaje, un objeto de apoyo
(se dibuja en el color del canal), una pose del libro entre {list(POSES)}, un prompt visual corto en inglés para ilustrar la escena
y "broll": 2–4 palabras en inglés para buscar metraje de archivo real de esa escena (sin personajes animados).
El gancho va en la escena 1 y debe funcionar en los primeros 2 segundos. La última escena es el "Reto de hoy" y termina con UNA frase corta
que pida la suscripción con una razón (ej.: «Suscríbete: mañana hay otro reto»). Si el tema viene de un capítulo de una serie, menciona «el video completo está en el canal».
{instr_cta}
Además entrega "ganchos_alternativos": 3 versiones DISTINTAS de la escena 1 (misma duración, otro ángulo: pregunta / dato o contradicción / historia en primera persona),
para probar cuál retiene mejor. IMPORTANTE: el total hablado debe sumar {largo}; cuenta las palabras. El título va SIN hashtags ni emojis.
Dentro de los textos usa comillas angulares «» o ninguna; NUNCA comillas dobles " (rompen el JSON). Devuelve JSON válido y completo.

Responde SOLO con JSON:
{{"titulo": "máx. 60 caracteres, con la fórmula del ADN adaptada", "titulos_alternativos": ["...", "..."],
 "descripcion": "3–4 líneas con palabras clave, sin enlaces, termina invitando al reto",
 "hashtags": ["#...", 5 a 8],
 "miniatura": {{"texto": "2–4 palabras", "emocion": "alegria|miedo|ira|tristeza|asco|sorpresa", "objeto": "...", "pose": "una de la lista"}},
 "escenas": [{{"n": 1, "texto": "lo que dice Germancho", "emocion": "...", "objeto": "...", "pose": "...", "prompt_visual": "english, short", "broll": "english keywords", "segundos": 0}}],
 "reto_de_hoy": "una acción concreta de < 5 minutos",
 "ganchos_alternativos": ["texto completo alternativo de la escena 1", "...", "..."],
 "palabras": 0}}"""
    mock = {"titulo": "La gente sigue sin plata por ESTO", "titulos_alternativos": ["3 hábitos que te mantienen sin dinero", "No es falta de plata"],
            "descripcion": "No es falta de dinero: son tres hábitos. Germancho te muestra cuáles y te deja un reto de 5 minutos. #dinero #habitos",
            "hashtags": ["#dinero", "#habitos", "#mentalidad", "#finanzaspersonales", "#shorts"],
            "miniatura": {"texto": "NO ES LA PLATA", "emocion": "sorpresa", "objeto": "moneda", "pose": "salto_sorpresa"},
            "escenas": [
                {"n": 1, "texto": "¿Crees que sigues sin plata por falta de dinero? No. Es por esto.", "emocion": "sorpresa", "objeto": "moneda", "pose": "salto_sorpresa", "prompt_visual": "coin spinning above his open hand", "segundos": 5},
                {"n": 2, "texto": "Hábito uno: gastas lo que llega el mismo día que llega.", "emocion": "ira", "objeto": "billete volando", "pose": "senalando", "prompt_visual": "banknote flying away from his hand", "segundos": 8},
                {"n": 3, "texto": "Hábito dos: te comparas con gente que ni conoces.", "emocion": "tristeza", "objeto": "teléfono", "pose": "aburrido", "prompt_visual": "staring at a phone screen, slumped", "segundos": 8},
                {"n": 4, "texto": "Hábito tres: pospones la decisión importante para el lunes. Y el lunes nunca llega.", "emocion": "miedo", "objeto": "calendario", "pose": "escalera", "prompt_visual": "climbing a ladder made of calendar pages", "segundos": 10},
                {"n": 5, "texto": "La buena noticia: los hábitos se cambian uno a la vez.", "emocion": "alegria", "objeto": "taza roja", "pose": "butaco_tazas", "prompt_visual": "sitting on a stool holding a red mug", "segundos": 7},
                {"n": 6, "texto": "Reto de hoy: anota en un papel el último gasto que no necesitabas. Solo eso. Y cuéntame en comentarios.", "emocion": "alegria", "objeto": "tarjeta Reto", "pose": "letrero", "prompt_visual": "holding a sign that reads RETO", "segundos": 10}],
            "reto_de_hoy": "Anota el último gasto que no necesitabas.", "palabras": 130,
            "ganchos_alternativos": ["¿Y si el problema nunca fue la plata? Mira esto.", "El 70 % de la gente repite estos tres hábitos sin notarlo.", "Yo gasté mi primer sueldo en dos días. Así aprendí esto."]}
    g = claude(estilo(canal), user, mock=mock, max_tokens=6000)
    palabras = sum(len(e.get("texto", "").split()) for e in g.get("escenas", []))
    minimo = 100 if formato == "shorts" else 900
    if len(g.get("escenas", [])) < 5 or palabras < minimo:
        print(f"  ! guion incompleto ({len(g.get('escenas', []))} escenas, {palabras} palabras); regenerando")
        user2 = user + f"\n\nTu intento anterior quedó incompleto ({len(g.get('escenas', []))} escenas, {palabras} palabras). Entrega las {n_escenas} escenas completas y el JSON cerrado."
        g = claude(estilo(canal), user2, mock=mock, max_tokens=6000)
    ultima = g["escenas"][-1]["texto"].lower() if g.get("escenas") else ""
    if "reto" not in ultima and g.get("reto_de_hoy"):
        g["escenas"].append({"n": len(g["escenas"]) + 1, "texto": f"Reto de hoy: {g['reto_de_hoy'].rstrip('.')}. Cuéntame en comentarios cómo te fue.",
                             "emocion": "alegria", "objeto": "tarjeta Reto", "pose": "letrero", "prompt_visual": "holding up a small blank card", "segundos": 8})
    g["palabras"] = sum(len(e.get("texto", "").split()) for e in g.get("escenas", []))
    g["titulo"] = re.sub(r"\s*#\S+", "", g.get("titulo", "")).strip() or g.get("titulo", "")
    g["canal"] = canal
    g["color"] = CANAL_COLOR[canal][1]
    g["tipo_contenido"] = tipo_contenido
    g["nivel"] = nivel
    g["ganchos_alternativos"] = [x for x in (g.get("ganchos_alternativos") or []) if isinstance(x, str) and len(x.split()) >= 4][:3]
    for e in g["escenas"]:
        if e.get("pose") not in POSES:
            e["pose"] = "saludando"
    if g["miniatura"].get("pose") not in POSES:
        g["miniatura"]["pose"] = "salto_sorpresa"
    return g


def guion_historia(ficha, perfil, tipo_contenido="atraccion", nivel=""):
    """Short narrativo con giro (formato «historia»): premisa absurda → contexto → desarrollo → tensión → giro → pregunta binaria."""
    canal = canal_de(perfil["id"])
    adn = ficha["adn"]; h = ficha.get("historia") or {}
    nivel = nivel or nivel_para(canal, tipo_contenido)
    of = oferta(nivel); cierre = of.get("linea_hablada", "") if (of.get("enlace_resuelto") or MOCK) else ""
    base = (f"HISTORIA REAL (no cambies hechos, nombres ni fechas; si algo no está aquí, no lo inventes):\n{json.dumps(h, ensure_ascii=False)}" if h
            else f"FICHA DE ADN DEL VIDEO DE REFERENCIA (replica la estructura narrativa, NO el contenido):\n{json.dumps(adn, ensure_ascii=False)}")
    user = f"""Canal: {perfil['canal']} · Idioma: {perfil['idioma']} · Formato: HISTORIA (Short narrativo de 45–60 s, 130–160 palabras).
{base}

Escribe la narración de Germancho en 6 a 8 escenas con esta estructura y tiempos: 1) gancho: premisa absurda o paradójica en una frase (≤ 3 s);
2) contexto: época, lugar, personaje (≈ 10 s); 3) desarrollo (≈ 15 s); 4) tensión: algo se alarga o se complica (≈ 10 s); 5) giro que invierte la expectativa (≈ 8 s);
6) cierre: una frase que conecta con {EJES[canal]} sin moralizar + la PREGUNTA BINARIA («¿A o B? Te leo») + «Suscríbete: mañana hay otra historia».
Tono: «cuentan que…», pausado, cálido, ligeramente irónico; una idea por frase; sin comillas dobles dentro de los textos.
Cada escena: texto hablado, emoción del personaje, pose entre {list(POSES)}, prompt visual corto en inglés y "broll": 2–4 palabras en inglés para metraje de archivo real de la época o del objeto.
{('Después de la pregunta, UNA frase de invitación suave: «' + cierre + '».') if tipo_contenido == 'conversion' and cierre else ''}
Responde SOLO con JSON:
{{"titulo": "≤ 60 caracteres, fórmula [figura] + [acción extrema] + a + [persona] + [acción cotidiana]… + giro insinuado, sin hashtags ni emojis",
 "titulos_alternativos": ["...", "..."], "descripcion": "3–4 líneas: resume la historia sin revelar el giro, cita la fuente en una línea y termina con la pregunta",
 "hashtags": ["#historia", "#curiosidades", 4 a 6 más del eje],
 "miniatura": {{"texto": "2–4 palabras gruesas (ej. CAFÉ HASTA MORIR)", "emocion": "sorpresa|miedo|tristeza|alegria", "objeto": "...", "pose": "una de la lista"}},
 "escenas": [{{"n": 1, "texto": "...", "emocion": "...", "objeto": "...", "pose": "...", "prompt_visual": "english", "broll": "english keywords", "segundos": 0}}],
 "pregunta_final": "¿A o B?", "reto_de_hoy": "la misma pregunta binaria",
 "ganchos_alternativos": ["3 versiones distintas de la escena 1"], "palabras": 0}}"""
    mock = {"titulo": "Un rey condenó a un hombre a tomar café… hasta morir", "titulos_alternativos": ["El experimento del café que duró más que el rey"], "descripcion": "Cuentan que un rey… Fuente: Wikipedia. ¿Café o té?",
            "hashtags": ["#historia", "#curiosidades", "#café"], "miniatura": {"texto": "CAFÉ HASTA MORIR", "emocion": "sorpresa", "objeto": "taza", "pose": "salto_sorpresa"},
            "escenas": [{"n": i + 1, "texto": t, "emocion": "sorpresa", "objeto": "taza", "pose": "saludando", "prompt_visual": "old coffee cup", "broll": q, "segundos": 8} for i, (t, q) in enumerate([
                ("Un rey condenó a un hombre a tomar café… hasta morir.", "royal castle"), ("Siglo dieciocho, Suecia. Gustavo tercero estaba seguro de que el café era veneno.", "old sweden painting"),
                ("Tomó a dos gemelos condenados a muerte: uno bebería café todos los días; el otro, té.", "twin brothers vintage"), ("Los médicos llevaban la cuenta. Pasaron los años. Los médicos murieron. El rey también.", "antique clock"),
                ("Y el primero en cerrar los ojos… fue el del té.", "tea cup vintage"), ("A veces lo que creemos veneno es compañía. ¿Tú qué habrías apostado: café o té? Te leo. Suscríbete: mañana hay otra historia.", "coffee cup steam")])],
            "pregunta_final": "¿Café o té?", "reto_de_hoy": "¿Café o té?", "ganchos_alternativos": ["¿Y si el café fuera una pena de muerte?", "Dos gemelos, dos tazas, una sentencia.", "El experimento duró más que el rey que lo ordenó."], "palabras": 120}
    g = claude(estilo(canal), user, mock=mock, max_tokens=6000)
    palabras = sum(len(e.get("texto", "").split()) for e in g.get("escenas", []))
    if len(g.get("escenas", [])) < 5 or palabras < 90:
        print(f"  ! historia incompleta ({len(g.get('escenas', []))} escenas, {palabras} palabras); regenerando")
        g = claude(estilo(canal), user + f"\n\nTu intento anterior quedó incompleto ({palabras} palabras). Entrega las 6–8 escenas completas y el JSON cerrado.", mock=mock, max_tokens=6000)
    g["palabras"] = sum(len(e.get("texto", "").split()) for e in g.get("escenas", []))
    g["titulo"] = re.sub(r"\s*#\S+", "", g.get("titulo", "")).strip() or g.get("titulo", "")
    g["reto_de_hoy"] = g.get("pregunta_final") or g.get("reto_de_hoy", "")
    g.update({"canal": canal, "color": CANAL_COLOR[canal][1], "tipo_contenido": tipo_contenido, "nivel": nivel, "formato": "historia", "historia_id": h.get("id", "")})
    g["ganchos_alternativos"] = [x for x in (g.get("ganchos_alternativos") or []) if isinstance(x, str) and len(x.split()) >= 4][:3]
    for e in g["escenas"]:
        if e.get("pose") not in POSES:
            e["pose"] = "saludando"
    if g.get("miniatura", {}).get("pose") not in POSES:
        g.setdefault("miniatura", {})["pose"] = "salto_sorpresa"
    return g
