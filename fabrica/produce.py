#!/usr/bin/env python3
"""
Fábrica de Shorts con Germancho.

    python -m fabrica.produce --perfil mitribu_es --video_id XXXXXXXX     # replicar la estructura de un video viral
    python -m fabrica.produce --perfil soyintegral_es --tema "qué pasa si dejas el azúcar 14 días"
    FABRICA_MOCK=1 python -m fabrica.produce --perfil mitribu_es --tema "prueba"   # sin APIs (prueba local)

Salida: producciones/<fecha>-<perfil>-<slug>/ {ficha.json, guion.json, voz.mp3, escenas/*.png, subtitulos.ass, short.mp4, miniatura.jpg, metadata.json}
y actualiza producciones/index.json (lo lee la pestaña Producciones de la página).
"""
import argparse, datetime as dt, json, os, shutil, sys, time
from .comun import cargar_env, OUT, slug, perfil as cargar_perfil, canal_de, guardar_json, MOCK
from . import adn, guion as mod_guion, voz, imagenes, render


def main():
    cargar_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", required=True)
    ap.add_argument("--video_id", default="")
    ap.add_argument("--tema", default="")
    ap.add_argument("--formato", default="shorts", choices=["shorts"])
    ap.add_argument("--voz", default=os.environ.get("ELEVEN_VOICE_NAME", ""))
    a = ap.parse_args()
    if not a.video_id and not a.tema:
        sys.exit("Indica --video_id o --tema")

    p = cargar_perfil(a.perfil)
    canal = canal_de(p["id"])
    t0 = time.time()
    print(f"=== Fábrica · {p['canal']} · {'video ' + a.video_id if a.video_id else 'tema: ' + a.tema}{' · MOCK' if MOCK else ''}")

    # 1. ADN
    f = adn.ficha(a.video_id or None, a.tema or None, p["idioma"])
    print(f"  ADN: {f['adn'].get('tema_central', '')[:70]} · gancho: {f['adn'].get('tipo_de_gancho')}")

    # 2. Guion
    g = mod_guion.guion(f, p, a.formato)
    nombre = f"{dt.date.today():%Y%m%d}-{p['id']}-{slug(g['titulo'])}"
    d = OUT / nombre
    (d / "escenas").mkdir(parents=True, exist_ok=True)
    guardar_json(d / "ficha.json", f)
    guardar_json(d / "guion.json", g)
    print(f"  Guion: «{g['titulo']}» · {len(g['escenas'])} escenas · ~{g.get('palabras', '?')} palabras")

    # 3. Voz
    mp3, palabras, limites, dur = voz.sintetizar(g["escenas"], str(d), a.voz or None, p["idioma"])
    print(f"  Voz: {dur:.1f} s · {len(palabras)} palabras")
    if dur > 59 and a.formato == "shorts":
        print("  ! aviso: supera 59 s; YouTube lo tratará como video normal. Acortar guion.")

    # 4. Escenas
    pngs = []
    for e in g["escenas"]:
        png = str(d / "escenas" / f"escena{e['n']:02d}.png")
        prompt = imagenes.generar_escena(e, canal, png)
        e["prompt_final"] = prompt
        pngs.append(png)
        print(f"  Escena {e['n']}: {e['pose']} · {e['emocion']}")
    guardar_json(d / "guion.json", g)

    # 5. Miniatura (escena de la emoción pedida; si no, la primera)
    m = g["miniatura"]
    base = next((png for e, png in zip(g["escenas"], pngs) if e["emocion"] == m.get("emocion")), pngs[0])
    imagenes.miniatura(base, m["texto"], canal, m.get("emocion", "sorpresa"), str(d / "miniatura.jpg"))

    # 6. Render
    ass = render.subtitulos_ass(palabras, canal, str(d / "subtitulos.ass"))
    mp4 = render.ensamblar(pngs, limites[: len(pngs)], mp3, ass, str(d / "short.mp4"), str(d / "_tmp"))
    shutil.rmtree(d / "_tmp", ignore_errors=True)
    tam = os.path.getsize(mp4) / 1e6

    # 7. Metadatos para publicar
    meta = {"id": nombre, "perfil": p["id"], "canal": p["canal"], "fecha": dt.datetime.now().isoformat(timespec="seconds"),
            "titulo": g["titulo"], "titulos_alternativos": g.get("titulos_alternativos", []), "descripcion": g["descripcion"] + "\n\n" + " ".join(g["hashtags"]),
            "hashtags": g["hashtags"], "reto_de_hoy": g.get("reto_de_hoy", ""), "duracion_s": round(dur, 1), "tamano_mb": round(tam, 1),
            "fuente": f["fuente"], "estado": "pendiente_aprobacion", "archivos": {"video": f"{nombre}/short.mp4", "miniatura": f"{nombre}/miniatura.jpg",
            "miniatura_16x9": f"{nombre}/miniatura_16x9.jpg", "guion": f"{nombre}/guion.json", "ficha": f"{nombre}/ficha.json"},
            "divulgacion_ia": "Marcar 'contenido alterado o sintético' al subir (voz e imágenes generadas con IA)."}
    guardar_json(d / "metadata.json", meta)

    # índice
    idx_path = OUT / "index.json"
    idx = json.loads(idx_path.read_text()) if idx_path.exists() else {"producciones": []}
    idx["producciones"] = [x for x in idx["producciones"] if x["id"] != nombre] + [meta]
    idx["producciones"].sort(key=lambda x: x["fecha"], reverse=True)
    idx["actualizado"] = meta["fecha"]
    guardar_json(idx_path, idx)
    print(f"\nListo en {time.time() - t0:.0f} s → producciones/{nombre}/short.mp4 ({tam:.1f} MB, {dur:.1f} s)")


if __name__ == "__main__":
    main()
