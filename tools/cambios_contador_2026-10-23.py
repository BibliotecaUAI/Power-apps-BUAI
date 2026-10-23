"""Cambios del Contador (23-10-2026) sobre src/Controls/*.json.

- Contador digitable: casilla numérica (máx. 4 cifras) en vez de − / +, estado «Sin dato»,
  avance «X de Y con dato», botón «Poner 0 en los espacios vacíos», tarjetas blancas al 95 %
  y borde plomo con respiración leve.
- Tabla de Ocupación: columna «Personas (total)» y fecha elegible con calendario desplegable
  (días con rondas marcados con un punto); se quitan los botones «Hoy / 7 días».

Reglas: no se cambia ninguna fórmula de posición existente salvo constantes indicadas;
los controles nuevos copian la fórmula de posición de un control vecino. Cada reemplazo
verifica cuántas veces aparece el texto original y se detiene si no coincide.

Uso: python3 tools/cambios_contador_2026-10-23.py src
"""
import copy, json, os, re, sys

SRC = sys.argv[1]
S_PC = 'Min(App.Width / 1366, App.Height / If(Host.OSType <> "Windows" && App.Height < 600, 819, 768))'
S_M = 'Min(App.Width / 640, App.Height / 700)'
LIBS = [("A", "ConteosA"), ("F", "ConteosF"), ("P", "ConteosP"), ("V", "ConteosV")]


def rep(text, old, new, count=1, where=""):
    n = text.count(old)
    if n != count:
        sys.exit(f"[{where}] se esperaban {count} apariciones y hay {n}: {old[:120]!r}")
    return text.replace(old, new)


class Pantalla:
    def __init__(self, archivo):
        self.ruta = os.path.join(SRC, "Controls", archivo)
        self.doc = json.load(open(self.ruta, encoding="utf-8"))
        self.top = self.doc["TopParent"]
        self.nuevos = []

    def buscar(self, nombre, nodo=None):
        nodo = nodo or self.top
        if nodo["Name"] == nombre:
            return nodo
        for h in nodo.get("Children", []):
            r = self.buscar(nombre, h)
            if r:
                return r
        return None

    def padre(self, nombre, nodo=None):
        nodo = nodo or self.top
        for h in nodo.get("Children", []):
            if h["Name"] == nombre:
                return nodo
            r = self.padre(nombre, h)
            if r:
                return r
        return None

    def get(self, ctrl, prop):
        c = self.buscar(ctrl) if isinstance(ctrl, str) else ctrl
        for r in c["Rules"]:
            if r["Property"] == prop:
                return r["InvariantScript"]
        return None

    def set(self, ctrl, prop, valor, categoria="Design"):
        c = self.buscar(ctrl) if isinstance(ctrl, str) else ctrl
        for r in c["Rules"]:
            if r["Property"] == prop:
                r["InvariantScript"] = valor
                return
        c["Rules"].append({"Property": prop, "Category": categoria, "InvariantScript": valor, "RuleProviderType": "Unknown"})
        if prop not in c["ControlPropertyState"]:
            c["ControlPropertyState"].append(prop)

    def editar(self, ctrl, prop, old, new, count=1):
        self.set(ctrl, prop, rep(self.get(ctrl, prop), old, new, count, f"{ctrl}.{prop}"))

    def todas_reglas(self, nodo=None):
        nodo = nodo or self.top
        for r in nodo["Rules"]:
            yield nodo, r
        for h in nodo.get("Children", []):
            yield from self.todas_reglas(h)

    def reemplazar_en_todo(self, old, new, minimo=1):
        n = 0
        for _, r in self.todas_reglas():
            k = r["InvariantScript"].count(old)
            if k:
                r["InvariantScript"] = r["InvariantScript"].replace(old, new)
                n += k
        if n < minimo:
            sys.exit(f"[global] se esperaba al menos {minimo} aparición y hay {n}: {old[:120]!r}")
        return n

    def quitar(self, nombre):
        p = self.padre(nombre)
        p["Children"] = [h for h in p["Children"] if h["Name"] != nombre]

    def clonar(self, origen, nombre, padre, props, despues_de=None):
        c = copy.deepcopy(self.buscar(origen))
        c["Name"] = nombre
        c["Parent"] = padre
        c["Children"] = [] if c["Template"]["Name"] != "gallery" else c["Children"]
        self.nuevos.append(c)
        for prop, valor in props.items():
            cat = "Behavior" if prop.startswith("On") else ("Data" if prop in ("Default", "Text", "Items", "Image", "HtmlText", "HintText", "MaxLength") else "Design")
            self.set(c, prop, valor, cat)
        p = self.buscar(padre)
        if despues_de:
            i = [h["Name"] for h in p["Children"]].index(despues_de)
            p["Children"].insert(i + 1, c)
        else:
            p["Children"].append(c)
        return c

    def guardar(self):
        # mismo formato que Power Apps Studio: sangría 2, UTF-8 sin escapar, saltos CRLF, sin salto final
        texto = json.dumps(self.doc, indent=2, ensure_ascii=False).replace("\n", "\r\n")
        with open(self.ruta, "wb") as f:
            f.write(texto.encode("utf-8"))


def renumerar(pantallas):
    """Da ControlUniqueId y PublishOrderIndex nuevos a los controles clonados (los originales no cambian)."""
    max_id = max_pub = 0
    for f in os.listdir(os.path.join(SRC, "Controls")):
        d = json.load(open(os.path.join(SRC, "Controls", f), encoding="utf-8"))
        def w(c):
            nonlocal max_id, max_pub
            max_id = max(max_id, int(c["ControlUniqueId"]))
            max_pub = max(max_pub, int(c.get("PublishOrderIndex", 0)))
            for h in c.get("Children", []):
                w(h)
        w(d["TopParent"])
    for p in pantallas:
        for c in p.nuevos:
            for nodo in [c] + c.get("Children", []):
                max_id += 1
                max_pub += 1
                nodo["ControlUniqueId"] = str(max_id)
                nodo["PublishOrderIndex"] = max_pub


# ---------------------------------------------------------------- textos comunes
TEMA_TXT = 'If(varTema = "oscuro", "#F2F2F7", "#1C1C1E")'
TEMA_SUB = 'If(varTema = "oscuro", "#C7C7CC", "#3F4247")'
NEGRO_MET = 'If(varTema = "oscuro", "#F2F2F7", "#1E1F22")'

COL_OCU_VIEJO_1 = 'ClearCollect(colCtOcu, Filter(colCtRec, Estado = "Guardada" && Tipo <> "Actividad" && If(varCtPer = "Semana", Value(FechaNum) >= Value(Text(DateAdd(Today(), -6, TimeUnit.Days), "yyyymmdd")), FechaNum = Text(Today(), "yyyymmdd"))))'
COL_OCU_VIEJO_2 = 'ClearCollect(colCtOcu, Filter(colCtRec, Estado = "Guardada" && Tipo <> "Actividad" && If(varCtPer = "Semana", Value(FechaNum) >= Value(Text(DateAdd(Today(), -6, TimeUnit.Days), "yyyymmdd")), FechaNum = Text(Coalesce(varCtDia, Today()), "yyyymmdd"))))'
COL_OCU_NUEVO = 'ClearCollect(colCtOcu, Filter(If(Coalesce(varCtFOcu, Today()) >= DateAdd(Today(), -6, TimeUnit.Days), colCtRec, colCtOcuSrc), Estado = "Guardada" && Tipo <> "Actividad" && If(varCtPer = "Semana", Value(FechaNum) >= Value(Text(DateAdd(Today(), -6, TimeUnit.Days), "yyyymmdd")), FechaNum = Text(Coalesce(varCtFOcu, Today()), "yyyymmdd"))))'

PROYECCION = '{ID: q.ID, Clave: q.Title, Fecha: q.field_1, FechaNum: q.field_2, Ronda: q.field_3, Biblioteca: q.field_4, Zona: q.field_5, Tipo: q.field_6, Puestos: Text(q.field_7), Personas: Text(q.field_8), Evento: q.field_9, Estado: q.field_10, Usuario: q.field_11, Registrado: q.field_12, Tardio: q.field_13, CorregidoPor: q.field_14, CorregidoEl: q.field_15, PersonasAntes: Text(q.field_16), Auto: q.field_17}'


def cargar_dia_antiguo():
    partes = []
    for cod, lista in LIBS:
        partes.append(f'"{cod}", IfError(ClearCollect(colCtOcuSrc, ForAll(Filter({lista}, field_2 = Text(varCtFOcu, "yyyymmdd")) As q, {PROYECCION})); true, Notify("No se pudo leer {lista} en SharePoint. Revise la conexión e intente de nuevo.", NotificationType.Error); false)')
    return 'If(varCtFOcu < DateAdd(Today(), -6, TimeUnit.Days), Switch(varCtBib, ' + ", ".join(partes) + '))'


def armar_calendario(mes):
    partes = []
    for cod, lista in LIBS:
        partes.append(f'"{cod}", IfError(ClearCollect(colCtCalDias, ShowColumns(Filter({lista}, StartsWith(field_2, Text(varCtCalMes, "yyyymm")) && field_6 = "Biblioteca" && field_10 = "Guardada"), field_2)); true, Clear(colCtCalDias); false)')
    return (f'Set(varCtCalMes, {mes}); Switch(varCtBib, ' + ", ".join(partes) + '); '
            'ClearCollect(colCtCal, ForAll(Sequence(42) As i, With({d: DateAdd(varCtCalMes, i.Value - Weekday(varCtCalMes, StartOfWeek.Monday), TimeUnit.Days)}, '
            '{i: i.Value, f: d, n: Day(d), mesOk: Month(d) = Month(varCtCalMes), hay: Text(d, "yyyymmdd") in colCtCalDias.field_2, fut: d > Today()})))')


def html_envoltorio_pc(cuerpo):
    return ('"<div style=\'zoom:" & Text(' + S_PC + ', "0.0000", "en-US") & ";-webkit-text-size-adjust:100%;text-size-adjust:100%;overflow:hidden;margin:0;padding:0;width:" & (RoundDown(Self.Width / ' + S_PC + ', 0) - 3) & "px;height:" & (RoundDown(Self.Height / ' + S_PC + ', 0) - 3) & "px\'>" & (' + cuerpo + ') & "</div>"')


def html_envoltorio_m(alto_cqw, cuerpo):
    return ('"<div style=\'width:100%;container-type:inline-size;margin:0;padding:0;overflow:hidden\'><div style=\'position:relative;width:100%;height:' + alto_cqw + 'cqw;overflow:hidden\'>" & (' + cuerpo + ') & "</div></div>"')


def u_pc(v):
    return f"{v:g}px"


def mk_u_m(base):
    return lambda v: f"{v * 100 / base:.3f}cqw"


DIAS_SEM = 'Switch(Weekday(varCtFOcu, StartOfWeek.Monday), 1, "lun", 2, "mar", 3, "mié", 4, "jue", 5, "vie", 6, "sáb", "dom")'
MESES = 'Switch(Month(varCtCalMes), 1, "Enero", 2, "Febrero", 3, "Marzo", 4, "Abril", 5, "Mayo", 6, "Junio", 7, "Julio", 8, "Agosto", 9, "Septiembre", 10, "Octubre", 11, "Noviembre", "Diciembre")'


def html_pastilla_fecha(u, ancho, alto):
    ic = u(16)
    return ('"<div style=\'display:flex;align-items:center;justify-content:space-between;box-sizing:border-box;width:' + u(ancho) + ';height:' + u(alto) + ';padding:0 ' + u(14) + ';border-radius:' + u(alto / 2) + ';background:" & If(varTema = "oscuro", "#2C2C2E", "#FFFFFF") & ";border:' + u(1) + ' solid " & If(varTema = "oscuro", "#5A5D62", "#CDD0D5") & ";font-family:Open Sans,Segoe UI,Arial,sans-serif;font-size:' + u(13) + ';font-weight:700;color:" & ' + TEMA_TXT + ' & ";white-space:nowrap\'>'
            '<span style=\'display:flex;align-items:center;gap:' + u(8) + '\'><svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' style=\'width:' + ic + ';height:' + ic + ';flex-shrink:0\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'1.8\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><rect x=\'3.5\' y=\'5\' width=\'17\' height=\'15.5\' rx=\'3\'/><path d=\'M3.5 10h17M8 3v4M16 3v4\'/></svg>" & '
            + DIAS_SEM + ' & " " & Text(varCtFOcu, "dd-mm-yyyy") & If(varCtFOcu = Today(), " · hoy", "") & "</span>'
            '<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' style=\'width:' + u(13) + ';height:' + u(13) + ';flex-shrink:0;transform:rotate(" & If(varCtCalOn, "180", "0") & "deg)\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2.2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><path d=\'M6 9l6 6 6-6\'/></svg></div>"')


def html_calendario(u):
    """Tarjeta del calendario de 296 × 330 (unidades de diseño)."""
    col = 268 / 7
    flecha = lambda d: ('<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 24 24\' style=\'width:' + u(14) + ';height:' + u(14) + '\' fill=\'none\' stroke=\'currentColor\' stroke-width=\'2.2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'><path d=\'' + d + '\'/></svg>')
    circulo = lambda x: ('<div style=\'position:absolute;left:' + u(x) + ';top:' + u(14) + ';width:' + u(36) + ';height:' + u(36) + ';box-sizing:border-box;border-radius:50%;border:' + u(1) + ' solid " & If(varTema = "oscuro", "#5A5D62", "#CDD0D5") & ";display:flex;align-items:center;justify-content:center\'>')
    letras = "".join('<div style=\'position:absolute;left:' + u(14 + k * col) + ';top:' + u(58) + ';width:' + u(col) + ';text-align:center\'>' + t + '</div>' for k, t in enumerate(["LU", "MA", "MI", "JU", "VI", "SÁ", "DO"]))
    izq, arr = f'14 + Mod(i - 1, 7) * {col:.4f}', '78 + RoundDown((i - 1) / 7, 0) * 36'
    if u is u_pc:
        pos_izq, pos_arr = f'Text({izq}, "0.000", "en-US") & "px', f'Text({arr}, "0.000", "en-US") & "px'
    else:
        k = f"{100 / 296:.6f}"
        pos_izq, pos_arr = f'Text(({izq}) * {k}, "0.000", "en-US") & "cqw', f'Text(({arr}) * {k}, "0.000", "en-US") & "cqw'
    celda = ('"<div style=\'position:absolute;left:" & ' + pos_izq + ';top:" & ' + pos_arr + ';width:' + u(col) + ';height:' + u(36) + ';display:flex;align-items:center;justify-content:center\'>'
             '<div style=\'position:relative;width:' + u(32) + ';height:' + u(32) + ';box-sizing:border-box;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:' + u(13) + ';font-weight:" & If(f = varCtFOcu || f = Today(), "800", "600") & ";" & '
             'If(f = varCtFOcu, "background:" & If(varTema = "oscuro", "#F2F2F7", "#111111") & ";color:" & If(varTema = "oscuro", "#111111", "#FFFFFF"), "color:" & If(!mesOk || fut, "#B4B9C0", ' + TEMA_TXT + ') & If(f = Today(), ";border:' + u(1.5) + ' solid " & ' + TEMA_TXT + ', "")) & "\'>" & n & '
             'If(hay, "<span style=\'position:absolute;left:50%;bottom:' + u(3) + ';width:' + u(5) + ';height:' + u(5) + ';margin-left:-' + u(2.5) + ';border-radius:50%;background:" & If(f = varCtFOcu, If(varTema = "oscuro", "#111111", "#FFFFFF"), ' + TEMA_TXT + ') & "\'></span>", "") & "</div></div>"')
    return ('"<div style=\'position:relative;box-sizing:border-box;width:' + u(296) + ';height:' + u(330) + ';border-radius:' + u(22) + ';background:" & If(varTema = "oscuro", "#2C2C2E", "#FFFFFF") & ";border:' + u(1) + ' solid " & If(varTema = "oscuro", "#5A5D62", "#CDD0D5") & ";box-shadow:0 ' + u(18) + ' ' + u(34) + ' -' + u(16) + ' rgba(17,17,17,.45);font-family:Open Sans,Segoe UI,Arial,sans-serif;color:" & ' + TEMA_TXT + ' & "\'>'
            + circulo(14) + flecha('M15 6l-6 6 6 6') + '</div>'
            '<div style=\'position:absolute;left:' + u(56) + ';right:' + u(56) + ';top:' + u(22) + ';text-align:center;font-size:' + u(14) + ';font-weight:800\'>" & ' + MESES + ' & " " & Year(varCtCalMes) & "</div>'
            + circulo(246) + flecha('M9 6l6 6-6 6') + '</div>'
            '<div style=\'font-size:' + u(10.5) + ';font-weight:700;color:" & ' + TEMA_SUB + ' & "\'>' + letras + '</div>" & '
            'Concat(colCtCal, ' + celda + ') & '
            '"<div style=\'position:absolute;left:' + u(14) + ';top:' + u(302) + ';display:flex;align-items:center;gap:' + u(6) + ';font-size:' + u(11) + ';color:" & ' + TEMA_SUB + ' & "\'><span style=\'width:' + u(6) + ';height:' + u(6) + ';border-radius:50%;background:" & ' + TEMA_TXT + ' & "\'></span>Con rondas guardadas</div>'
            '<div style=\'position:absolute;right:' + u(16) + ';top:' + u(300) + ';font-size:' + u(12) + ';font-weight:700;text-decoration:underline\'>Hoy</div></div>"')


IMG_BORDE = ('"data:image/svg+xml;utf8," & EncodeUrl("<svg xmlns=\'http://www.w3.org/2000/svg\' viewBox=\'0 0 {w} {h}\' preserveAspectRatio=\'none\'>'
             '<defs><linearGradient id=\'p\' x1=\'0\' y1=\'0\' x2=\'1\' y2=\'0\'><stop offset=\'0\' stop-color=\'#5A5D62\'/><stop offset=\'0.5\' stop-color=\'#9EA3A9\'/><stop offset=\'1\' stop-color=\'#5A5D62\'/></linearGradient></defs>'
             '<rect x=\'{m}\' y=\'{m}\' width=\'{iw}\' height=\'{ih}\' rx=\'{r}\' ry=\'{r}\' fill=\'none\' stroke=\'url(#p)\' stroke-width=\'{s}\'/>'
             '<rect x=\'{m}\' y=\'{m}\' width=\'{iw}\' height=\'{ih}\' rx=\'{r}\' ry=\'{r}\' fill=\'none\' stroke=\'#C9CCD0\' stroke-width=\'{s}\' stroke-opacity=\'0\'>'
             '<animate attributeName=\'stroke-opacity\' values=\'0;0.75;0\' keyTimes=\'0;0.5;1\' calcMode=\'spline\' keySplines=\'0.42 0 0.58 1;0.42 0 0.58 1\' dur=\'2.4s\' repeatCount=\'indefinite\'/></rect></svg>")')


def img_borde(w, h, r, s):
    m = s / 2
    return IMG_BORDE.format(w=w, h=h, r=r, s=s, m=f"{m:g}", iw=f"{w - s:g}", ih=f"{h - s:g}")


ESTADO = ('If(!ThisItem.Dato, "Sin dato", ThisItem.Puestos > 0 && ThisItem.Personas > ThisItem.Puestos, "Supera los puestos", "Registrado")')
ESTADO_COLOR = ('If(!ThisItem.Dato, "#6E6E73", ThisItem.Puestos > 0 && ThisItem.Personas > ThisItem.Puestos, "#8A4B00", ' + TEMA_TXT + ')')
BORDE_CASILLA = ('If(ThisItem.Dato || !IsBlank({txt}.Text), If(varTema = "oscuro", "#C7C7CC", "#3F4247"), If(varTema = "oscuro", "#5A5D62", "#CDD0D5"))')


def contador(p, suf, S, html_zona, viejo_ini, viejo_fin, nuevo_medio, casilla, lbl, borde_img, borde_rect):
    # 1) colección de conteo: marca qué espacios tienen dato escrito
    p.reemplazar_en_todo('Antes: If(IsBlank(q), -1, Coalesce(Value(q.Personas), 0))})', 'Antes: If(IsBlank(q), -1, Coalesce(Value(q.Personas), 0)), Dato: !IsBlank(q)})')
    p.reemplazar_en_todo('Personas: 0, Evento: false, Antes: -1})', 'Personas: 0, Evento: false, Antes: -1, Dato: false})')
    # 2) tarjeta: 95 % blanco, borde lo dibuja la imagen, casilla en vez de − / +
    h = p.get(html_zona, "HtmlText")
    h = rep(h, 'If(varTema = "oscuro", "rgba(58,58,62,0.78)", "rgba(255,255,255,0.78)")', 'If(varTema = "oscuro", "rgba(58,58,62,0.95)", "rgba(255,255,255,0.95)")', 1, html_zona)
    i, j = h.index(viejo_ini), h.index(viejo_fin) + len(viejo_fin)
    h = h[:i] + nuevo_medio + h[j:]
    for viejo, nuevo in borde_rect:
        h = rep(h, viejo, nuevo, 1, html_zona)
    p.set(html_zona, "HtmlText", h)
    gal = "galZonasCt" + suf
    p.quitar("btnMenosCt" + suf)
    p.quitar("btnMas" + "Ct" + suf)
    p.clonar("imgBrilloFondoCt" + suf, "imgBordeZonaCt" + suf, gal, {
        "Image": borde_img[0], "X": f"{S} * (0)", "Y": f"{S} * (0)", "Width": f"{S} * ({borde_img[1]})", "Height": f"{S} * ({borde_img[2]})",
        "ZIndex": "2", "Visible": "true", "TabIndex": "-1"}, despues_de="htmlZonaCt" + suf)
    x, y, w, hh, tam = casilla
    txt = "txtPersCt" + suf
    p.clonar("txtZPueCt" + suf, txt, gal, {
        "Default": 'If(ThisItem.Dato, Text(ThisItem.Personas), "")',
        "DelayOutput": "false", "HintText": '""', "MaxLength": "4", "Format": "TextFormat.Number",
        "AccessibleLabel": '"Personas en " & ThisItem.Zona', "Tooltip": '"Escriba cuántas personas hay en " & ThisItem.Zona',
        "OnChange": 'Patch(colCtCuenta' + ', ThisItem, {Personas: If(IsBlank(Self.Text), 0, Max(0, RoundDown(Value(Self.Text), 0))), Dato: !IsBlank(Self.Text)})',
        "Color": f'If(Host.OSType = "iOS", RGBA(0, 0, 0, 0), ColorValue({NEGRO_MET}))',
        "Fill": "RGBA(0, 0, 0, 0)", "HoverFill": "RGBA(0, 0, 0, 0)", "PressedFill": "RGBA(0, 0, 0, 0)", "DisabledFill": "RGBA(0, 0, 0, 0)",
        "BorderThickness": f"{S} * (0)", "FocusedBorderThickness": f"{S} * (0)", "HoverBorderColor": "RGBA(0, 0, 0, 0)",
        "DisplayMode": "If(varCtGuardando, DisplayMode.Disabled, DisplayMode.Edit)",
        "Align": "Align.Center", "FontWeight": "FontWeight.Bold",
        "Size": f'If(Host.OSType = "iOS", Max(13, {S} * ({tam})), {S} * ({tam}))',
        "PaddingLeft": f"{S} * (2)", "PaddingRight": f"{S} * (2)", "PaddingTop": f"{S} * (0)", "PaddingBottom": f"{S} * (0)",
        "X": f"{S} * ({x})", "Y": f"{S} * ({y})", "Width": f"{S} * ({w})", "Height": f"{S} * ({hh})",
        "Visible": "true", "ZIndex": "6", "TabIndex": "0"})
    p.clonar("lblIOSe_txtZPueCt" + suf, "lblIOSe_" + txt, gal, {
        "Text": f"{txt}.Text", "Color": f"ColorValue({NEGRO_MET})", "Fill": "RGBA(0, 0, 0, 0)",
        "Align": "Align.Center", "FontWeight": "FontWeight.Bold",
        "Size": f"Max(13, {S} * ({tam}))",
        "X": f"({S} * ({x})) + {S} * (4.2)", "Y": f"({S} * ({y})) + {S} * (4.2)",
        "Width": f"({S} * ({w})) - {S} * (8.4)", "Height": f"({S} * ({hh})) - {S} * (8.4)",
        "Visible": 'Host.OSType = "iOS"', "ZIndex": "5"}, despues_de="btnEventoCt" + suf)


def tabla_ocupacion(p, suf):
    n1 = p.reemplazar_en_todo(COL_OCU_VIEJO_1, COL_OCU_NUEVO)
    n2 = p.reemplazar_en_todo(COL_OCU_VIEJO_2, COL_OCU_NUEVO)
    n3 = p.reemplazar_en_todo('n: CountRows(rs), pers: If(IsEmpty(rs), -1, Round(Average(rs, p), 0))', 'n: CountRows(rs), tot: If(IsEmpty(rs), -1, Sum(rs, p)), pers: If(IsEmpty(rs), -1, Round(Average(rs, p), 0))')
    pant = "Contador" + suf
    p.editar(pant, "OnVisible", 'If(IsBlank(varCtPer), Set(varCtPer, "Hoy"));', 'Set(varCtPer, "Hoy"); Set(varCtFOcu, Today()); Set(varCtCalOn, false); ClearCollect(colCtOcuSrc, FirstN(colCtRec, 0));')
    return n1, n2, n3


# ================================================================ PANTALLA COMPUTADOR
pc = Pantalla("2038.json")
medio_pc = ('<div style=\'position:absolute;left:16px;top:52px;width:112px;height:52px;box-sizing:border-box;border-radius:14px;background:" & (If(varTema = "oscuro", "#2C2C2E", "#FFFFFF")) & ";border:1.5px solid " & ' + BORDE_CASILLA.format(txt="txtPersCt") + ' & ";text-align:center;line-height:49px;font-size:28px;font-weight:800;color:" & ' + NEGRO_MET + ' & "\'>" & If(IsBlank(txtPersCt.Text), "—", "") & "</div>'
            '<div style=\'position:absolute;left:142px;right:16px;top:57px\'><div style=\'font-size:13px;font-weight:800;color:" & ' + ESTADO_COLOR + ' & "\'>" & ' + ESTADO + ' & "</div><div style=\'font-size:10.5px;margin-top:4px;color:" & (' + TEMA_SUB + ') & "\'>" & If(ThisItem.Dato, "Toque el número para cambiarlo", "Toque y escriba la cantidad") & "</div></div>')
contador(pc, "", S_PC, "htmlZonaCt",
         "<div style='position:absolute;left:16px;top:52px;width:52px;", ">+</div>", medio_pc,
         (16, 52, 112, 52, 22), None, (img_borde(360, 148, 20, 1), 360, 148),
         [(';border:1px solid " & (If(varTema = "oscuro", "rgba(255,255,255,0.22)", "rgba(255,255,255,0.95)")) & ";box-shadow', ';border:1px solid transparent;box-shadow')])

# panel derecho: avance de espacios con dato + nota más abajo para dar espacio al botón «Poner 0»
avance_pc = '<div style=\'position:absolute;left:22px;right:22px;top:244px\'><div style=\'display:flex;justify-content:space-between;align-items:baseline;font-size:10px;letter-spacing:1px;font-weight:700;color:" & (If(varTema = "oscuro", "#C7C7CC", "#3F4247")) & "\'><span>ESPACIOS CON DATO</span><span style=\'font-size:12px;letter-spacing:0;color:" & (If(varTema = "oscuro", "#F2F2F7", "#1C1C1E")) & "\'>" & CountRows(Filter(colCtCuenta, Dato)) & " de " & CountRows(colCtCuenta) & "</span></div><div style=\'font-size:10.5px;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:" & (If(varTema = "oscuro", "#C7C7CC", "#3F4247")) & "\'>" & With({fz: Filter(colCtCuenta, !Dato)}, If(IsEmpty(fz), "Todos los espacios tienen dato.", "Faltan: " & Concat(FirstN(fz, 3), Zona, ", ") & If(CountRows(fz) > 3, " y " & (CountRows(fz) - 3) & " más", "") & ". Si guarda ahora, quedan en 0.")) & "</div></div>'
pc.editar("htmlCardDerCt", "HtmlText", "<div style='position:absolute;left:22px;right:22px;top:418px;", avance_pc + "<div style='position:absolute;left:22px;right:22px;top:462px;")
y_noreal = pc.get("btnNoRealCt", "Y")
pc.clonar("btnNoRealCt", "btnCerosCt", "Contador", {
    "Text": '"Poner 0 en los espacios vacíos"', "Tooltip": '"Escribe 0 en los espacios que quedaron sin dato"',
    "OnSelect": 'UpdateIf(colCtCuenta, !Dato, {Personas: 0, Dato: true})',
    "DisplayMode": 'If(varCtGuardando || IsEmpty(Filter(colCtCuenta, !Dato)), DisplayMode.Disabled, DisplayMode.Edit)',
    "Y": f"({y_noreal}) + {S_PC} * (56)", "Height": f"{S_PC} * (40)",
    "RadiusTopLeft": f"{S_PC} * (20.0)", "RadiusTopRight": f"{S_PC} * (20.0)", "RadiusBottomLeft": f"{S_PC} * (20.0)", "RadiusBottomRight": f"{S_PC} * (20.0)",
    "DisabledFill": 'ColorValue(If(varTema = "oscuro", "#2C2C2E", "#FFFFFF"))', "DisabledColor": 'ColorValue(If(varTema = "oscuro", "#636366", "#AEAEB2"))',
    "DisabledBorderColor": 'ColorValue(If(varTema = "oscuro", "#5A5D62", "#CDD0D5"))'}, despues_de="btnNoRealCt")

# tabla de ocupación (computador)
tabla_ocupacion(pc, "")
t = pc.get("htmlTablaOcuCt", "HtmlText")
t = rep(t, "<div style='width:120px;text-align:center'>Bloque</div><div style='width:90px;text-align:center'>Rondas</div><div style='width:150px;text-align:center'>Personas (prom.)</div><div style='width:140px;text-align:center'>Ocupación prom.</div><div style='width:130px;text-align:center'>Ocupación máx.</div><div style='width:112px;text-align:center'>Uso biblioteca</div>",
        "<div style='width:100px;text-align:center'>Bloque</div><div style='width:84px;text-align:center'>Rondas</div><div style='width:108px;text-align:center;line-height:1.15'>Personas<br>(total)</div><div style='width:110px;text-align:center;line-height:1.15'>Personas<br>(prom.)</div><div style='width:124px;text-align:center'>Ocupación prom.</div><div style='width:106px;text-align:center'>Ocupación máx.</div><div style='width:107px;text-align:center'>Uso biblioteca</div>", 1, "tabla pc encabezado")
t = rep(t, "<div style='width:120px;text-align:center;font-weight:700'>\" & fr & \"</div><div style='width:90px;text-align:center'>\" & If(n > 0, n & \" rondas\", \"Pendiente\") & \"</div><div style='width:150px;text-align:center'>\" & If(pers < 0, \"—\", pers) & \"</div><div style='width:140px;text-align:center;font-weight:700'>\"",
        "<div style='width:100px;text-align:center;font-weight:700'>\" & fr & \"</div><div style='width:84px;text-align:center'>\" & If(n > 0, n & \" rondas\", \"Pendiente\") & \"</div><div style='width:108px;text-align:center;font-weight:800'>\" & If(tot < 0, \"—\", Text(tot, \"#,0\", \"es-CL\")) & \"</div><div style='width:110px;text-align:center'>\" & If(pers < 0, \"—\", pers) & \"</div><div style='width:124px;text-align:center;font-weight:700'>\"", 1, "tabla pc fila")
t = rep(t, "\"</div><div style='width:130px;text-align:center'>\" & If((mx)", "\"</div><div style='width:106px;text-align:center'>\" & If((mx)", 1, "tabla pc fila máx")
t = rep(t, "\"</div><div style='width:112px;text-align:center'>\" & If((bib)", "\"</div><div style='width:107px;text-align:center'>\" & If((bib)", 1, "tabla pc fila bib")
t = rep(t, "<div style='width:120px;text-align:center'>\" & (If(varCtPer = \"Semana\", \"7 días\", \"Día\")) & \"</div><div style='width:90px;text-align:center'>\" & (CountRows(colCtR)) & \" rondas</div><div style='width:150px;text-align:center'>\" & (If(IsEmpty(colCtR), \"—\", Round(Average(colCtR, p), 0))) & \"</div><div style='width:140px;text-align:center'>\"",
        "<div style='width:100px;text-align:center'>\" & (If(varCtPer = \"Semana\", \"7 días\", \"Día\")) & \"</div><div style='width:84px;text-align:center'>\" & (CountRows(colCtR)) & \" rondas</div><div style='width:108px;text-align:center;font-weight:800'>\" & (If(IsEmpty(colCtR), \"—\", Text(Sum(colCtR, p), \"#,0\", \"es-CL\"))) & \"</div><div style='width:110px;text-align:center'>\" & (If(IsEmpty(colCtR), \"—\", Round(Average(colCtR, p), 0))) & \"</div><div style='width:124px;text-align:center'>\"", 1, "tabla pc pie")
t = rep(t, "</div><div style='width:130px;text-align:center'>\" & (If((If(IsEmpty(Filter(colCtR, c > 0)), -1, Max(", "</div><div style='width:106px;text-align:center'>\" & (If((If(IsEmpty(Filter(colCtR, c > 0)), -1, Max(", 1, "tabla pc pie máx")
t = rep(t, "</div><div style='width:112px;text-align:center'>\" & (If((If(Coalesce(Sum(colCtR, p), 0) = 0", "</div><div style='width:107px;text-align:center'>\" & (If((If(Coalesce(Sum(colCtR, p), 0) = 0", 1, "tabla pc pie bib")
t = rep(t, "Cifra oficial = <b>ocupación promedio</b>", "Personas (total) = suma de los conteos de todas las rondas del bloque. Cifra oficial = <b>ocupación promedio</b>", 1, "tabla pc nota")
pc.set("htmlTablaOcuCt", "HtmlText", t)
pc.editar("htmlCardCurvaCt", "HtmlText", '(If(varCtPer = "Semana", "PROMEDIO 7 DÍAS", "HOY"))', '(If(varCtPer = "Semana", "PROMEDIO 7 DÍAS", If(Coalesce(varCtFOcu, Today()) = Today(), "HOY", Text(varCtFOcu, "dd-mm-yyyy"))))')
pc.editar("imgCurvaCt", "Image", 'd: DateAdd(Today(), -o.Value, TimeUnit.Days)', 'd: DateAdd(Coalesce(varCtFOcu, Today()), -o.Value, TimeUnit.Days)')
pc.editar("imgCurvaCt", "Image", 'If(n = 1, "Hoy", ', 'If(n = 1, If(dd.d = Today(), "Hoy", Text(dd.d, "dd-mm")), ')

# fecha: la pastilla «Hoy / 7 días» pasa a ser el botón de la fecha
cadena_pc = pc.get("btnPerHoyCt", "OnSelect").split('Set(varCtPer, "Hoy"); ', 1)[1]
elegir = lambda fecha: f'Set(varCtFOcu, {fecha}); Set(varCtCalOn, false); {cargar_dia_antiguo()}; {cadena_pc}'
pc.set("htmlPerCt", "HtmlText", html_envoltorio_pc(html_pastilla_fecha(u_pc, 244, 42)))
pc.set("btnPerHoyCt", "OnSelect", 'If(varCtCalOn, Set(varCtCalOn, false), Set(varCtCalOn, true); ' + armar_calendario('Date(Year(varCtFOcu), Month(varCtFOcu), 1)') + ')')
pc.set("btnPerHoyCt", "Width", f"{S_PC} * (240)")
pc.set("btnPerHoyCt", "Tooltip", '"Elegir la fecha"')
pc.set("btnPerHoyCt", "AccessibleLabel", '"Fecha de la tabla: " & Text(varCtFOcu, "dd-mm-yyyy") & ". Toque para elegir otra"')
pc.set("btnPerSemCt", "Visible", "false")

x_pc = lambda dx: f"((App.Width - 1366 * {S_PC}) / 2) + {S_PC} * ({dx})"
y_tab = pc.get("htmlTablaOcuCt", "Y")
y_pc = lambda dy: f"({y_tab}) + {S_PC} * ({dy})"
vis_cal = "varCtTab = 2 && varCtCalOn"
TR = {"Fill": "RGBA(0, 0, 0, 0)", "HoverFill": "RGBA(0, 0, 0, 0)", "PressedFill": "RGBA(127, 127, 127, 0.10)", "DisabledFill": "RGBA(0, 0, 0, 0)",
      "Color": "RGBA(0, 0, 0, 0)", "DisabledColor": "RGBA(0, 0, 0, 0)", "Text": '""', "BorderThickness": "0", "FocusedBorderThickness": "0"}
pc.clonar("btnPerSemCt", "btnCalCerrarCt", "Contador", dict(TR, **{
    "X": pc.get("htmlTablaOcuCt", "X"), "Y": y_tab, "Width": pc.get("htmlTablaOcuCt", "Width"), "Height": pc.get("htmlTablaOcuCt", "Height"),
    "OnSelect": "Set(varCtCalOn, false)", "Visible": vis_cal, "Tooltip": '"Cerrar el calendario"', "TabIndex": "-1",
    "PressedFill": "RGBA(0, 0, 0, 0)", "RadiusTopLeft": "0", "RadiusTopRight": "0", "RadiusBottomLeft": "0", "RadiusBottomRight": "0"}))
pc.clonar("htmlPerCt", "htmlCalCt", "Contador", {
    "HtmlText": html_envoltorio_pc(html_calendario(u_pc)), "X": x_pc(562), "Y": y_pc(-8), "Width": f"{S_PC} * (299)", "Height": f"{S_PC} * (333)", "Visible": vis_cal})
for nombre, dx, dy, w, h, accion, tip in [
        ("btnCalAntCt", 562 + 14, -8 + 14, 36, 36, armar_calendario("DateAdd(varCtCalMes, -1, TimeUnit.Months)"), "Mes anterior"),
        ("btnCalSigCt", 562 + 246, -8 + 14, 36, 36, armar_calendario("DateAdd(varCtCalMes, 1, TimeUnit.Months)"), "Mes siguiente"),
        ("btnCalHoyCt", 562 + 226, -8 + 294, 58, 28, elegir("Today()"), "Ver hoy")]:
    pc.clonar("btnPerSemCt", nombre, "Contador", dict(TR, **{
        "X": x_pc(dx), "Y": y_pc(dy), "Width": f"{S_PC} * ({w})", "Height": f"{S_PC} * ({h})", "OnSelect": accion, "Visible": vis_cal,
        "Tooltip": f'"{tip}"', "AccessibleLabel": f'"{tip}"', "RadiusTopLeft": f"{S_PC} * ({h / 2})", "RadiusTopRight": f"{S_PC} * ({h / 2})",
        "RadiusBottomLeft": f"{S_PC} * ({h / 2})", "RadiusBottomRight": f"{S_PC} * ({h / 2})"}))
gal = pc.clonar("galZonasCt", "galCalCt", "Contador", {
    "Items": "colCtCal", "WrapCount": "7", "TemplateSize": f"{S_PC} * (36)", "TemplatePadding": f"{S_PC} * (0)",
    "X": x_pc(562 + 14), "Y": y_pc(-8 + 78), "Width": f"{S_PC} * (268)", "Height": f"{S_PC} * (216)", "Visible": vis_cal,
    "DelayItemLoading": "false", "FocusedBorderThickness": f"{S_PC} * (0)"})
gal["Children"] = [h for h in gal["Children"] if h["Template"]["Name"] == "galleryTemplate"]
gal["Children"][0]["Name"] = "galCalCttemplate1"
gal["Children"][0]["Parent"] = "galCalCt"
pc.clonar("btnPerSemCt", "btnDiaCalCt", "galCalCt", dict(TR, **{
    "X": f"{S_PC} * (0)", "Y": f"{S_PC} * (0)", "Width": "Parent.TemplateWidth", "Height": "Parent.TemplateHeight",
    "OnSelect": "If(ThisItem.mesOk && !ThisItem.fut, " + elegir("ThisItem.f") + ")",
    "DisplayMode": "If(ThisItem.mesOk && !ThisItem.fut, DisplayMode.Edit, DisplayMode.Disabled)",
    "Visible": "true", "Tooltip": 'Text(ThisItem.f, "dd-mm-yyyy")', "AccessibleLabel": 'Text(ThisItem.f, "dd-mm-yyyy") & If(ThisItem.hay, ", con rondas", "")',
    "RadiusTopLeft": f"{S_PC} * (16)", "RadiusTopRight": f"{S_PC} * (16)", "RadiusBottomLeft": f"{S_PC} * (16)", "RadiusBottomRight": f"{S_PC} * (16)"}))
# capas: el calendario queda sobre la tabla
z = max(int(pc.get(h, "ZIndex") or 0) for h in [c["Name"] for c in pc.top["Children"]] if pc.get(h, "ZIndex") and pc.get(h, "ZIndex").isdigit())
for k, nombre in enumerate(["btnCalCerrarCt", "htmlCalCt", "galCalCt", "btnCalAntCt", "btnCalSigCt", "btnCalHoyCt"]):
    pc.set(nombre, "ZIndex", str(z + 1 + k))
pc.set("btnCerosCt", "ZIndex", str(z + 7))

# ================================================================ PANTALLA CELULAR
m = Pantalla("2155.json")
um = mk_u_m(596)
medio_m = ('<div style=\'position:absolute;left:' + um(20) + ';top:' + um(64) + ';width:' + um(140) + ';height:' + um(66) + ';box-sizing:border-box;border-radius:' + um(16) + ';background:" & (If(varTema = "oscuro", "#2C2C2E", "#FFFFFF")) & ";border:' + um(1.5) + ' solid " & ' + BORDE_CASILLA.format(txt="txtPersCtM") + ' & ";text-align:center;line-height:' + um(63) + ';font-size:' + um(34) + ';font-weight:800;color:" & ' + NEGRO_MET + ' & "\'>" & If(IsBlank(txtPersCtM.Text), "—", "") & "</div>'
           '<div style=\'position:absolute;left:' + um(180) + ';right:' + um(20) + ';top:' + um(70) + '\'><div style=\'font-size:' + um(17) + ';font-weight:800;color:" & ' + ESTADO_COLOR + ' & "\'>" & ' + ESTADO + ' & "</div><div style=\'font-size:' + um(13) + ';margin-top:' + um(4) + ';color:" & (' + TEMA_SUB + ') & "\'>" & If(ThisItem.Dato, "Toque el número para cambiarlo", "Toque y escriba la cantidad") & "</div></div>')
contador(m, "M", S_M, "htmlZonaCtM",
         "<div style='position:absolute;left:3.356cqw;top:10.738cqw;width:11.074cqw;", ">+</div>", medio_m,
         (20, 64, 140, 66, 26), None, (img_borde(592, 182, 22, 1.6), 592, 182),
         [(';border:0.168cqw solid #CDD0D5;', ';border:0.168cqw solid transparent;')])

kpi = m.get("htmlKpiContarCtM", "HtmlText")
tile6 = ('"<div style=\'width:50%;padding:1.812cqw 0;text-align:center\'><div style=\'font-size:5.797cqw;font-weight:800;letter-spacing:-0.145cqw;line-height:1;color:" & (' + TEMA_TXT + ') & "\'>" & CountRows(Filter(colCtCuenta, Dato)) & " de " & CountRows(colCtCuenta) & "</div>'
         '<div style=\'font-size:2.083cqw;letter-spacing:0.181cqw;font-weight:600;margin-top:1.087cqw;color:" & (' + TEMA_SUB + ') & "\'>ESPACIOS CON DATO</div>'
         '<div style=\'font-size:2.083cqw;color:#8A8D91;white-space:nowrap;overflow:hidden;text-overflow:ellipsis\'>" & With({k: CountRows(Filter(colCtCuenta, !Dato))}, If(k = 0, "Todos con dato", "Faltan " & k & " · al guardar quedan en 0")) & "</div></div>"')
kpi = rep(kpi, '</div></div></div>") & "</div></div>"', '</div></div>" & ' + tile6 + ' & "</div>") & "</div></div>"', 1, "kpi celular")
kpi = rep(kpi, "height:37.681cqw", "height:50.362cqw", 1, "kpi celular alto")  # el contenido no cabía (ya pasaba antes)
m.set("htmlKpiContarCtM", "HtmlText", kpi)
m.editar("conKpiContarCtM", "Height", f"{S_M} * (261)", f"{S_M} * (325)")
m.editar("btnCardKpiContarCtM", "Height", f"{S_M} * (236)", f"{S_M} * (300)")
m.editar("htmlKpiContarCtM", "Height", f"{S_M} * (214)", f"{S_M} * (278)")
m.clonar("btnNoRealCtM", "btnCerosCtM", "conGuardarCtM", {
    "Text": '"Poner 0 en los espacios vacíos"', "Tooltip": '"Escribe 0 en los espacios que quedaron sin dato"',
    "OnSelect": 'UpdateIf(colCtCuenta, !Dato, {Personas: 0, Dato: true})',
    "DisplayMode": 'If(varCtGuardando || IsEmpty(Filter(colCtCuenta, !Dato)), DisplayMode.Disabled, DisplayMode.Edit)',
    "Y": f"{S_M} * (178)", "Height": f"{S_M} * (56)",
    "RadiusTopLeft": f"{S_M} * (28.0)", "RadiusTopRight": f"{S_M} * (28.0)", "RadiusBottomLeft": f"{S_M} * (28.0)", "RadiusBottomRight": f"{S_M} * (28.0)",
    "DisabledFill": 'ColorValue(If(varTema = "oscuro", "#2C2C2E", "#FFFFFF"))', "DisabledColor": 'ColorValue(If(varTema = "oscuro", "#636366", "#AEAEB2"))',
    "DisabledBorderColor": 'ColorValue(If(varTema = "oscuro", "#5A5D62", "#CDD0D5"))', "ZIndex": "5"}, despues_de="btnNoRealCtM")
m.editar("htmlNotaCtM", "Y", f"{S_M} * (180)", f"{S_M} * (246)")
m.editar("conGuardarCtM", "Height", f"{S_M} * (281)", f"{S_M} * (347)")

tabla_ocupacion(m, "M")
t = m.get("htmlTablaCtM", "HtmlText")
t = rep(t, "<span style='flex:1;text-align:center'>Rondas</span>", "<span style='flex:1;text-align:center'>Rondas</span><span style='flex:1;text-align:center'>Total</span>", 1, "tabla m encabezado")
t = rep(t, "<span style='flex:1;text-align:center'>\" & If(n > 0, n & \" rondas\", \"Pendiente\") & \"</span>",
        "<span style='flex:1;text-align:center'>\" & If(n > 0, n & \" rondas\", \"Pendiente\") & \"</span><span style='flex:1;text-align:center;font-weight:800'>\" & If(tot < 0, \"—\", Text(tot, \"#,0\", \"es-CL\")) & \"</span>", 1, "tabla m fila")
t = rep(t, "<span style='flex:1;text-align:center'>\" & (CountRows(colCtR)) & \" rondas</span>",
        "<span style='flex:1;text-align:center'>\" & (CountRows(colCtR)) & \" rondas</span><span style='flex:1;text-align:center'>\" & (If(IsEmpty(colCtR), \"—\", Text(Sum(colCtR, p), \"#,0\", \"es-CL\"))) & \"</span>", 1, "tabla m pie")
m.set("htmlTablaCtM", "HtmlText", t)
m.editar("imgCurvaCtM", "Image", 'd: DateAdd(Today(), -o.Value, TimeUnit.Days)', 'd: DateAdd(Coalesce(varCtFOcu, Today()), -o.Value, TimeUnit.Days)')
m.editar("imgCurvaCtM", "Image", 'If(n = 1, "Hoy", ', 'If(n = 1, If(dd.d = Today(), "Hoy", Text(dd.d, "dd-mm")), ')

cadena_m = m.get("btnPerHoyCtM", "OnSelect").split('Set(varCtPer, "Hoy"); ', 1)[1]
elegir_m = lambda fecha: f'Set(varCtFOcu, {fecha}); Set(varCtCalOn, false); {cargar_dia_antiguo()}; {cadena_m}'
upm = mk_u_m(214)
m.set("htmlPerCtM", "HtmlText", html_envoltorio_m(f"{50 / 214 * 100:.3f}", html_pastilla_fecha(upm, 210, 46)))
m.set("btnPerHoyCtM", "OnSelect", 'If(varCtCalOn, Set(varCtCalOn, false), Set(varCtCalOn, true); ' + armar_calendario('Date(Year(varCtFOcu), Month(varCtFOcu), 1)') + ')')
m.set("btnPerHoyCtM", "Width", f"{S_M} * (206)")
m.set("btnPerHoyCtM", "Tooltip", '"Elegir la fecha"')
m.set("btnPerHoyCtM", "AccessibleLabel", '"Fecha de la tabla: " & Text(varCtFOcu, "dd-mm-yyyy") & ". Toque para elegir otra"')
m.set("btnPerSemCtM", "Visible", "false")

ucm = mk_u_m(296)
vis_m = "varCtCalOn"
m.clonar("btnPerSemCtM", "btnCalCerrarCtM", "conTablaCtM", dict(TR, **{
    "X": f"{S_M} * (24)", "Y": f"{S_M} * (8)", "Width": f"{S_M} * (592)", "Height": f"{S_M} * (572)",
    "OnSelect": "Set(varCtCalOn, false)", "Visible": vis_m, "Tooltip": '"Cerrar el calendario"', "TabIndex": "-1", "PressedFill": "RGBA(0, 0, 0, 0)",
    "RadiusTopLeft": "0", "RadiusTopRight": "0", "RadiusBottomLeft": "0", "RadiusBottomRight": "0", "ZIndex": "57"}))
m.clonar("htmlPerCtM", "htmlCalCtM", "conTablaCtM", {
    "HtmlText": html_envoltorio_m(f"{330 / 296 * 100:.3f}", html_calendario(ucm)),
    "X": f"{S_M} * (300)", "Y": f"{S_M} * (76)", "Width": f"{S_M} * (296)", "Height": f"{S_M} * (330)", "Visible": vis_m, "ZIndex": "58"})
for k, (nombre, dx, dy, w, h, accion, tip) in enumerate([
        ("btnCalAntCtM", 300 + 14, 76 + 14, 36, 36, armar_calendario("DateAdd(varCtCalMes, -1, TimeUnit.Months)"), "Mes anterior"),
        ("btnCalSigCtM", 300 + 246, 76 + 14, 36, 36, armar_calendario("DateAdd(varCtCalMes, 1, TimeUnit.Months)"), "Mes siguiente"),
        ("btnCalHoyCtM", 300 + 226, 76 + 294, 58, 28, elegir_m("Today()"), "Ver hoy")]):
    m.clonar("btnPerSemCtM", nombre, "conTablaCtM", dict(TR, **{
        "X": f"{S_M} * ({dx})", "Y": f"{S_M} * ({dy})", "Width": f"{S_M} * ({w})", "Height": f"{S_M} * ({h})", "OnSelect": accion, "Visible": vis_m,
        "Tooltip": f'"{tip}"', "AccessibleLabel": f'"{tip}"', "ZIndex": str(60 + k),
        "RadiusTopLeft": f"{S_M} * ({h / 2})", "RadiusTopRight": f"{S_M} * ({h / 2})", "RadiusBottomLeft": f"{S_M} * ({h / 2})", "RadiusBottomRight": f"{S_M} * ({h / 2})"}))
galm = m.clonar("galZonasCtM", "galCalCtM", "conTablaCtM", {
    "Items": "colCtCal", "WrapCount": "7", "TemplateSize": f"{S_M} * (36)", "TemplatePadding": f"{S_M} * (0)",
    "X": f"{S_M} * ({300 + 14})", "Y": f"{S_M} * ({76 + 78})", "Width": f"{S_M} * (268)", "Height": f"{S_M} * (216)", "Visible": vis_m,
    "DelayItemLoading": "false", "FocusedBorderThickness": f"{S_M} * (0)", "ZIndex": "59"})
galm["Children"] = [h for h in galm["Children"] if h["Template"]["Name"] == "galleryTemplate"]
galm["Children"][0]["Name"] = "galCalCtMtemplate1"
galm["Children"][0]["Parent"] = "galCalCtM"
m.clonar("btnPerSemCtM", "btnDiaCalCtM", "galCalCtM", dict(TR, **{
    "X": f"{S_M} * (0)", "Y": f"{S_M} * (0)", "Width": "Parent.TemplateWidth", "Height": "Parent.TemplateHeight",
    "OnSelect": "If(ThisItem.mesOk && !ThisItem.fut, " + elegir_m("ThisItem.f") + ")",
    "DisplayMode": "If(ThisItem.mesOk && !ThisItem.fut, DisplayMode.Edit, DisplayMode.Disabled)",
    "Visible": "true", "Tooltip": 'Text(ThisItem.f, "dd-mm-yyyy")', "AccessibleLabel": 'Text(ThisItem.f, "dd-mm-yyyy") & If(ThisItem.hay, ", con rondas", "")',
    "RadiusTopLeft": f"{S_M} * (16)", "RadiusTopRight": f"{S_M} * (16)", "RadiusBottomLeft": f"{S_M} * (16)", "RadiusBottomRight": f"{S_M} * (16)", "ZIndex": "1"}))

renumerar([pc, m])
pc.guardar()
m.guardar()
print("Cambios aplicados en Contador y ContadorM.")

# ---------------------------------------------------------------- ajuste posterior (23-10, tarde)
# El equipo de Edif. A y Edif. F puede cambiar entre esas dos bibliotecas sin ser jefatura:
# en btnBibACt/btnBibFCt (y sus pares M) la condición `varCtBib <> "A"` / `varCtBib <> "F"`
# pasó a `!(varCtBib in ["A", "F"])`. Postgrado y Viña siguen fijas según la ficha de Personal.
# Además: filtro de fecha más angosto (htmlPerCt 212 de ancho en X 646; btnPerHoyCt 204 en X 650),
# contenido centrado, y se quitaron los botones ocultos btnPerSemCt / btnPerSemCtM.
