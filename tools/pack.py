"""Reempaqueta la carpeta src en un .msapp con los mismos nombres (separador \\) y orden.

Uso: python3 tools/pack.py src dist/BUAI_Contador_Prueba_1.msapp
"""
import json, os, sys, zipfile

src, msapp = sys.argv[1], sys.argv[2]
with open(os.path.join(src, ".msapp-manifest.json")) as f:
    manifest = json.load(f)
os.makedirs(os.path.dirname(os.path.abspath(msapp)), exist_ok=True)
with zipfile.ZipFile(msapp, "w") as z:
    for entry in manifest:
        path = os.path.join(src, entry["name"].replace("\\", "/"))
        with open(path, "rb") as f:
            z.writestr(zipfile.ZipInfo(entry["name"], (1980, 1, 1, 0, 0, 0)), f.read(), compress_type=entry["compress"])
print(f"{len(manifest)} entradas empaquetadas en {msapp}")
