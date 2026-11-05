"""Guion de Short (45–60 s) en escenas, con la voz de Germancho, a partir de la ficha de ADN y el perfil del canal."""
import json
from .comun import claude, ESTILO_GERMANCHO, POSES, CANAL_COLOR, canal_de

EJES = {"equilibrate": "Amor (pareja, amor propio, familia, vínculos)", "mitribu": "Dinero (mentalidad financiera, ingresos, hábitos con el dinero)",
        "soyintegral": "Salud (hábitos, cuerpo, sueño, estrés, bienestar laboral)"}


def guion(ficha, perfil, formato="shorts"):
    canal = canal_de(perfil["id"])
    adn = ficha["adn"]
    largo = "45–58 segundos (120–150 palabras habladas)" if formato == "shorts" else "8–10 minutos (1.200–1.500 palabras)"
    n_escenas = "6 a 8" if formato == "shorts" else "20 a 30"
    user = f"""Canal: {perfil['canal']} · Eje: {EJES[canal]} · Idioma: {perfil['idioma']} · Formato: {formato} ({largo}).

FICHA DE ADN DEL VIDEO DE REFERENCIA (replica estructura y gancho, NO el contenido literal):
{json.dumps(adn, ensure_ascii=False)}

Escribe el guion de Germancho en {n_escenas} escenas. Cada escena: una o dos frases habladas, una emoción del personaje, un objeto de apoyo
(se dibuja en el color del canal), una pose del libro entre {list(POSES)} y un prompt visual corto en inglés para ilustrar la escena.
El gancho va en la escena 1 y debe funcionar en los primeros 2 segundos. La última escena es el "Reto de hoy".

Responde SOLO con JSON:
{{"titulo": "máx. 60 caracteres, con la fórmula del ADN adaptada", "titulos_alternativos": ["...", "..."],
 "descripcion": "3–4 líneas con palabras clave, sin enlaces, termina invitando al reto",
 "hashtags": ["#...", 5 a 8],
 "miniatura": {{"texto": "2–4 palabras", "emocion": "alegria|miedo|ira|tristeza|asco|sorpresa", "objeto": "...", "pose": "una de la lista"}},
 "escenas": [{{"n": 1, "texto": "lo que dice Germancho", "emocion": "...", "objeto": "...", "pose": "...", "prompt_visual": "english, short", "segundos": 0}}],
 "reto_de_hoy": "una acción concreta de < 5 minutos",
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
            "reto_de_hoy": "Anota el último gasto que no necesitabas.", "palabras": 130}
    g = claude(ESTILO_GERMANCHO, user, mock=mock)
    g["canal"] = canal
    g["color"] = CANAL_COLOR[canal][1]
    for e in g["escenas"]:
        if e.get("pose") not in POSES:
            e["pose"] = "saludando"
    if g["miniatura"].get("pose") not in POSES:
        g["miniatura"]["pose"] = "salto_sorpresa"
    return g
