"""Simula pantallas de la app (posición, tamaño y contenido de cada control) en distintos dispositivos.

Para cada dispositivo calcula las fórmulas X/Y/Width/Height/Visible y el HTML/imagen/texto de
cada control con datos reales, arma una página con todo en su lugar y la abre en Chromium
para sacar una captura y medir: controles nuevos que se montan sobre otros, cosas fuera de
la pantalla, textos que no caben, y letra de casillas bajo 16 px en iPhone (zoom al escribir).
"""
import html as htmlmod
import json
import os
import re

from powerfx import Entorno, NoSoportado, compilar, es_blank, num, txt

PT_A_PX = 96 / 72


class Control:
    def __init__(self, d, padre, sim):
        self.nombre = d["Name"]
        self.tipo = d["Template"]["Name"]
        self.reglas = {r["Property"]: r["InvariantScript"] for r in d["Rules"]}
        self.padre = padre
        self.hijos = []
        self.sim = sim
        self.galeria = None  # galería que contiene a este control (si está en una plantilla)

    def prop(self, p, env, registro=None):
        registro = registro if registro is not None else self.sim.registro_actual.get(self.galeria)
        clave = (self.nombre, p, id(registro))
        cache = self.sim.cache
        if clave in cache:
            return cache[clave]
        val = self._prop(p, env, registro)
        cache[clave] = val
        return val

    def _prop(self, p, env, registro):
        if p == "Text" and self.tipo == "text":
            p = "Default"
        if self.tipo == "gallery" and p == "TemplateWidth":
            return num(self.prop("Width", env)) / max(1, num(self.prop("WrapCount", env) or 1))
        if self.tipo == "gallery" and p == "TemplateHeight":
            return num(self.prop("TemplateSize", env))
        if self.tipo == "gallery" and p == "AllItems":
            return self.prop("Items", env)
        if self.tipo == "screen" and p in ("Width", "Height"):
            return env.app["Width" if p == "Width" else "Height"]
        if p not in self.reglas or self.reglas[p] == "":
            return {"Visible": True, "X": 0.0, "Y": 0.0, "WrapCount": 1.0}.get(p)
        ambitos = [{"__self__": self.nombre}]
        if registro is not None:
            ambitos.append(dict(registro, __registro__=registro))
        return env.ev(compilar(self.reglas[p]), ambitos)


class Simulador:
    def __init__(self, ruta_json):
        d = json.load(open(ruta_json, encoding="utf-8"))
        self.controles = {}
        self.cache = {}
        self.registro_actual = {}
        self.raiz = self._cargar(d["TopParent"], None, None)

    def _cargar(self, d, padre, galeria):
        c = Control(d, padre, self)
        c.galeria = galeria
        self.controles[c.nombre] = c
        for h in d.get("Children", []):
            if h["Template"]["Name"] == "galleryTemplate":
                continue
            c.hijos.append(self._cargar(h, c.nombre, c.nombre if c.tipo == "gallery" else galeria))
        return c


# ---------------------------------------------------------------- colores y estilo
def css_color(v):
    if v is None:
        return "transparent"
    return str(v)


def colores(env):
    """Reemplaza ColorValue/RGBA del intérprete por valores CSS reales."""
    def llamar(f, args, amb, base=env.llamar):
        if f == "ColorValue":
            v = txt(env.ev(args[0], amb))
            if len(v) == 9:  # #RRGGBBAA
                a = int(v[7:9], 16) / 255
                return f"rgba({int(v[1:3], 16)},{int(v[3:5], 16)},{int(v[5:7], 16)},{a:.3f})"
            return v
        if f == "RGBA":
            r, g, b, a = [num(env.ev(x, amb)) for x in args]
            return f"rgba({r:g},{g:g},{b:g},{a:g})"
        if f == "ColorFade":
            return env.ev(args[0], amb)
        return base(f, args, amb)
    env.llamar = llamar


def caja(c, env, reg, x, y, w, h, z):
    def P(p, defecto=None):
        try:
            v = c.prop(p, env, reg)
        except NoSoportado:
            return defecto
        return defecto if v is None else v
    est = f"left:{x:.2f}px;top:{y:.2f}px;width:{w:.2f}px;height:{h:.2f}px;z-index:{z}"
    radio = num(P("RadiusTopLeft", 0) or 0)
    borde = num(P("BorderThickness", 0) or 0)
    tam = num(P("Size", 13) or 13) * PT_A_PX
    pad = "padding:{:.1f}px {:.1f}px {:.1f}px {:.1f}px".format(*(num(P(k, 0) or 0) for k in ("PaddingTop", "PaddingRight", "PaddingBottom", "PaddingLeft")))
    peso = {"FontWeight.Bold": 700, "FontWeight.Semibold": 600}.get(txt(P("FontWeight", "")), 400)
    alin = {"Align.Center": "center", "Align.Right": "right"}.get(txt(P("Align", "")), "left")
    comun = f"{est};border-radius:{radio:.1f}px;border:{borde:.2f}px solid {css_color(P('BorderColor'))};box-sizing:border-box;font-family:Open Sans,Arial,sans-serif;font-size:{tam:.2f}px;font-weight:{peso};color:{css_color(P('Color'))};background:{css_color(P('Fill'))}"
    if c.tipo == "htmlViewer":
        contenido = txt(P("HtmlText", ""))
        return f"<div class='c html' data-n='{c.nombre}' style='{comun};{pad};overflow:hidden;background:{css_color(P('Fill'))};border-width:0'>{contenido}</div>"
    if c.tipo == "image":
        src = txt(P("Image", ""))
        ajuste = "fill" if "Stretch" in txt(P("ImagePosition", "")) else "contain"
        return f"<img class='c img' data-n='{c.nombre}' style='{est};position:absolute;object-fit:{ajuste}' src=\"{htmlmod.escape(src)}\">"
    if c.tipo in ("button", "label"):
        texto = htmlmod.escape(txt(P("Text", "")))
        valin = "center" if c.tipo == "button" or "Middle" in txt(P("VerticalAlign", "")) else "flex-start"
        return (f"<div class='c {c.tipo}' data-n='{c.nombre}' style='{comun};{pad};display:flex;align-items:{valin};justify-content:{ {'left': 'flex-start', 'right': 'flex-end', 'center': 'center'}.get(alin, 'center') if c.tipo == 'button' else {'center': 'center', 'right': 'flex-end'}.get(alin, 'flex-start')};text-align:{alin};overflow:hidden;white-space:{'normal' if c.tipo == 'button' else 'nowrap'}'>{texto}</div>")
    if c.tipo == "text":
        texto = htmlmod.escape(txt(P("Default", "")))
        return (f"<div class='c text' data-n='{c.nombre}' data-tam='{tam:.2f}' style='{comun};{pad};display:flex;align-items:center;justify-content:{ {'center': 'center', 'right': 'flex-end'}.get(alin, 'flex-start')};overflow:hidden;white-space:nowrap'>{texto}</div>")
    if c.tipo == "dropdown":
        return f"<div class='c dd' data-n='{c.nombre}' style='{comun};{pad};display:flex;align-items:center'>{htmlmod.escape(txt(P('Default', '')))}</div>"
    return ""


def dibujar(sim, env, nodo, ox, oy, z, partes, rects, reg=None, auto=None, errores=None):
    """Dibuja `nodo` y sus hijos. `auto` = posición calculada por un contenedor automático."""
    def P(c, p, defecto=None, r=reg):
        try:
            v = c.prop(p, env, r)
        except NoSoportado as e:
            errores.append(f"{c.nombre}.{p}: {e}")
            return defecto
        return defecto if v is None else v
    for c in nodo.hijos:
        if c.tipo == "timer":
            continue
        if not env.verdad(P(c, "Visible", True)):
            continue
        if auto and c.nombre in auto:
            x, y, w, h = auto[c.nombre]
        else:
            x, y = num(P(c, "X", 0)), num(P(c, "Y", 0))
            w, h = num(P(c, "Width", 0)), num(P(c, "Height", 0))
        ax, ay = ox + x, oy + y
        z += 1
        if c.tipo == "groupContainer":
            partes.append(f"<div class='c con' data-n='{c.nombre}' style='left:{ax:.2f}px;top:{ay:.2f}px;width:{w:.2f}px;height:{h:.2f}px;z-index:{z}'></div>")
            rects.append((c.nombre, ax, ay, w, h, c.tipo, reg is not None))
            hijos_auto = None
            if "LayoutMode.Auto" in c.reglas.get("LayoutMode", ""):
                hijos_auto, yy = {}, num(P(c, "PaddingTop", 0))
                gap = num(P(c, "LayoutGap", 0))
                for h2 in c.hijos:
                    if not env.verdad(P(h2, "Visible", True)):
                        continue
                    hh = num(P(h2, "Height", 0))
                    hijos_auto[h2.nombre] = (0.0, yy, w, hh)
                    yy += hh + gap
            z = dibujar(sim, env, c, ax, ay, z, partes, rects, reg, hijos_auto, errores)
            continue
        if c.tipo == "gallery":
            items = P(c, "Items", []) or []
            wrap = int(num(P(c, "WrapCount", 1)) or 1)
            th = num(P(c, "TemplateSize", 0)) + num(P(c, "TemplatePadding", 0))
            tw = w / wrap
            rects.append((c.nombre, ax, ay, w, h, c.tipo, reg is not None))
            for k, item in enumerate(items):
                cx, cy = ax + (k % wrap) * tw, ay + (k // wrap) * th
                if cy - ay >= h - 0.5:
                    break  # fuera del alto de la galería
                sim.registro_actual[c.nombre] = item
                z = dibujar(sim, env, c, cx, cy, z, partes, rects, item, None, errores)
            sim.registro_actual.pop(c.nombre, None)
            continue
        try:
            partes.append(caja(c, env, reg, ax, ay, w, h, z))
        except NoSoportado as e:
            errores.append(f"{c.nombre}: {e}")
            partes.append(f"<div class='c err' style='left:{ax}px;top:{ay}px;width:{w}px;height:{h}px;z-index:{z}'>{c.nombre}</div>")
        rects.append((c.nombre, ax, ay, w, h, c.tipo, reg is not None))
    return z


def pagina(sim, env, alto_extra=0):
    partes, rects, errores = [], [], []
    sim.cache.clear()
    fondo = "#DFE2E6"
    try:
        f = sim.raiz.prop("Fill", env)
        fondo = css_color(f)
    except NoSoportado:
        pass
    dibujar(sim, env, sim.raiz, 0, 0, 0, partes, rects, None, None, errores)
    W, H = env.app["Width"], env.app["Height"]
    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           "<link href='https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700;800&display=swap' rel='stylesheet'>"
           f"<style>html,body{{margin:0;background:{fondo}}} .c{{position:absolute}} .err{{background:repeating-linear-gradient(45deg,#f00 0 6px,#fff 6px 12px);opacity:.6}}"
           ".con{pointer-events:none}</style></head>"
           f"<body><div id='pant' style='position:relative;width:{W}px;height:{H + alto_extra}px;overflow:hidden'>" + "".join(partes) + "</div></body></html>")
    return doc, rects, errores
