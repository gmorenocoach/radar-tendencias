"""
Cola de producción: toma del plan las piezas (largos y shorts) que se publican pronto y las fabrica en lote.

    python -m fabrica.cola --perfil equilibrate_es --dias 2 --max 4      # piezas con fecha ≤ hoy+2 días, hasta 4
    python -m fabrica.cola --todos --dias 2 --max 6                      # todos los perfiles con plan activo
    python -m fabrica.cola --pieza equilibrate_es-20261106-L              # una pieza concreta

Actualiza en planes/<perfil>.json el estado de cada pieza: planificado → produciendo → producido (con produccion_id) o error.
"""
import argparse, datetime as dt, json, subprocess, sys, time
from .comun import ROOT, guardar_json

PLANES = ROOT / "planes"


def cargar(perfil_id):
    p = PLANES / f"{perfil_id}.json"
    return (json.loads(p.read_text()), p) if p.exists() else (None, p)


def producir(pieza, plan):
    perfil = plan["perfil"]
    if pieza["tipo"] == "largo":
        cmd = [sys.executable, "-m", "fabrica.largo", "--perfil", perfil, "--minutos", str(pieza.get("minutos") or plan["plan"].get("minutos_largo", 15))]
        if plan["plan"].get("modo_largo") == "economico":
            cmd.append("--economico")
    else:
        cmd = [sys.executable, "-m", "fabrica.produce", "--perfil", perfil]
    if pieza.get("tipo_contenido"):
        cmd += ["--tipo", pieza["tipo_contenido"]]
    if pieza.get("nivel"):
        cmd += ["--nivel", pieza["nivel"]]
    vid = (pieza.get("referencia_video_id") or "").strip()
    if len(vid) == 11:
        cmd += [f"--video_id={vid}"]          # con '=' porque algunos IDs de YouTube empiezan por '-'
    
    else:
        tema = pieza["titulo"] + (f". Gancho: {pieza['gancho']}" if pieza.get("gancho") else "") + (f". Serie: {pieza['serie']}, capítulo {pieza['capitulo']}" if pieza.get("serie") else "") \
            + (f". Formato de conversión: {pieza['formato_conv']}" if pieza.get("formato_conv") else "")
        cmd += [f"--tema={tema}"]
    print(f"\n>>> {pieza['id']} · {pieza['tipo']} · {pieza['titulo'][:60]}")
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    print(r.stdout[-1500:])
    if r.returncode != 0:
        print(r.stderr[-1500:])
        return None, f"error: {r.stderr.strip().splitlines()[-1][:200] if r.stderr.strip() else 'desconocido'}"
    # id de la producción = última línea "Listo ... → <carpeta>/"
    prod_id = ""
    for line in r.stdout.splitlines()[::-1]:
        if "→" in line:
            prod_id = line.split("→")[1].strip().replace("producciones/", "").split("/")[0]
            break
    return prod_id, f"ok {int(time.time() - t0)}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--perfil", default=""); ap.add_argument("--todos", action="store_true"); ap.add_argument("--pieza", default="")
    ap.add_argument("--dias", type=int, default=2); ap.add_argument("--max", type=int, default=4)
    a = ap.parse_args()
    hoy = dt.date.today()
    perfiles = [a.perfil] if a.perfil else ([p.stem for p in PLANES.glob("*.json") if p.name != "index.json"] if (a.todos or a.pieza) else [])
    if not perfiles:
        sys.exit("Indica --perfil, --todos o --pieza")
    # candidatas por perfil, luego se intercalan (round-robin) para que ningún canal acapare la cola
    colas = {}
    for pid in perfiles:
        plan, path = cargar(pid)
        if not plan or (plan["plan"].get("modo") == "pausa" and not a.pieza):
            continue
        cands = [x for x in plan["piezas"] if x["tipo"] in ("largo", "short") and x.get("estado") in ("planificado", "error")
                 and (x["id"] == a.pieza if a.pieza else dt.date.fromisoformat(x["fecha"]) <= hoy + dt.timedelta(days=a.dias))]
        cands.sort(key=lambda x: (x["fecha"], 0 if x["tipo"] == "largo" else 1))
        if cands:
            colas[pid] = (plan, path, cands)
    hechas = 0
    while hechas < a.max and any(c[2] for c in colas.values()):
        for pid, (plan, path, cands) in list(colas.items()):
            if not cands or hechas >= a.max:
                continue
            pieza = cands.pop(0)
            pieza["estado"] = "produciendo"; guardar_json(path, plan)
            prod_id, msg = producir(pieza, plan)
            pieza["estado"] = "producido" if prod_id else "error"
            pieza["produccion_id"] = prod_id or ""; pieza["resultado"] = msg; pieza["producido_en"] = dt.datetime.now().isoformat(timespec="seconds")
            guardar_json(path, plan)
            hechas += 1
    print(f"\nCola: {hechas} piezas procesadas")


if __name__ == "__main__":
    main()
