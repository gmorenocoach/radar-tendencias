"""Reconstruye producciones/index.json a partir de los metadata.json de cada carpeta (evita conflictos entre corridas)."""
import json
from pathlib import Path
OUT = Path(__file__).resolve().parent.parent / "producciones"

def main():
    prods = []
    for m in OUT.glob("*/metadata.json"):
        try:
            prods.append(json.loads(m.read_text()))
        except Exception as e:
            print("  ! metadata ilegible:", m, e)
    prods.sort(key=lambda x: x.get("fecha", ""), reverse=True)
    idx = {"actualizado": prods[0]["fecha"] if prods else "", "producciones": prods}
    (OUT / "index.json").write_text(json.dumps(idx, ensure_ascii=False, indent=1))
    print(f"índice: {len(prods)} producciones")

if __name__ == "__main__":
    main()
