"""Intérprete mínimo de Power Fx para simular pantallas de la app BUAI.

Cubre las funciones que usan las fórmulas de posición, tamaño y HTML de las pantallas
(If, Switch, With, Text, Concat, Filter, Sum, etc.). No ejecuta acciones (Patch, Set…):
solo calcula valores. Si una fórmula usa algo que no cubre, lanza NoSoportado para que
el simulador lo informe en vez de inventar un resultado.
"""
import datetime as dt
import math
import re
import urllib.parse


class NoSoportado(Exception):
    pass


BLANK = None

# ------------------------------------------------------------------ análisis léxico
TOK = re.compile(r'''
    (?P<ws>\s+)
  | (?P<num>\d+\.\d*|\.\d+|\d+)
  | (?P<str>"(?:[^"]|"")*")
  | (?P<op>&&|\|\||<>|<=|>=|[-+*/^&=<>!(),;{}\[\]:.%@])
  | (?P<id>'[^']+'|[A-Za-z_À-ÿ][A-Za-z0-9_À-ÿ]*)
''', re.X)


def tokens(s):
    i, out = 0, []
    while i < len(s):
        m = TOK.match(s, i)
        if not m:
            raise NoSoportado(f"carácter inesperado {s[i]!r} en {s[max(0, i - 20):i + 20]!r}")
        i = m.end()
        k = m.lastgroup
        if k == "ws":
            continue
        v = m.group()
        if k == "str":
            out.append(("str", v[1:-1].replace('""', '"')))
        elif k == "num":
            out.append(("num", float(v)))
        elif k == "id":
            out.append(("id", v.strip("'")))
        else:
            out.append(("op", v))
    out.append(("eof", None))
    return out


# ------------------------------------------------------------------ análisis sintáctico (Pratt)
PREC = {"||": 1, "Or": 1, "&&": 2, "And": 2, "=": 3, "<>": 3, "<": 3, ">": 3, "<=": 3, ">=": 3, "in": 3, "exactin": 3,
        "&": 4, "+": 5, "-": 5, "*": 6, "/": 6, "^": 7}


class Parser:
    def __init__(self, s):
        self.t = tokens(s)
        self.i = 0

    def peek(self):
        return self.t[self.i]

    def next(self):
        tk = self.t[self.i]
        self.i += 1
        return tk

    def expect(self, v):
        tk = self.next()
        if tk[1] != v:
            raise NoSoportado(f"se esperaba {v!r} y vino {tk!r}")

    def parse(self):
        e = self.expr(0)
        if self.peek()[1] == ";":  # cadenas de acciones: solo interesa el valor de la primera
            raise NoSoportado("fórmula de comportamiento")
        if self.peek()[0] != "eof":
            raise NoSoportado(f"sobra {self.peek()!r}")
        return e

    def binop(self):
        tk = self.peek()
        if tk[0] in ("op", "id") and tk[1] in PREC:
            return tk[1]
        return None

    def expr(self, minp):
        left = self.unary()
        while True:
            op = self.binop()
            if op is None or PREC[op] <= minp:
                break
            self.next()
            right = self.expr(PREC[op] - 1 if op == "^" else PREC[op])
            left = ("bin", op, left, right)
        return left

    def unary(self):
        tk = self.peek()
        if tk[1] in ("!", "Not") and not (tk[1] == "Not" and self.t[self.i + 1][1] == "("):
            self.next()
            return ("not", self.unary())
        if tk[1] == "-":
            self.next()
            return ("neg", self.unary())
        if tk[1] == "+":
            self.next()
            return self.unary()
        return self.postfix(self.primary())

    def postfix(self, e):
        while True:
            tk = self.peek()
            if tk[1] == ".":
                self.next()
                name = self.next()[1]
                e = ("dot", e, name)
            elif tk[1] == "%":
                self.next()
                e = ("bin", "/", e, ("num", 100.0))
            else:
                return e

    def primary(self):
        tk = self.next()
        k, v = tk
        if k == "num":
            return ("num", v)
        if k == "str":
            return ("str", v)
        if v == "(":
            e = self.expr(0)
            self.expect(")")
            return e
        if v == "{":
            campos = []
            if self.peek()[1] != "}":
                while True:
                    nombre = self.next()[1]
                    self.expect(":")
                    campos.append((nombre, self.expr(0)))
                    if self.peek()[1] == ",":
                        self.next()
                        continue
                    break
            self.expect("}")
            return ("rec", campos)
        if v == "[":
            items = []
            if self.peek()[1] != "]":
                while True:
                    items.append(self.expr(0))
                    if self.peek()[1] == ",":
                        self.next()
                        continue
                    break
            self.expect("]")
            return ("tab", items)
        if k == "id":
            if v in ("true", "false"):
                return ("bool", v == "true")
            if self.peek()[1] == "(":
                self.next()
                args = []
                if self.peek()[1] != ")":
                    while True:
                        a = self.expr(0)
                        if self.peek()[0] == "id" and self.peek()[1] == "As":
                            self.next()
                            a = ("as", a, self.next()[1])
                        args.append(a)
                        if self.peek()[1] == ",":
                            self.next()
                            continue
                        break
                self.expect(")")
                return ("call", v, args)
            return ("id", v)
        raise NoSoportado(f"token inesperado {tk!r}")


_cache = {}


def compilar(s):
    if s not in _cache:
        _cache[s] = Parser(s.lstrip("=")).parse()
    return _cache[s]


# ------------------------------------------------------------------ valores
def es_blank(v):
    return v is None or v == ""


def num(v):
    if v is None or v == "":
        return 0.0
    if isinstance(v, bool):
        return 1.0 if v else 0.0
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, (dt.date, dt.datetime)):
        raise NoSoportado("número desde fecha")
    try:
        return float(str(v).replace(",", "."))
    except ValueError:
        return None


def txt(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, float):
        return str(int(v)) if v == int(v) else repr(v)
    if isinstance(v, dt.datetime):
        return v.strftime("%d-%m-%Y %H:%M")
    if isinstance(v, dt.date):
        return v.strftime("%d-%m-%Y")
    return str(v)


def fmt_num(v, f, loc):
    sep_mil, sep_dec = (".", ",") if loc.lower().startswith("es") else (",", ".")
    dec = len(f.split(".")[1]) if "." in f else 0
    entero_min = len(f.split(".")[0].replace("#", "").replace(",", ""))
    s = f"{abs(v):.{dec}f}"
    ent, _, fr = s.partition(".")
    ent = ent.zfill(entero_min)
    if "," in f.split(".")[0]:
        ent = f"{int(ent):,}".replace(",", sep_mil)
    return ("-" if v < 0 and float(s) != 0 else "") + ent + (sep_dec + fr if dec else "")


def fmt_fecha(v, f):
    m = {"yyyy": "%Y", "yy": "%y", "mm": "%m", "dd": "%d", "hh": "%H", "ss": "%S"}
    out, i = "", 0
    while i < len(f):
        for k in ("yyyy", "yy", "mm", "dd", "hh", "ss"):
            if f.startswith(k, i):
                if k == "mm" and "hh" in f[:i]:
                    out += v.strftime("%M")
                else:
                    out += v.strftime(m[k])
                i += len(k)
                break
        else:
            out += f[i]
            i += 1
    return out


ENUMS = {"TimeUnit", "StartOfWeek", "NotificationType", "DisplayMode", "Align", "VerticalAlign", "FontWeight", "Font",
         "TextFormat", "Layout", "LayoutMode", "LayoutDirection", "ScreenTransition", "Color", "SortOrder", "TextMode",
         "Overflow", "ImagePosition", "BorderStyle", "Transition", "LoadingSpinner", "LayoutAlignItems", "LayoutJustifyContent",
         "LayoutOverflow", "DropShadow", "Live", "TextRole", "VirtualKeyboardMode"}


class Entorno:
    """Contexto de evaluación: variables globales, colecciones, controles y ámbitos de registro."""

    def __init__(self, variables, colecciones, app, controles=None, hoy=dt.date(2026, 10, 23), ahora=None):
        self.var = variables
        self.col = colecciones
        self.app = app
        self.controles = controles or {}
        self.hoy = hoy
        self.ahora = ahora or dt.datetime.combine(hoy, dt.time(14, 20))

    # resolución de nombres -------------------------------------------------
    def nombre(self, n, ambitos):
        for a in reversed(ambitos):
            if n in a:
                return a[n]
        if n in self.var:
            return self.var[n]
        if n in self.col:
            return self.col[n]
        if n in ("ThisItem", "ThisRecord"):
            for a in reversed(ambitos):
                if "__registro__" in a:
                    return a["__registro__"]
            raise NoSoportado(f"{n} sin registro")
        if n == "Self":
            return ("__ctrl__", ambitos[0]["__self__"])
        if n == "Parent":
            return ("__ctrl__", self.controles[ambitos[0]["__self__"]].padre)
        if n in self.controles:
            return ("__ctrl__", n)
        if n in ("App", "Host"):
            return ("__obj__", n)
        if n in ENUMS:
            return ("__enum__", n)
        if n.startswith("var") or n.startswith("col"):
            return None  # variable no definida = Blank
        raise NoSoportado(f"nombre desconocido {n}")

    def miembro(self, base, campo, ambitos):
        if isinstance(base, tuple) and base and base[0] == "__ctrl__":
            return self.controles[base[1]].prop(campo, self)
        if isinstance(base, tuple) and base and base[0] == "__obj__":
            if base[1] == "App":
                if campo in self.app:
                    return self.app[campo]
                if campo == "Theme":
                    return ("__obj__", "Theme")
            if base[1] == "Host":
                return self.app["OSType"] if campo == "OSType" else None
            if base[1] in ("Theme", "Colors"):
                return ("__obj__", "Colors") if campo == "Colors" else "#3860B2"
            raise NoSoportado(f"{base[1]}.{campo}")
        if isinstance(base, tuple) and base and base[0] == "__enum__":
            return f"{base[1]}.{campo}"
        if isinstance(base, dict):
            return base.get(campo)
        if isinstance(base, list):  # columna de una tabla
            return [{"Value": r.get(campo)} for r in base]
        if base is None:
            return None
        raise NoSoportado(f"miembro {campo} de {type(base)}")

    # evaluación ------------------------------------------------------------
    def ev(self, n, ambitos):
        k = n[0]
        if k == "num":
            return n[1]
        if k == "str":
            return n[1]
        if k == "bool":
            return n[1]
        if k == "id":
            return self.nombre(n[1], ambitos)
        if k == "dot":
            return self.miembro(self.ev(n[1], ambitos), n[2], ambitos)
        if k == "not":
            return not self.verdad(self.ev(n[1], ambitos))
        if k == "neg":
            return -num(self.ev(n[1], ambitos))
        if k == "rec":
            return {c: self.ev(e, ambitos) for c, e in n[1]}
        if k == "tab":
            vals = [self.ev(e, ambitos) for e in n[1]]
            return [v if isinstance(v, dict) else {"Value": v} for v in vals]
        if k == "bin":
            return self.binario(n, ambitos)
        if k == "call":
            return self.llamar(n[1], n[2], ambitos)
        raise NoSoportado(k)

    def verdad(self, v):
        if isinstance(v, str):
            return v.lower() == "true"
        return bool(v)

    def binario(self, n, ambitos):
        op = n[1]
        if op in ("&&", "And"):
            return self.verdad(self.ev(n[2], ambitos)) and self.verdad(self.ev(n[3], ambitos))
        if op in ("||", "Or"):
            return self.verdad(self.ev(n[2], ambitos)) or self.verdad(self.ev(n[3], ambitos))
        a, b = self.ev(n[2], ambitos), self.ev(n[3], ambitos)
        if op == "&":
            return txt(a) + txt(b)
        if op in ("in", "exactin"):
            if isinstance(b, list):
                vals = [list(r.values())[0] if len(r) == 1 else r.get("Value") for r in b]
                return a in vals if op == "exactin" else txt(a).lower() in [txt(x).lower() for x in vals]
            return txt(a).lower() in txt(b).lower() if op == "in" else txt(a) in txt(b)
        if op in ("=", "<>"):
            if isinstance(a, (dt.date, dt.datetime)) or isinstance(b, (dt.date, dt.datetime)):
                r = a == b
            elif isinstance(a, bool) or isinstance(b, bool):
                r = self.verdad(a) == self.verdad(b)
            elif isinstance(a, (int, float)) or isinstance(b, (int, float)):
                r = num(a) == num(b)
            elif a is None or b is None:
                r = es_blank(a) and es_blank(b)
            elif isinstance(a, bool) or isinstance(b, bool):
                r = self.verdad(a) == self.verdad(b)
            else:
                r = txt(a) == txt(b)
            return r if op == "=" else not r
        if op in ("<", ">", "<=", ">="):
            if isinstance(a, (dt.date, dt.datetime)) or isinstance(b, (dt.date, dt.datetime)):
                x, y = a, b
            elif isinstance(a, str) and isinstance(b, str) and num(a) is None:
                x, y = a, b
            else:
                x, y = num(a), num(b)
            return {"<": x < y, ">": x > y, "<=": x <= y, ">=": x >= y}[op]
        x, y = num(a), num(b)
        if op == "+":
            return x + y
        if op == "-":
            return x - y
        if op == "*":
            return x * y
        if op == "/":
            if y == 0:
                raise NoSoportado("división por cero")
            return x / y
        if op == "^":
            return x ** y
        raise NoSoportado(op)

    def tabla(self, nodo, ambitos):
        t = self.ev(nodo, ambitos)
        if t is None:
            return []
        if not isinstance(t, list):
            raise NoSoportado("se esperaba una tabla")
        return t

    def por_registro(self, tabla, expr, ambitos, alias=None):
        for r in tabla:
            amb = ambitos + [dict(r, __registro__=r, **({alias: r} if alias else {}))]
            yield r, self.ev(expr, amb)

    def args_tabla(self, a, ambitos):
        alias = None
        if a[0] == "as":
            alias, a = a[2], a[1]
        return self.tabla(a, ambitos), alias

    def llamar(self, f, args, amb):
        ev = lambda i: self.ev(args[i], amb)
        if f == "If":
            i = 0
            while i + 1 < len(args):
                if self.verdad(ev(i)):
                    return ev(i + 1)
                i += 2
            return ev(i) if i < len(args) else None
        if f == "Switch":
            v = ev(0)
            i = 1
            while i + 1 < len(args):
                if txt(ev(i)) == txt(v) and (num(ev(i)) == num(v) if isinstance(v, float) else True):
                    return ev(i + 1)
                i += 2
            return ev(i) if i < len(args) else None
        if f == "With":
            rec = ev(0)
            return self.ev(args[1], amb + [dict(rec)])
        if f == "IfError":
            try:
                return ev(0)
            except NoSoportado:
                raise
        if f in ("Min", "Max"):
            first = ev(0) if args[0][0] != "as" else None
            if isinstance(first, list) or args[0][0] == "as":
                t, al = self.args_tabla(args[0], amb)
                vals = [num(v) for _, v in self.por_registro(t, args[1], amb, al) if v is not None]
                return (min if f == "Min" else max)(vals) if vals else None
            vals = [num(ev(i)) for i in range(len(args))]
            return (min if f == "Min" else max)(vals)
        if f in ("Sum", "Average", "CountIf"):
            t, al = self.args_tabla(args[0], amb)
            if f == "CountIf":
                return float(sum(1 for _, v in self.por_registro(t, args[1], amb, al) if self.verdad(v)))
            vals = [num(v) for _, v in self.por_registro(t, args[1], amb, al)]
            if f == "Sum":
                return float(sum(vals))
            return (sum(vals) / len(vals)) if vals else None
        if f == "Filter":
            t, al = self.args_tabla(args[0], amb)
            out = []
            for r in t:
                a2 = amb + [dict(r, __registro__=r, **({al: r} if al else {}))]
                if all(self.verdad(self.ev(c, a2)) for c in args[1:]):
                    out.append(r)
            return out
        if f == "LookUp":
            t, al = self.args_tabla(args[0], amb)
            for r in t:
                a2 = amb + [dict(r, __registro__=r, **({al: r} if al else {}))]
                if self.verdad(self.ev(args[1], a2)):
                    return self.ev(args[2], a2) if len(args) > 2 else r
            return None
        if f == "ForAll":
            t, al = self.args_tabla(args[0], amb)
            out = []
            for _, v in self.por_registro(t, args[1], amb, al):
                out.append(v if isinstance(v, dict) else {"Value": v})
            return out
        if f == "Concat":
            t, al = self.args_tabla(args[0], amb)
            sep = txt(ev(2)) if len(args) > 2 else ""
            return sep.join(txt(v) for _, v in self.por_registro(t, args[1], amb, al))
        if f == "CountRows":
            return float(len(self.tabla(args[0], amb)))
        if f == "IsEmpty":
            return len(self.tabla(args[0], amb)) == 0
        if f == "First":
            t = self.tabla(args[0], amb)
            return t[0] if t else None
        if f == "Last":
            t = self.tabla(args[0], amb)
            return t[-1] if t else None
        if f == "FirstN":
            return self.tabla(args[0], amb)[:int(num(ev(1)))]
        if f == "Index":
            t = self.tabla(args[0], amb)
            i = int(num(ev(1)))
            return t[i - 1] if 0 < i <= len(t) else None
        if f == "Sequence":
            n = int(num(ev(0)))
            ini = num(ev(1)) if len(args) > 1 else 1
            paso = num(ev(2)) if len(args) > 2 else 1
            return [{"Value": ini + k * paso} for k in range(n)]
        if f == "Sort":
            t, al = self.args_tabla(args[0], amb)
            claves = [(r, v) for r, v in self.por_registro(t, args[1], amb, al)]
            desc = len(args) > 2 and "Descending" in txt(ev(2))
            claves.sort(key=lambda x: (x[1] is None, num(x[1]) if isinstance(x[1], (int, float)) else txt(x[1])), reverse=desc)
            return [r for r, _ in claves]
        if f == "Distinct":
            t, al = self.args_tabla(args[0], amb)
            vistos = []
            for _, v in self.por_registro(t, args[1], amb, al):
                if v not in vistos:
                    vistos.append(v)
            return [{"Value": v} for v in vistos]
        if f == "Text":
            v = ev(0)
            if len(args) == 1:
                return txt(v)
            fmt = txt(ev(1))
            loc = txt(ev(2)) if len(args) > 2 else "es-CL"
            if isinstance(v, (dt.date, dt.datetime)):
                return fmt_fecha(v, fmt)
            if v is None:
                return ""
            return fmt_num(num(v), fmt, loc)
        if f == "Value":
            return num(ev(0))
        if f in ("Round", "RoundDown", "RoundUp"):
            v, d = num(ev(0)), int(num(ev(1)))
            fac = 10 ** d
            if f == "Round":
                return math.floor(abs(v) * fac + 0.5) / fac * (1 if v >= 0 else -1)
            if f == "RoundDown":
                return math.floor(abs(v) * fac) / fac * (1 if v >= 0 else -1)
            return math.ceil(abs(v) * fac) / fac * (1 if v >= 0 else -1)
        if f == "Coalesce":
            for i in range(len(args)):
                v = ev(i)
                if not es_blank(v):
                    return v
            return None
        if f == "IsBlank":
            return es_blank(ev(0))
        if f == "Not":
            return not self.verdad(ev(0))
        if f == "Upper":
            return txt(ev(0)).upper()
        if f == "Lower":
            return txt(ev(0)).lower()
        if f == "Proper":
            return txt(ev(0)).title()
        if f == "Trim":
            return " ".join(txt(ev(0)).split())
        if f == "Len":
            return float(len(txt(ev(0))))
        if f == "Left":
            return txt(ev(0))[:int(num(ev(1)))]
        if f == "Mid":
            s = txt(ev(0))
            ini = int(num(ev(1))) - 1
            return s[ini:ini + int(num(ev(2)))] if len(args) > 2 else s[ini:]
        if f == "Substitute":
            return txt(ev(0)).replace(txt(ev(1)), txt(ev(2)))
        if f == "Split":
            return [{"Value": x} for x in txt(ev(0)).split(txt(ev(1)))]
        if f == "EncodeUrl":
            return urllib.parse.quote(txt(ev(0)), safe="-_.!~*'()")
        if f == "Abs":
            return abs(num(ev(0)))
        if f == "Mod":
            return num(ev(0)) % num(ev(1))
        if f == "Pi":
            return math.pi
        if f == "Today":
            return self.hoy
        if f == "Now":
            return self.ahora
        if f == "Date":
            return dt.date(int(num(ev(0))), int(num(ev(1))), int(num(ev(2))))
        if f == "Time":
            return dt.time(int(num(ev(0))), int(num(ev(1))))
        if f in ("Day", "Month", "Year", "Hour"):
            v = ev(0)
            return float({"Day": v.day, "Month": v.month, "Year": v.year, "Hour": getattr(v, "hour", 0)}[f])
        if f == "Weekday":
            v = ev(0)
            lunes = len(args) > 1 and "Monday" in txt(ev(1))
            return float(v.isoweekday() if lunes else v.isoweekday() % 7 + 1)
        if f == "DateAdd":
            v, n = ev(0), int(num(ev(1)))
            unidad = txt(ev(2)) if len(args) > 2 else "Days"
            if "Month" in unidad:
                mes = v.month - 1 + n
                y, mm = v.year + mes // 12, mes % 12 + 1
                import calendar
                return v.replace(year=y, month=mm, day=min(v.day, calendar.monthrange(y, mm)[1]))
            return v + dt.timedelta(days=n)
        if f == "User":
            return {"Email": "rocio.arancibia@uai.cl", "FullName": "Rocío Arancibia", "Image": ""}
        if f in ("ColorValue", "RGBA", "ColorFade"):
            return "#color"
        raise NoSoportado(f"función {f}")


def evaluar(formula, entorno, ambitos):
    return entorno.ev(compilar(formula), ambitos)
