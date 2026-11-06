"""Analiza las miniaturas de los videos virales de cada perfil: brillo, % oscuro, % amarillo, % tonos piel (proxy de rostro), % texto probable.
Escribe data/miniaturas_<perfil>.json con promedios y los 10 ejemplos más vistos. Se ejecuta tras el radar nocturno."""
import io, json, sys
import requests
from PIL import Image
from .comun import ROOT

DATA = ROOT / "data"


def metricas(img):
    im = img.convert("RGB").resize((160, 90))
    px = list(im.getdata()); n = len(px)
    brillo = sum((r + g + b) / 3 for r, g, b in px) / n
    oscuros = sum(1 for r, g, b in px if (r + g + b) / 3 < 60) / n
    amarillo = sum(1 for r, g, b in px if r > 180 and g > 150 and b < 90) / n
    piel = sum(1 for r, g, b in px if r > 95 and g > 40 and b > 20 and r > g > b and (r - g) > 15 and (r - b) > 15 and r < 250) / n
    saturados = sum(1 for r, g, b in px if max(r, g, b) - min(r, g, b) > 120) / n
    return {"brillo": round(brillo), "pct_oscuro": round(oscuros * 100), "pct_amarillo": round(amarillo * 100), "pct_piel": round(piel * 100), "pct_saturado": round(saturados * 100)}


def analizar(perfil_id, n=30):
    p = DATA / f"{perfil_id}.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    filas = []
    for v in d["videos"][:n]:
        url = v.get("miniatura")
        if not url:
            continue
        try:
            r = requests.get(url, timeout=20); r.raise_for_status()
            m = metricas(Image.open(io.BytesIO(r.content)))
        except Exception:
            continue
        filas.append({"video_id": v["video_id"], "titulo": v["titulo"], "vistas": v["vistas"], "ratio": v["ratio_vistas_subs"], "miniatura": url, **m})
    if not filas:
        return None
    prom = {k: round(sum(f[k] for f in filas) / len(filas)) for k in ("brillo", "pct_oscuro", "pct_amarillo", "pct_piel", "pct_saturado")}
    top = sorted(filas, key=lambda f: -f["vistas"])[:10]
    prom_top = {k: round(sum(f[k] for f in top) / len(top)) for k in prom}
    oscuras = sum(1 for f in filas if f["pct_oscuro"] >= 35) / len(filas)
    con_rostro = sum(1 for f in filas if f["pct_piel"] >= 8) / len(filas)
    con_amarillo = sum(1 for f in filas if f["pct_amarillo"] >= 2) / len(filas)
    out = {"perfil": perfil_id, "n": len(filas), "promedio": prom, "promedio_top10": prom_top,
           "lectura": {"pct_miniaturas_oscuras": round(oscuras * 100), "pct_con_rostro_probable": round(con_rostro * 100), "pct_con_amarillo": round(con_amarillo * 100)},
           "recomendacion": ("Predomina fondo oscuro + rostro: usar variante OSCURA con rostro grande" if oscuras > 0.5 and con_rostro > 0.5 else
                             "Predomina fondo claro: la variante CLARA compite bien" if oscuras < 0.3 else "Mixto: probar clara y oscura con 'Prueba y compara'"),
           "ejemplos": top}
    (DATA / f"miniaturas_{perfil_id}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"{perfil_id}: {len(filas)} miniaturas · oscuras {out['lectura']['pct_miniaturas_oscuras']}% · rostro {out['lectura']['pct_con_rostro_probable']}% · amarillo {out['lectura']['pct_con_amarillo']}% → {out['recomendacion']}")
    return out


if __name__ == "__main__":
    perfiles = sys.argv[1:] or [p.stem for p in DATA.glob("*_e?.json") if not p.stem.startswith(("cache", "miniaturas"))]
    for pid in perfiles:
        analizar(pid)
