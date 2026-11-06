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
    ap.add_argument("--etapa", default="completa", choices=["completa", "propuesta"], help="propuesta = solo ADN, guion y miniaturas (para aprobar)")
    ap.add_argument("--continuar", default="", help="ID de una propuesta ya aprobada: produce voz, escenas y render con su guion")
    a = ap.parse_args()
    if not a.video_id and not a.tema and not a.continuar:
        sys.exit("Indica --video_id, --tema o --continuar")

    p = cargar_perfil(a.perfil)
    canal = canal_de(p["id"])
    t0 = time.time()
    if a.continuar:
        d = OUT / a.continuar
        f = json.loads((d / "ficha.json").read_text()); g = json.loads((d / "guion.json").read_text()); nombre = a.continuar
        (d / "escenas").mkdir(parents=True, exist_ok=True)
        print(f"=== Fábrica · {p['canal']} · continuar propuesta {nombre}")
    else:
        print(f"=== Fábrica · {p['canal']} · {'video ' + a.video_id if a.video_id else 'tema: ' + a.tema} · etapa {a.etapa}{' · MOCK' if MOCK else ''}")
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

    if a.etapa == "propuesta" and not a.continuar:
        # miniaturas de propuesta (1 imagen IA + rostro) y ficha para decidir
        m = g["miniatura"]
        textos = [m["texto"]] + [t for t in g.get("titulos_alternativos", []) if len(t.split()) <= 5][:1]
        try:
            imagenes.miniatura_pro(canal, m.get("emocion", "sorpresa"), m.get("objeto", "taza"), textos, str(d / "miniatura_16x9"), "16:9")
            shutil.copy(str(d / "miniatura_16x9.jpg"), str(d / "miniatura.jpg"))
        except Exception as e:
            print(f"  ! miniatura pro falló ({e})")
        imagenes.miniatura_rostro(canal, m.get("emocion", "sorpresa"), textos, str(d / "miniatura_16x9"), "16:9")
        cfg = json.loads((OUT.parent / "config/perfiles.json").read_text()); enlaces = cfg.get("_enlaces", {})
        meta = {"id": nombre, "perfil": p["id"], "canal": p["canal"], "formato": "short", "fecha": dt.datetime.now().isoformat(timespec="seconds"),
                "titulo": g["titulo"], "titulos_alternativos": g.get("titulos_alternativos", []), "descripcion": g["descripcion"] + "\n\n" + " ".join(g["hashtags"]),
                "hashtags": g["hashtags"], "reto_de_hoy": g.get("reto_de_hoy", ""), "duracion_s": 0, "tamano_mb": 0, "fuente": f["fuente"], "estado": "propuesta",
                "adn_resumen": {k: f["adn"].get(k) for k in ("tema_central", "gancho_primeros_segundos", "tipo_de_gancho", "formula_del_titulo", "emocion_dominante", "formula_miniatura", "por_que_funciona")},
                "guion_texto": [e["texto"] for e in g["escenas"]],
                "archivos": {"video": "", "miniatura": f"{nombre}/miniatura.jpg", "miniatura_16x9": f"{nombre}/miniatura_16x9.jpg", "guion": f"{nombre}/guion.json", "ficha": f"{nombre}/ficha.json",
                             "miniaturas": [f"{nombre}/{x}" for x in sorted(os.listdir(d)) if x.startswith("miniatura") and x.endswith(".jpg")]},
                "divulgacion_ia": "Marcar 'contenido alterado o sintético' al subir (voz e imágenes generadas con IA)."}
        guardar_json(d / "metadata.json", meta)
        from .indice import main as reconstruir_indice
        reconstruir_indice()
        print(f"\nPropuesta lista en {time.time() - t0:.0f} s → producciones/{nombre} (revisar y aprobar)")
        return

    # 3. Voz
    mp3, palabras, limites, dur = voz.sintetizar(g["escenas"], str(d), a.voz or None, p["idioma"], voz_id=None if a.voz else p.get("voz_id"))
    print(f"  Voz: {dur:.1f} s · {len(palabras)} palabras")
    if dur > 175 and a.formato == "shorts":
        print("  ! aviso: supera 3 minutos; YouTube no lo tratará como Short. Acortar guion.")

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
    textos = [m["texto"]] + [t for t in g.get("titulos_alternativos", []) if len(t.split()) <= 5][:1]
    try:
        imagenes.miniatura_pro(canal, m.get("emocion", "sorpresa"), m.get("objeto", "taza"), textos, str(d / "miniatura_16x9"), "16:9")
        imagenes.miniatura_pro(canal, m.get("emocion", "sorpresa"), m.get("objeto", "taza"), textos[:1], str(d / "miniatura"), "9:16")
        os.replace(str(d / "miniatura_9x16.jpg"), str(d / "miniatura.jpg"))
        imagenes.miniatura_rostro(canal, m.get("emocion", "sorpresa"), textos, str(d / "miniatura_16x9"), "16:9")
        imagenes.miniatura_rostro(canal, m.get("emocion", "sorpresa"), textos[:1], str(d / "miniatura"), "9:16")
    except Exception as e:
        print(f"  ! miniatura pro falló ({e}); usando versión básica")
        base = next((png for e_, png in zip(g["escenas"], pngs) if e_["emocion"] == m.get("emocion")), pngs[0])
        imagenes.miniatura(base, m["texto"], canal, m.get("emocion", "sorpresa"), str(d / "miniatura.jpg"))

    # 6. Render
    ass = render.subtitulos_ass(palabras, canal, str(d / "subtitulos.ass"))
    mp4 = render.ensamblar(pngs, limites[: len(pngs)], mp3, ass, str(d / "short.mp4"), str(d / "_tmp"))
    shutil.rmtree(d / "_tmp", ignore_errors=True)
    tam = os.path.getsize(mp4) / 1e6

    # 7. Metadatos para publicar
    # CTA del canal (enlaces desde config/perfiles.json → _enlaces); se omiten líneas con enlaces vacíos
    cfg = json.loads((OUT.parent / "config/perfiles.json").read_text())
    enlaces = cfg.get("_enlaces", {})
    cta_lineas = []
    for linea in (p.get("cta") or "").split("\n"):
        for k, v in enlaces.items():
            linea = linea.replace("{" + k + "}", v)
        if "{ENLACE_" not in linea and linea.strip():
            cta_lineas.append(linea)
    cta = "\n".join(cta_lineas)
    meta = {"id": nombre, "perfil": p["id"], "canal": p["canal"], "fecha": dt.datetime.now().isoformat(timespec="seconds"),
            "titulo": g["titulo"], "titulos_alternativos": g.get("titulos_alternativos", []), "descripcion": g["descripcion"] + ("\n\n" + cta if cta else "") + "\n\n" + " ".join(g["hashtags"]),
            "hashtags": g["hashtags"], "reto_de_hoy": g.get("reto_de_hoy", ""), "duracion_s": round(dur, 1), "tamano_mb": round(tam, 1),
            "fuente": f["fuente"], "estado": "pendiente_aprobacion", "archivos": {"video": f"{nombre}/short.mp4", "miniatura": f"{nombre}/miniatura.jpg",
            "miniatura_16x9": f"{nombre}/miniatura_16x9.jpg", "guion": f"{nombre}/guion.json", "ficha": f"{nombre}/ficha.json",
            "miniaturas": [f"{nombre}/{x}" for x in sorted(os.listdir(d)) if x.startswith("miniatura") and x.endswith(".jpg")]},
            "divulgacion_ia": "Marcar 'contenido alterado o sintético' al subir (voz e imágenes generadas con IA)."}
    guardar_json(d / "metadata.json", meta)

    from .indice import main as reconstruir_indice
    reconstruir_indice()
    print(f"\nListo en {time.time() - t0:.0f} s → producciones/{nombre}/short.mp4 ({tam:.1f} MB, {dur:.1f} s)")


if __name__ == "__main__":
    main()
