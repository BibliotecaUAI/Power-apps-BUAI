"""Extrae un .msapp a una carpeta legible, guardando el orden original de las entradas.

Uso: python3 tools/unpack.py app/BUAI_Contador_Prueba_1.msapp src
"""
import json, os, sys, zipfile

msapp, out = sys.argv[1], os.path.abspath(sys.argv[2])
manifest = []
with zipfile.ZipFile(msapp) as z:
    for info in z.infolist():
        rel = info.filename.replace("\\", "/")
        dest = os.path.normpath(os.path.join(out, rel))
        if not dest.startswith(out + os.sep):
            sys.exit(f"Ruta insegura en el archivo: {info.filename}")
        manifest.append({"name": info.filename, "compress": info.compress_type})
        if rel.endswith("/"):
            continue
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(dest, "wb") as f:
            f.write(z.read(info))
with open(os.path.join(out, ".msapp-manifest.json"), "w") as f:
    json.dump(manifest, f, indent=1)
print(f"{len(manifest)} entradas extraídas en {out}")
