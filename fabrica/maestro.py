"""Genera o actualiza la imagen maestra de Germancho para un canal.

    python -m fabrica.maestro --canal mitribu --instruccion "cambia los ojos a ..."        # edita la maestra actual
    python -m fabrica.maestro --canal equilibrate --desde mitribu                           # deriva la maestra de otro canal cambiando el color
"""
import argparse, os, requests, shutil
from .comun import cargar_env, ROOT, PAGES_BASE, CANAL_COLOR
from .imagenes import _fal, _descargar, FAL_MODEL

def main():
    cargar_env()
    ap = argparse.ArgumentParser(); ap.add_argument("--canal", required=True); ap.add_argument("--instruccion", default=""); ap.add_argument("--desde", default="")
    a = ap.parse_args()
    color_en, _ = CANAL_COLOR[a.canal]
    origen = a.desde or a.canal
    ref_url = f"{PAGES_BASE}/assets/germancho/maestro_{origen}.png"
    base = ("This is Germancho, a hand-drawn scribbly ink cartoon: inverted-triangle head with spiky scribbled hair, long thin neck, stick-thin body, "
            "very long wire legs, twig hands. Keep the SAME character, pose, line style and plain off-white background. ")
    if a.desde and a.desde != a.canal:
        instr = f"Change ONLY the hoodie and the high-top sneakers to {color_en} (keep white soles and laces). Everything else identical. "
    else:
        instr = ""
    instr += a.instruccion + " No text, no signature, no dark background, vertical 9:16."
    print("prompt:", base + instr)
    res = _fal(FAL_MODEL, {"prompt": base + instr, "image_url": ref_url, "aspect_ratio": "9:16", "output_format": "png", "safety_tolerance": "2"})
    out = ROOT / "assets/germancho" / f"maestro_{a.canal}.png"
    if out.exists():
        shutil.copy(out, ROOT / "assets/germancho" / f"maestro_{a.canal}_anterior.png")
    _descargar(res["images"][0]["url"], str(out))
    print("maestra guardada:", out)

if __name__ == "__main__":
    main()
