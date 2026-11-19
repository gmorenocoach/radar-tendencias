"""
Auditoría de canales propios (API pública, solo clave): suscriptores, últimos 50 videos, Shorts vs largos, vistas, interacción, cadencia.

    python -m fabrica.auditoria --handles @equilibrateGM,@soyintegralsas,@BaristadelSer

Salida: data/auditoria_<handle>.json y resumen en consola. Cuota ≈ 4 unidades por canal.
"""
import argparse, collections, datetime as dt, json, os, statistics, sys
import requests
from .comun import ROOT, guardar_json

sys.path.insert(0, str(ROOT))
from radar import segundos  # noqa: E402

API = "https://www.googleapis.com/youtube/v3/"


def get(recurso, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    r = requests.get(API + recurso, params=params, timeout=30); r.raise_for_status(); return r.json()


def auditar(handle, n=50):
    c = get("channels", part="snippet,statistics,contentDetails,brandingSettings", forHandle=handle.lstrip("@"))["items"][0]
    st = c["statistics"]; up = c["contentDetails"]["relatedPlaylists"]["uploads"]
    ids, token = [], None
    while len(ids) < n:
        r = get("playlistItems", part="contentDetails", playlistId=up, maxResults=50, **({"pageToken": token} if token else {}))
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        token = r.get("nextPageToken")
        if not token:
            break
    vids = []
    for i in range(0, len(ids[:n]), 50):
        for v in get("videos", part="snippet,statistics,contentDetails", id=",".join(ids[i:i + 50])).get("items", []):
            sn, s = v["snippet"], v.get("statistics", {})
            d = segundos(v["contentDetails"]["duration"])
            vids.append({"id": v["id"], "titulo": sn["title"], "publicado": sn["publishedAt"], "duracion_s": d, "formato": "short" if d <= 180 else "largo",
                         "vistas": int(s.get("viewCount", 0)), "likes": int(s.get("likeCount", 0) or 0), "comentarios": int(s.get("commentCount", 0) or 0),
                         "live": sn.get("liveBroadcastContent", "none"), "url": f"https://www.youtube.com/watch?v={v['id']}"})
    vids.sort(key=lambda x: x["publicado"], reverse=True)
    hoy = dt.datetime.now(dt.timezone.utc)
    def dias(v): return max((hoy - dt.datetime.fromisoformat(v["publicado"].replace("Z", "+00:00"))).days, 1)
    for v in vids:
        v["dias"] = dias(v); v["vistas_dia"] = round(v["vistas"] / v["dias"], 2)
        v["interaccion"] = round((v["likes"] + v["comentarios"]) / max(v["vistas"], 1), 4)
    ult30 = [v for v in vids if v["dias"] <= 30]; ult90 = [v for v in vids if v["dias"] <= 90]
    shorts = [v for v in vids if v["formato"] == "short"]; largos = [v for v in vids if v["formato"] == "largo"]
    res = {"handle": handle, "canal": c["snippet"]["title"], "canal_id": c["id"], "creado": c["snippet"]["publishedAt"][:10], "generado": hoy.isoformat(timespec="seconds"),
           "suscriptores": int(st.get("subscriberCount", 0)), "videos_total": int(st.get("videoCount", 0)), "vistas_total": int(st.get("viewCount", 0)),
           "keywords": c.get("brandingSettings", {}).get("channel", {}).get("keywords", ""), "descripcion": c["snippet"].get("description", "")[:500],
           "analizados": len(vids), "publicados_30d": len(ult30), "publicados_90d": len(ult90),
           "vistas_30d": sum(v["vistas"] for v in ult30), "vistas_90d": sum(v["vistas"] for v in ult90),
           "shorts": {"n": len(shorts), "mediana_vistas": statistics.median(v["vistas"] for v in shorts) if shorts else 0, "max": max((v["vistas"] for v in shorts), default=0),
                      "interaccion_media": round(statistics.mean(v["interaccion"] for v in shorts), 4) if shorts else 0},
           "largos": {"n": len(largos), "mediana_vistas": statistics.median(v["vistas"] for v in largos) if largos else 0, "max": max((v["vistas"] for v in largos), default=0),
                      "interaccion_media": round(statistics.mean(v["interaccion"] for v in largos), 4) if largos else 0,
                      "minutos_totales": round(sum(v["duracion_s"] for v in largos) / 60)},
           "top10": sorted(vids, key=lambda v: -v["vistas"])[:10], "videos": vids}
    guardar_json(ROOT / "data" / f"auditoria_{handle.lstrip('@').lower()}.json", res)
    print(f"{res['canal']} ({handle}): {res['suscriptores']} subs · {res['videos_total']} videos · {res['vistas_total']} vistas · últimos 30 d: {len(ult30)} videos, {res['vistas_30d']} vistas")
    print(f"  shorts {len(shorts)} (mediana {res['shorts']['mediana_vistas']}, max {res['shorts']['max']}) · largos {len(largos)} (mediana {res['largos']['mediana_vistas']}, max {res['largos']['max']})")
    for v in res["top10"][:5]:
        print(f"   {v['publicado'][:10]} {v['formato']:5} {v['vistas']:>7} vistas {v['interaccion'] * 100:4.1f}% | {v['titulo'][:70]}")
    return res


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--handles", required=True)
    a = ap.parse_args()
    for h in a.handles.split(","):
        try:
            auditar(h.strip())
        except Exception as e:
            print(f"! {h}: {e}")


if __name__ == "__main__":
    main()
