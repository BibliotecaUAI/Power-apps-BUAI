"""Corre la simulación de Contador y ContadorM en varios dispositivos y deja capturas e informe.

Uso: python3 correr.py <carpeta src nueva> <carpeta src original> <carpeta salida>
"""
import asyncio
import datetime as dt
import json
import os
import sys

from powerfx import Entorno
from simular import Simulador, colores, pagina

NUEVO, ORIGINAL, SALIDA = sys.argv[1:4]
os.makedirs(SALIDA, exist_ok=True)
HOY = dt.date(2026, 10, 23)

# Dispositivos (ancho × alto en px de pantalla, como los ve Power Apps)
DISPOSITIVOS = [
    ("iPhone SE", 375, 667, "iOS"), ("iPhone 14", 390, 844, "iOS"), ("iPhone 15 Pro Max", 430, 932, "iOS"),
    ("Galaxy S23", 360, 780, "Android"), ("Pixel 7", 412, 915, "Android"), ("Moto G", 360, 800, "Android"),
    ("iPad mini vertical", 744, 1133, "iOS"), ("iPad 10 vertical", 820, 1180, "iOS"), ("Galaxy Tab vertical", 800, 1280, "Android"),
    ("iPad 10 horizontal", 1180, 820, "iOS"), ("iPad Pro 12.9 horizontal", 1366, 1024, "iOS"), ("Galaxy Tab horizontal", 1280, 800, "Android"),
    ("iPhone 14 horizontal", 844, 390, "iOS"), ("Pixel 7 horizontal", 915, 412, "Android"),
    ("Notebook 1366", 1366, 657, "Windows"), ("Notebook 1536 (125 %)", 1536, 730, "Windows"), ("Monitor Full HD", 1920, 969, "Windows"),
    ("Monitor 2K", 2560, 1305, "Windows"), ("Notebook 1280", 1280, 632, "Windows"), ("MacBook Air", 1440, 789, "MacOS"),
]

# ---------------------------------------------------------------- datos reales (Postgrado, 22-10-2026)
ZONAS = [("Sala 401", "Sala de estudio", 5, 0), ("Sala ADI", "Sala de estudio", 7, 2), ("Sala 402", "Sala de estudio", 6, 3),
         ("Sala 403", "Sala de estudio", 5, 1), ("Sala 404", "Sala de estudio", 5, None), ("Sala 405", "Sala de estudio", 6, 4),
         ("Sala 406", "Sala de estudio", 6, 2), ("Sala 407", "Sala de estudio", 6, None), ("Sala 408", "Sala de estudio", 5, 5),
         ("Sala 409", "Sala de estudio", 5, None), ("Sala 410", "Sala de estudio", 6, 7), ("Sala 411", "Sala de estudio", 5, 0),
         ("Sala 412", "Sala de estudio", 5, 1), ("Bloomberg", "Biblioteca", 18, 3), ("Espacio central", "Biblioteca", 72, 23)]
RONDAS = {9: [22, 18, 90, 0], 10: [27, 27, 162, 5], 12: [20, 20, 162, 4], 13: [34, 34, 162, 14], 14: [28, 28, 162, 8],
          15: [26, 26, 162, 3], 16: [22, 22, 162, 3], 18: [7, 7, 162, 3]}


def datos(con_cambios):
    cuenta = []
    for zona, tipo, puestos, pers in ZONAS:
        r = {"Zona": zona, "Tipo": tipo, "Puestos": float(puestos), "Personas": float(pers or 0), "Evento": zona == "Sala ADI", "Antes": -1.0}
        if con_cambios:
            r["Dato"] = pers is not None
        cuenta.append(r)
    horas = [{"h": float(h), "est": "g" if h in RONDAS else ("f" if h > 14 else "p"), "pers": float(RONDAS.get(h, [0])[0])} for h in range(8, 21)]
    rr = [{"f": "20261022", "h": float(h), "p": float(v[0]), "pc": float(v[1]), "c": float(v[2]), "b": float(v[3])} for h, v in RONDAS.items()]
    franjas = []
    for k, (s, fin) in enumerate([(8, 10), (11, 13), (14, 16), (17, 20)]):
        rs = [r for r in rr if s <= r["h"] <= fin]
        cc = [r for r in rs if r["c"] > 0]
        fr = {"fr": f"{s:02d}–{fin:02d}", "n": float(len(rs)), "pers": float(round(sum(r["p"] for r in rs) / len(rs))) if rs else -1.0,
              "prom": sum(r["pc"] / r["c"] for r in cc) / len(cc) if cc else -1.0, "mx": max((r["pc"] / r["c"] for r in cc), default=-1.0),
              "bib": (sum(r["b"] for r in rs) / max(1, sum(r["p"] for r in rs))) if sum(r["p"] for r in rs) else -1.0}
        if con_cambios:
            fr["tot"] = float(sum(r["p"] for r in rs)) if rs else -1.0
        franjas.append(fr)
    zonas_pct = [{"zona": z[0], "pct": (z[3] or 0) / z[2]} for z in ZONAS]
    curva = [{"h": float(h), "v": (RONDAS[h][1] / RONDAS[h][2]) if h in RONDAS else -1.0} for h in range(8, 21)]
    cal_dias = [{"field_2": f"202610{d:02d}"} for d in (1, 2, 5, 6, 7, 8, 9, 13, 14, 15, 16, 19, 21, 22)]
    mes = dt.date(2026, 10, 1)
    cal = []
    for i in range(1, 43):
        d = mes + dt.timedelta(days=i - mes.isoweekday())
        cal.append({"i": float(i), "f": d, "n": float(d.day), "mesOk": d.month == mes.month, "hay": d.strftime("%Y%m%d") in [x["field_2"] for x in cal_dias], "fut": d > HOY})
    zonas_all = [{"Zona": z[0], "Tipo": z[1], "Puestos": str(z[2]), "Activa": "Sí", "Orden": str(k + 1), "Biblioteca": "Biblioteca Postgrado", "ID": float(k)} for k, z in enumerate(ZONAS)]
    return {"colCtCuenta": cuenta, "colCtHoras": horas, "colCtR": rr, "colCtF": franjas, "colCtZ": zonas_pct, "colCtC": curva,
            "colCtCal": cal, "colCtCalDias": cal_dias, "colCtZonas": zonas_all, "colCtRec": [], "colCtOcu": [], "colCtOcuSrc": []}


def variables(tab, cal_abierto):
    return {"varTema": "claro", "varCtTab": float(tab), "varCtPaso": "contar", "varCtBib": "P", "varCtRonda": 14.0, "varCtCorr": False,
            "varCtGuardando": False, "varCtPer": "Hoy", "varCtFOcu": dt.date(2026, 10, 22), "varCtCalOn": cal_abierto,
            "varCtCalMes": dt.date(2026, 10, 1), "varCtDia": HOY, "varCtJefe": True, "varCargado": True, "varCtCargado": True,
            "varYo": {"Nombre": "Rocío Arancibia", "Cargo": "Asistente de Biblioteca", "Area": "Servicios", "Biblioteca": "Postgrado"},
            "varArea": "Servicios", "varFoto": None, "varCtZSel": None, "varCtAbre": None}


ESCENARIOS = [("contar", 1, False), ("ocupacion_calendario", 2, True)]
MEDIR = r"""
() => {
  const out = [];
  const fuera = [];
  for (const el of document.querySelectorAll('.html')) {
    // textos que se salen de su visor HTML (se cortan sin avisar)
    const r = el.getBoundingClientRect();
    for (const t of el.querySelectorAll('*')) {
      const cs = getComputedStyle(t);
      if (t.scrollWidth > t.clientWidth + 1 && cs.overflow === 'hidden' && cs.textOverflow !== 'ellipsis' && t.clientWidth > 0 && t.children.length === 0 && t.textContent.trim())
        out.push({n: el.dataset.n, txt: t.textContent.trim().slice(0, 40), tipo: 'corte horizontal'});
    }
    const hijo = el.firstElementChild;
    if (hijo) {
      const fondo = Array.from(hijo.querySelectorAll('*')).reduce((m, t) => Math.max(m, t.getBoundingClientRect().bottom), 0);
      if (fondo > r.bottom + 1 && fondo - r.bottom > 2) out.push({n: el.dataset.n, txt: 'contenido ' + Math.round(fondo - r.bottom) + ' px bajo el borde', tipo: 'corte vertical'});
    }
  }
  return out;
}
"""


async def main():
    from playwright.async_api import async_playwright
    informe = {}
    async with async_playwright() as p:
        nav = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
        for version, src in (("nuevo", NUEVO), ("original", ORIGINAL)):
            for disp, W, H, so in DISPOSITIVOS:
                pantalla = "ContadorM" if W < H else "Contador"
                archivo = {"Contador": "2038.json", "ContadorM": "2155.json"}[pantalla]
                sim = Simulador(os.path.join(src, "Controls", archivo))
                for esc, tab, cal in ESCENARIOS:
                    app = {"Width": float(W), "Height": float(H), "OSType": so, "MinScreenWidth": 320.0, "MinScreenHeight": 320.0, "DesignWidth": 1366.0, "DesignHeight": 768.0}
                    env = Entorno(variables(tab, cal), datos(version == "nuevo"), app, sim.controles, hoy=HOY)
                    colores(env)
                    extra = 2200 if pantalla == "ContadorM" else 0
                    doc, rects, errores = pagina(sim, env, extra)
                    clave = f"{version}|{disp}|{esc}"
                    pg = await nav.new_page(viewport={"width": W, "height": H + extra})
                    await pg.set_content(doc, wait_until="networkidle")
                    medidas = await pg.evaluate(MEDIR)
                    nombre = f"{version}_{disp}_{esc}".replace(" ", "_").replace("(", "").replace(")", "").replace("%", "")
                    await pg.screenshot(path=os.path.join(SALIDA, nombre + ".png"), full_page=True)
                    await pg.close()
                    informe[clave] = {"pantalla": pantalla, "rects": rects, "errores": sorted(set(errores)), "medidas": medidas}
        await nav.close()
    json.dump(informe, open(os.path.join(SALIDA, "informe.json"), "w"), ensure_ascii=False)
    print("listo", len(informe))


asyncio.run(main())
