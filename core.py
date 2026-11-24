"""
core.py — Lógica de negocio del Procesador de Texto IA.

Contiene (sin nada de interfaz gráfica):
  · Modelo de formato: estilo por carácter (fuente, tamaño, negrita, cursiva, subrayado, color)
    y alineación por párrafo, aplicado sobre un widget Text de Tkinter mediante etiquetas.
  · Apertura y guardado compatibles: .docx (python-docx) y .txt (UTF-8).
  · Búsqueda y reemplazo.
  · Estadísticas del documento (palabras, caracteres, líneas).

Formato intercambiable del documento (lista de párrafos):
    [{"align": "left" | "center" | "right" | "justify", "runs": [(texto, Estilo), ...]}, ...]
"""

import re
from dataclasses import dataclass, replace
from pathlib import Path

FUENTES = ["Calibri", "Arial", "Times New Roman", "Courier New", "Segoe UI", "Verdana", "Georgia", "Tahoma"]
TAMANOS = [8, 9, 10, 11, 12, 14, 16, 18, 20, 24, 28, 36, 48, 72]
ALINEACIONES = ["left", "center", "right", "justify"]


@dataclass(frozen=True)
class Estilo:
    fuente: str = "Calibri"
    tamano: int = 11
    negrita: bool = False
    cursiva: bool = False
    subrayado: bool = False
    color: str = "#000000"

    def etiqueta(self) -> str:
        return f"st|{self.fuente}|{self.tamano}|{int(self.negrita)}|{int(self.cursiva)}|{int(self.subrayado)}|{self.color}"

    @staticmethod
    def desde_etiqueta(tag: str) -> "Estilo":
        _, fuente, tam, b, i, u, color = tag.split("|")
        return Estilo(fuente, int(tam), b == "1", i == "1", u == "1", color)

    def con(self, **cambios) -> "Estilo":
        return replace(self, **cambios)


ESTILO_BASE = Estilo()


class GestorFormato:
    """Aplica y lee estilos sobre un widget Text de Tkinter."""

    def __init__(self, texto, zoom=1.0):
        self.t = texto
        self.zoom = zoom
        self._configuradas = set()
        for a in ALINEACIONES:
            self.t.tag_configure("al|" + a, justify="left" if a == "justify" else a)

    # ---------- etiquetas ----------
    def asegurar(self, estilo: Estilo) -> str:
        tag = estilo.etiqueta()
        if tag not in self._configuradas:
            self._configurar(tag, estilo)
            self._configuradas.add(tag)
        return tag

    def _configurar(self, tag, e: Estilo):
        partes = []
        if e.negrita:
            partes.append("bold")
        if e.cursiva:
            partes.append("italic")
        if e.subrayado:
            partes.append("underline")
        tam = max(4, round(e.tamano * self.zoom))
        self.t.tag_configure(tag, font=(e.fuente, tam, " ".join(partes)), foreground=e.color)

    def aplicar_zoom(self, zoom: float):
        self.zoom = zoom
        for tag in self._configuradas:
            self._configurar(tag, Estilo.desde_etiqueta(tag))

    # ---------- lectura ----------
    def estilo_en(self, indice) -> Estilo:
        for tag in self.t.tag_names(indice):
            if tag.startswith("st|"):
                return Estilo.desde_etiqueta(tag)
        return ESTILO_BASE

    def alineacion_en(self, indice) -> str:
        for tag in self.t.tag_names(f"{indice} linestart"):
            if tag.startswith("al|"):
                return tag[3:]
        return "left"

    def segmentos(self, inicio, fin):
        """Devuelve [(texto, Estilo)] agrupando caracteres seguidos con el mismo estilo."""
        res = []
        i = self.t.index(inicio)
        fin = self.t.index(fin)
        actual, buf = None, []
        while self.t.compare(i, "<", fin):
            c = self.t.get(i)
            e = self.estilo_en(i)
            if e != actual and buf:
                res.append(("".join(buf), actual))
                buf = []
            actual = e
            buf.append(c)
            i = self.t.index(f"{i}+1c")
        if buf:
            res.append(("".join(buf), actual))
        return res

    # ---------- escritura ----------
    def cambiar_estilo(self, inicio, fin, funcion):
        """Aplica funcion(Estilo) -> Estilo a cada tramo del rango, conservando el resto del formato."""
        i = self.t.index(inicio)
        for texto, e in self.segmentos(inicio, fin):
            j = self.t.index(f"{i}+{len(texto)}c")
            self.t.tag_remove(e.etiqueta(), i, j)
            self.t.tag_add(self.asegurar(funcion(e)), i, j)
            i = j

    def alinear(self, inicio, fin, alineacion):
        a = self.t.index(f"{inicio} linestart")
        b = self.t.index(f"{fin} lineend+1c")
        for x in ALINEACIONES:
            self.t.tag_remove("al|" + x, a, b)
        self.t.tag_add("al|" + alineacion, a, b)

    def insertar(self, indice, texto, estilo: Estilo, alineacion=None):
        if alineacion is None:
            alineacion = self.alineacion_en(indice)
        self.t.insert(indice, texto, (self.asegurar(estilo), "al|" + alineacion))

    # ---------- documento completo ----------
    def a_modelo(self):
        parrafos = []
        ultima = int(self.t.index("end-1c").split(".")[0])
        for n in range(1, ultima + 1):
            ini, fin = f"{n}.0", f"{n}.end"
            parrafos.append({"align": self.alineacion_en(ini), "runs": self.segmentos(ini, fin)})
        return parrafos

    def desde_modelo(self, parrafos):
        self.t.delete("1.0", "end")
        for k, p in enumerate(parrafos):
            al = p.get("align", "left")
            for texto, e in p["runs"]:
                self.insertar("end-1c", texto, e, al)
            if k < len(parrafos) - 1:
                ultimo = p["runs"][-1][1] if p["runs"] else ESTILO_BASE
                self.insertar("end-1c", "\n", ultimo, al)


# =====================================================================
# ARCHIVOS (.docx / .txt)
# =====================================================================
FORMATOS = [
    ("Documento de Word", "*.docx"),
    ("Documento de texto", "*.txt"),
    ("Todos los archivos", "*.*"),
]


def abrir(ruta: str):
    """Lee un .docx o .txt y devuelve la lista de párrafos."""
    ext = Path(ruta).suffix.lower()
    if ext == ".docx":
        return leer_docx(ruta)
    datos = Path(ruta).read_bytes()
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = datos.decode("cp1252", errors="replace")   # .txt guardado por el Bloc de notas antiguo
    texto = texto.replace("\r\n", "\n")
    return [{"align": "left", "runs": [(linea, ESTILO_BASE)] if linea else []} for linea in texto.split("\n")]


def guardar(ruta: str, parrafos):
    """Guarda la lista de párrafos en .docx (con formato) o .txt (texto plano)."""
    if Path(ruta).suffix.lower() == ".docx":
        escribir_docx(ruta, parrafos)
    else:
        texto = "\r\n".join("".join(t for t, _ in p["runs"]) for p in parrafos)
        Path(ruta).write_text(texto, encoding="utf-8-sig")   # con BOM: WordPad y el Bloc de notas detectan UTF-8


def leer_docx(ruta):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH as A

    mapa = {A.CENTER: "center", A.RIGHT: "right", A.JUSTIFY: "justify"}
    doc = Document(ruta)
    parrafos = []
    for p in doc.paragraphs:
        runs = []
        for r in p.runs:
            if not r.text:
                continue
            f = r.font
            color = "#000000"
            if f.color is not None and f.color.type is not None and f.color.rgb is not None:
                color = "#" + str(f.color.rgb)
            runs.append((r.text, Estilo(
                fuente=f.name or "Calibri",
                tamano=int(f.size.pt) if f.size else 11,
                negrita=bool(r.bold), cursiva=bool(r.italic), subrayado=bool(r.underline),
                color=color.lower(),
            )))
        parrafos.append({"align": mapa.get(p.alignment, "left"), "runs": runs})
    return parrafos or [{"align": "left", "runs": []}]


def escribir_docx(ruta, parrafos):
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH as A
    from docx.shared import Pt, RGBColor

    mapa = {"left": A.LEFT, "center": A.CENTER, "right": A.RIGHT, "justify": A.JUSTIFY}
    doc = Document()
    for p in parrafos:
        par = doc.add_paragraph()
        par.alignment = mapa.get(p["align"], A.LEFT)
        for texto, e in p["runs"]:
            r = par.add_run(texto)
            r.bold, r.italic, r.underline = e.negrita, e.cursiva, e.subrayado
            r.font.name = e.fuente
            r.font.size = Pt(e.tamano)
            if e.color.lower() != "#000000":
                r.font.color.rgb = RGBColor.from_string(e.color[1:].upper())
    doc.save(ruta)


# =====================================================================
# BÚSQUEDA Y ESTADÍSTICAS
# =====================================================================
def buscar_todas(texto: str, patron: str, mayusculas: bool = False):
    """Devuelve las posiciones (inicio, fin) de todas las coincidencias en una cadena."""
    if not patron:
        return []
    flags = 0 if mayusculas else re.IGNORECASE
    return [(m.start(), m.end()) for m in re.finditer(re.escape(patron), texto, flags)]


def reemplazar_texto(texto: str, patron: str, nuevo: str, mayusculas: bool = False):
    """Reemplaza todas las coincidencias en una cadena; devuelve (texto_nuevo, cantidad)."""
    if not patron:
        return texto, 0
    flags = 0 if mayusculas else re.IGNORECASE
    return re.subn(re.escape(patron), lambda m: nuevo, texto, flags=flags)


def estadisticas(texto: str) -> dict:
    return {
        "palabras": len(re.findall(r"\w+", texto)),
        "caracteres": len(texto),
        "sin_espacios": len(re.sub(r"\s", "", texto)),
        "lineas": texto.count("\n") + 1 if texto else 0,
    }
