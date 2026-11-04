"""Cliente falso de la YouTube Data API para probar la lógica del radar sin red.
Genera canales y videos deterministas: algunos canales cumplen los filtros y otros no."""
import random, datetime as dt

random.seed(7)
HOY = dt.datetime.now(dt.timezone.utc)

TITULOS_ES = ["7 señales de que el universo te está hablando", "Qué pasa cuando sueltas el control",
              "El número 1111 y lo que nadie te dijo", "3 hábitos que cambian tu energía",
              "Por qué atraes personas tóxicas", "La trampa de la dopamina explicada",
              "Cómo calmar la ansiedad en 5 minutos", "Señales de burnout que ignoras"]
TITULOS_EN = ["7 signs the universe is talking to you", "What happens when you let go",
              "Angel number 1111 explained", "3 habits that change your energy"]


class FakeYouTube:
    cuota = 0
    agotado = False

    def __init__(self):
        self.canales = {}
        for i in range(40):
            cid = f"UC_fake_{i:02d}"
            subs = random.choice([300, 2500, 8000, 25000, 60000, 95000, 250000])
            # canales pares: fórmula probada (muchos virales); impares: un solo golpe de suerte
            self.canales[cid] = dict(subs=subs, base=max(subs // 10, 50), formula=(i % 2 == 0), videos=[])
            for j in range(25):
                vid = f"v_{i:02d}_{j:02d}"
                dias = random.randint(1, 200)
                vistas = self.canales[cid]["base"] * random.uniform(0.3, 2.0)
                if (self.canales[cid]["formula"] and j % 4 == 0) or (not self.canales[cid]["formula"] and j == 0):
                    vistas = subs * random.uniform(6, 40)
                en = i % 5 == 0
                self.canales[cid]["videos"].append(dict(
                    id=vid, cid=cid, dias=dias, vistas=int(vistas), en=en,
                    titulo=random.choice(TITULOS_EN if en else TITULOS_ES),
                    dur=random.choice(["PT45S", "PT58S", "PT9M12S", "PT14M3S", "PT2M"])))
        self.videos = {v["id"]: v for c in self.canales.values() for v in c["videos"]}

    def _snippet(self, v):
        pub = (HOY - dt.timedelta(days=v["dias"])).strftime("%Y-%m-%dT%H:%M:%SZ")
        return dict(title=v["titulo"], description="descripción de prueba " * 3, channelId=v["cid"],
                    channelTitle=f"Canal {v['cid'][-2:]}", publishedAt=pub,
                    thumbnails={"high": {"url": f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg"}},
                    defaultAudioLanguage="en" if v["en"] else "es", tags=["prueba"])

    def get(self, recurso, **p):
        self.cuota += {"search": 100, "videos": 1, "channels": 1, "playlistItems": 1}[recurso]
        if recurso == "search":
            corto = p.get("videoDuration") == "short"
            pool = [v for v in self.videos.values() if v["dias"] <= 90 and ((v["dur"].startswith("PT") and "M" not in v["dur"]) == corto)]
            random.shuffle(pool)
            return {"items": [{"id": {"videoId": v["id"]}} for v in pool[:50]]}
        if recurso == "videos":
            items = []
            for vid in p["id"].split(","):
                v = self.videos.get(vid)
                if v:
                    items.append({"id": vid, "snippet": self._snippet(v),
                                  "statistics": {"viewCount": str(v["vistas"]), "likeCount": str(v["vistas"] // 30), "commentCount": str(v["vistas"] // 400)},
                                  "contentDetails": {"duration": v["dur"]}})
            return {"items": items}
        if recurso == "channels":
            items = []
            for cid in p["id"].split(","):
                c = self.canales.get(cid)
                if c:
                    items.append({"id": cid, "snippet": {"title": f"Canal {cid[-2:]}", "country": "CO", "publishedAt": "2023-01-01T00:00:00Z"},
                                  "statistics": {"subscriberCount": str(c["subs"]), "videoCount": "120", "viewCount": str(c["subs"] * 40)},
                                  "contentDetails": {"relatedPlaylists": {"uploads": "UU" + cid[2:]}}})
            return {"items": items}
        if recurso == "playlistItems":
            cid = "UC" + p["playlistId"][2:]
            return {"items": [{"contentDetails": {"videoId": v["id"]}} for v in self.canales[cid]["videos"]]}
