"""
ui.py — Interfaz gráfica del Procesador de Texto IA (Tkinter + ttk).

Replica la disposición ergonómica observada en WordPad (ingeniería inversa de caja negra):
  barra de menús · barra de herramientas por grupos (Archivo, Portapapeles, Fuente, Párrafo, Edición)
  · regla · hoja de edición · barra de estado en tiempo real
y añade un panel lateral "Asistente IA" (funcionalidad nueva).

La interfaz no contiene lógica de negocio: delega en core.py (formato, archivos, estadísticas)
y en ia.py (Gemini en hilo secundario).
"""

import queue
import time
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

import core
from core import ALINEACIONES, ESTILO_BASE, FUENTES, TAMANOS, GestorFormato
from ia import MODELOS, NOMBRES, AsistenteIA

NOMBRE_APP = "Procesador de Texto IA"


class ProcesadorIA:
    def __init__(self, raiz: tk.Tk):
        self.raiz = raiz
        self.ruta = None
        self.modificado = False
        self.estilo = ESTILO_BASE          # estilo con el que se escribe
        self.zoom = 1.0
        self.ia = AsistenteIA()
        self.ia_ocupada = False

        raiz.geometry("1180x720")
        raiz.minsize(800, 480)
        raiz.protocol("WM_DELETE_WINDOW", self.salir)
        self._estilos_ttk()
        self._menus()
        self._barra_herramientas()
        self._cuerpo()
        self._barra_estado()
        self._atajos()
        self.actualizar_titulo()
        self.actualizar_estado()
        self.texto.focus_set()

    # ================================================================== UI
    def _estilos_ttk(self):
        s = ttk.Style()
        try:
            s.theme_use("clam")
        except tk.TclError:
            pass
        s.configure("Cinta.TFrame", background="#f3f6fb")
        s.configure("Cinta.TLabel", background="#f3f6fb", foreground="#5b6475", font=("Segoe UI", 8))
        s.configure("Herr.TButton", padding=(3, 3))
        s.configure("Activo.TButton", padding=(3, 3), background="#cfe0fb")
        s.configure("IA.TButton", padding=(8, 5), foreground="#ffffff", background="#6d28d9")
        s.map("IA.TButton", background=[("active", "#7c3aed")])
        s.configure("Estado.TLabel", background="#e9edf3", foreground="#333", padding=(8, 2))

    def _menus(self):
        m = tk.Menu(self.raiz)
        archivo = tk.Menu(m, tearoff=0)
        archivo.add_command(label="Nuevo", accelerator="Ctrl+N", command=self.nuevo)
        archivo.add_command(label="Abrir…", accelerator="Ctrl+O", command=self.abrir)
        archivo.add_command(label="Guardar", accelerator="Ctrl+S", command=self.guardar)
        archivo.add_command(label="Guardar como…", accelerator="Ctrl+Mayús+S", command=self.guardar_como)
        archivo.add_separator()
        archivo.add_command(label="Salir", command=self.salir)
        m.add_cascade(label="Archivo", menu=archivo)

        editar = tk.Menu(m, tearoff=0)
        editar.add_command(label="Deshacer", accelerator="Ctrl+Z", command=lambda: self._edit("undo"))
        editar.add_command(label="Rehacer", accelerator="Ctrl+Y", command=lambda: self._edit("redo"))
        editar.add_separator()
        editar.add_command(label="Cortar", accelerator="Ctrl+X", command=lambda: self.texto.event_generate("<<Cut>>"))
        editar.add_command(label="Copiar", accelerator="Ctrl+C", command=lambda: self.texto.event_generate("<<Copy>>"))
        editar.add_command(label="Pegar", accelerator="Ctrl+V", command=self.pegar)
        editar.add_command(label="Seleccionar todo", accelerator="Ctrl+E", command=self.seleccionar_todo)
        editar.add_separator()
        editar.add_command(label="Buscar…", accelerator="Ctrl+F", command=lambda: self.buscar(False))
        editar.add_command(label="Reemplazar…", accelerator="Ctrl+H", command=lambda: self.buscar(True))
        m.add_cascade(label="Editar", menu=editar)

        formato = tk.Menu(m, tearoff=0)
        formato.add_command(label="Negrita", accelerator="Ctrl+B", command=lambda: self.alternar("negrita"))
        formato.add_command(label="Cursiva", accelerator="Ctrl+I", command=lambda: self.alternar("cursiva"))
        formato.add_command(label="Subrayado", accelerator="Ctrl+U", command=lambda: self.alternar("subrayado"))
        formato.add_command(label="Color de texto…", command=self.elegir_color)
        formato.add_separator()
        for a, nombre, tecla in [("left", "Alinear a la izquierda", "Ctrl+L"), ("center", "Centrar", "Ctrl+Mayús+C"),
                                 ("right", "Alinear a la derecha", "Ctrl+R"), ("justify", "Justificar", "Ctrl+J")]:
            formato.add_command(label=nombre, accelerator=tecla, command=lambda a=a: self.alinear(a))
        m.add_cascade(label="Formato", menu=formato)

        insertar = tk.Menu(m, tearoff=0)
        insertar.add_command(label="Fecha y hora", accelerator="F5", command=self.insertar_fecha)
        m.add_cascade(label="Insertar", menu=insertar)

        ver = tk.Menu(m, tearoff=0)
        ver.add_command(label="Acercar", accelerator="Ctrl++", command=lambda: self.cambiar_zoom(0.1))
        ver.add_command(label="Alejar", accelerator="Ctrl+-", command=lambda: self.cambiar_zoom(-0.1))
        ver.add_command(label="Zoom 100 %", accelerator="Ctrl+0", command=lambda: self.cambiar_zoom(None))
        ver.add_separator()
        ver.add_command(label="Mostrar/ocultar Asistente IA", accelerator="F1", command=self.alternar_panel)
        m.add_cascade(label="Ver", menu=ver)

        ia = tk.Menu(m, tearoff=0)
        ia.add_command(label="Corrector de estilo semántico", accelerator="Ctrl+Mayús+E", command=lambda: self.usar_ia("corregir"))
        ia.add_command(label="Resumen automático", accelerator="Ctrl+Mayús+R", command=lambda: self.usar_ia("resumir"))
        ia.add_command(label="Autocompletado contextual", accelerator="Ctrl+Espacio", command=lambda: self.usar_ia("continuar"))
        ia.add_separator()
        ia.add_command(label="Configurar API Key…", command=self.configurar_ia)
        m.add_cascade(label="IA", menu=ia)

        ayuda = tk.Menu(m, tearoff=0)
        ayuda.add_command(label="Acerca de", command=self.acerca)
        m.add_cascade(label="Ayuda", menu=ayuda)
        self.raiz.config(menu=m)

    def _grupo(self, barra, titulo):
        g = ttk.Frame(barra, style="Cinta.TFrame", padding=(6, 4, 6, 0))
        g.pack(side="left", fill="y")
        fila = ttk.Frame(g, style="Cinta.TFrame")
        fila.pack(side="top")
        ttk.Label(g, text=titulo, style="Cinta.TLabel").pack(side="bottom", pady=(2, 0))
        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", pady=6)
        return fila

    def _barra_herramientas(self):
        barra = ttk.Frame(self.raiz, style="Cinta.TFrame")
        barra.pack(side="top", fill="x")
        b = lambda p, t, c, w=None: ttk.Button(p, text=t, command=c, style="Herr.TButton", width=w)

        g = self._grupo(barra, "Archivo")
        for t, c in [("📄", self.nuevo), ("📂", self.abrir), ("💾", self.guardar)]:
            b(g, t, c, 3).pack(side="left", padx=1)

        g = self._grupo(barra, "Portapapeles")
        b(g, "📋", self.pegar, 3).pack(side="left", padx=1)
        b(g, "✂", lambda: self.texto.event_generate("<<Cut>>"), 3).pack(side="left", padx=1)
        b(g, "⧉", lambda: self.texto.event_generate("<<Copy>>"), 3).pack(side="left", padx=1)

        g = self._grupo(barra, "Fuente")
        self.var_fuente = tk.StringVar(value=self.estilo.fuente)
        cb = ttk.Combobox(g, textvariable=self.var_fuente, values=FUENTES, width=13)
        cb.pack(side="left", padx=1)
        cb.bind("<<ComboboxSelected>>", lambda e: self.cambiar("fuente", self.var_fuente.get()))
        cb.bind("<Return>", lambda e: self.cambiar("fuente", self.var_fuente.get()))
        self.var_tamano = tk.StringVar(value=str(self.estilo.tamano))
        ct = ttk.Combobox(g, textvariable=self.var_tamano, values=TAMANOS, width=4)
        ct.pack(side="left", padx=1)
        ct.bind("<<ComboboxSelected>>", lambda e: self._tamano_desde_combo())
        ct.bind("<Return>", lambda e: self._tamano_desde_combo())
        self.btn_fmt = {}
        for clave, txt in [("negrita", "N"), ("cursiva", "K"), ("subrayado", "S")]:
            bt = b(g, txt, lambda c=clave: self.alternar(c), 3)
            bt.pack(side="left", padx=1)
            self.btn_fmt[clave] = bt
        b(g, "🎨", self.elegir_color, 3).pack(side="left", padx=1)

        g = self._grupo(barra, "Párrafo")
        self.btn_al = {}
        for a, txt in zip(ALINEACIONES, ["⯇≡", "≡", "≡⯈", "☰"]):
            bt = b(g, txt, lambda a=a: self.alinear(a), 3)
            bt.pack(side="left", padx=1)
            self.btn_al[a] = bt

        g = self._grupo(barra, "Edición")
        b(g, "🔍", lambda: self.buscar(False), 3).pack(side="left", padx=1)
        b(g, "⇄", lambda: self.buscar(True), 3).pack(side="left", padx=1)
        b(g, "🕒", self.insertar_fecha, 3).pack(side="left", padx=1)

        g = self._grupo(barra, "IA")
        ttk.Button(g, text="✨ Asistente", style="IA.TButton", command=self.alternar_panel).pack(side="left", padx=1)

    def _cuerpo(self):
        self.panel = ttk.PanedWindow(self.raiz, orient="horizontal")
        self.panel.pack(fill="both", expand=True)

        # --- "hoja" de papel sobre fondo gris, como WordPad ---
        fondo = tk.Frame(self.panel, bg="#d9dde4")
        regla = tk.Canvas(fondo, height=18, bg="#eef1f5", highlightthickness=0)
        regla.pack(side="top", fill="x")
        self.regla = regla
        hoja = tk.Frame(fondo, bg="#d9dde4")
        hoja.pack(fill="both", expand=True, padx=40, pady=(8, 0))
        barra_v = ttk.Scrollbar(hoja, orient="vertical")
        barra_v.pack(side="right", fill="y")
        self.texto = tk.Text(hoja, wrap="word", undo=True, autoseparators=True, maxundo=-1,
                             relief="flat", padx=48, pady=36, bg="white", insertwidth=2,
                             font=("Calibri", 11), yscrollcommand=barra_v.set, spacing1=2, spacing3=4,
                             selectbackground="#b9d3f5", selectforeground="black")
        self.texto.pack(fill="both", expand=True)
        barra_v.config(command=self.texto.yview)
        self.fmt = GestorFormato(self.texto)
        self.texto.tag_configure("encontrado", background="#ffe58a")
        self.panel.add(fondo, weight=4)
        regla.bind("<Configure>", lambda e: self._dibujar_regla())

        # --- panel del Asistente IA (funcionalidad nueva) ---
        self.panel_ia = ttk.Frame(self.panel, padding=10)
        ttk.Label(self.panel_ia, text="✨ Asistente IA", font=("Segoe UI", 13, "bold")).pack(anchor="w")
        ttk.Label(self.panel_ia, text="Selecciona texto (o nada para usar todo el documento)\n"
                                       "y elige una acción.", foreground="#666").pack(anchor="w", pady=(2, 8))
        for tarea, txt in [("corregir", "✔ Corregir estilo"), ("resumir", "📝 Resumir"),
                           ("continuar", "➜ Autocompletar")]:
            ttk.Button(self.panel_ia, text=txt, style="IA.TButton",
                       command=lambda t=tarea: self.usar_ia(t)).pack(fill="x", pady=2)
        self.lbl_ia = ttk.Label(self.panel_ia, text="Motor: " + self._motor_texto(), foreground="#555", wraplength=260)
        self.lbl_ia.pack(anchor="w", pady=(10, 4))
        self.barra_progreso = ttk.Progressbar(self.panel_ia, mode="indeterminate")
        self.barra_progreso.pack(fill="x")
        self.salida_ia = tk.Text(self.panel_ia, wrap="word", height=10, width=34, bg="#faf7ff",
                                 relief="solid", bd=1, font=("Segoe UI", 10), padx=8, pady=8)
        self.salida_ia.pack(fill="both", expand=True, pady=6)
        fila = ttk.Frame(self.panel_ia)
        fila.pack(fill="x")
        ttk.Button(fila, text="Insertar", command=self.insertar_resultado).pack(side="left", expand=True, fill="x")
        ttk.Button(fila, text="Reemplazar selección", command=self.reemplazar_con_resultado).pack(side="left", expand=True, fill="x")
        ttk.Button(self.panel_ia, text="⚙ Configurar API Key", command=self.configurar_ia).pack(fill="x", pady=(6, 0))
        self.panel.add(self.panel_ia, weight=1)
        self.panel_visible = True
        self.ultimo_resultado = ""
        self.ultima_seleccion = None

    def _barra_estado(self):
        self.var_estado = tk.StringVar()
        self.var_ia = tk.StringVar(value=self._estado_ia_inicial())
        barra = ttk.Frame(self.raiz)
        barra.pack(side="bottom", fill="x")
        ttk.Label(barra, textvariable=self.var_estado, style="Estado.TLabel").pack(side="left", fill="x", expand=True)
        ttk.Label(barra, textvariable=self.var_ia, style="Estado.TLabel").pack(side="right")

    def _dibujar_regla(self):
        c = self.regla
        c.delete("all")
        ancho = c.winfo_width()
        x0 = 40 + 48
        paso = 37.8 * self.zoom       # ~1 cm a 96 ppp
        n = 0
        x = x0
        while x < ancho - 40:
            alto = 8 if n % 2 == 0 else 4
            c.create_line(x, 18, x, 18 - alto, fill="#7a8494")
            if n % 2 == 0 and n:
                c.create_text(x, 5, text=str(n // 2), fill="#7a8494", font=("Segoe UI", 6))
            x += paso / 2
            n += 1

    # ================================================================ atajos
    def _atajos(self):
        t = self.texto
        pares = {
            "<Control-n>": self.nuevo, "<Control-o>": self.abrir, "<Control-s>": self.guardar,
            "<Control-S>": self.guardar_como, "<Control-b>": lambda: self.alternar("negrita"),
            "<Control-i>": lambda: self.alternar("cursiva"), "<Control-u>": lambda: self.alternar("subrayado"),
            "<Control-l>": lambda: self.alinear("left"), "<Control-C>": lambda: self.alinear("center"),
            "<Control-r>": lambda: self.alinear("right"), "<Control-j>": lambda: self.alinear("justify"),
            "<Control-f>": lambda: self.buscar(False), "<Control-h>": lambda: self.buscar(True),
            "<Control-e>": self.seleccionar_todo, "<Control-y>": lambda: self._edit("redo"),
            "<Control-plus>": lambda: self.cambiar_zoom(0.1), "<Control-equal>": lambda: self.cambiar_zoom(0.1),
            "<Control-minus>": lambda: self.cambiar_zoom(-0.1), "<Control-0>": lambda: self.cambiar_zoom(None),
            "<F5>": self.insertar_fecha, "<F1>": self.alternar_panel,
            "<Control-R>": lambda: self.usar_ia("resumir"), "<Control-E>": lambda: self.usar_ia("corregir"),
            "<Control-space>": lambda: self.usar_ia("continuar"),
        }
        for sec, fn in pares.items():
            t.bind(sec, lambda e, fn=fn: (fn(), "break")[1])
        t.bind("<<Paste>>", lambda e: (self.pegar(), "break")[1])
        t.bind("<Key>", self._tecla)
        t.bind("<<Modified>>", self._modificado)
        for ev in ("<KeyRelease>", "<ButtonRelease-1>"):
            t.bind(ev, lambda e: self.actualizar_estado(), add="+")

    def _tecla(self, ev):
        """Escribe cada carácter con el estilo y la alineación actuales (como WordPad)."""
        if ev.state & 0x4 or ev.state & 0x20000:           # Ctrl / Alt
            return None
        ch = ev.char
        if ev.keysym in ("Return", "KP_Enter"):
            ch = "\n"
        elif ev.keysym == "Tab":
            ch = "\t"
        if not ch or (ord(ch) < 32 and ch not in "\n\t"):
            return None
        self._borrar_seleccion()
        self.fmt.insertar("insert", ch, self.estilo, self.fmt.alineacion_en("insert"))
        self.texto.see("insert")
        return "break"

    def _borrar_seleccion(self):
        if self.texto.tag_ranges("sel"):
            self.texto.delete("sel.first", "sel.last")

    def _edit(self, que):
        try:
            self.texto.edit_undo() if que == "undo" else self.texto.edit_redo()
        except tk.TclError:
            pass

    # ============================================================== archivo
    def _modificado(self, _=None):
        if self.texto.edit_modified():
            self.modificado = True
            self.actualizar_titulo()
        self.texto.edit_modified(False)

    def actualizar_titulo(self):
        nombre = Path(self.ruta).name if self.ruta else "Documento"
        self.raiz.title(f"{'*' if self.modificado else ''}{nombre} - {NOMBRE_APP}")

    def _confirmar_descartar(self):
        if not self.modificado:
            return True
        r = messagebox.askyesnocancel(NOMBRE_APP, "¿Deseas guardar los cambios del documento?")
        if r is None:
            return False
        return self.guardar() if r else True

    def nuevo(self):
        if not self._confirmar_descartar():
            return
        self.texto.delete("1.0", "end")
        self.ruta, self.modificado, self.estilo = None, False, ESTILO_BASE
        self.texto.edit_reset()
        self.actualizar_titulo()
        self.actualizar_estado()

    def abrir(self, ruta=None):
        if not self._confirmar_descartar():
            return
        ruta = ruta or filedialog.askopenfilename(filetypes=core.FORMATOS)
        if not ruta:
            return
        try:
            inicio = time.perf_counter()
            self.fmt.desde_modelo(core.abrir(ruta))
            ms = round((time.perf_counter() - inicio) * 1000)
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(NOMBRE_APP, f"No se pudo abrir el archivo:\n{e}")
            return
        self.ruta, self.modificado = ruta, False
        self.texto.edit_reset()
        self.texto.mark_set("insert", "1.0")
        self.actualizar_titulo()
        self.actualizar_estado(f"Abierto en {ms} ms")

    def guardar(self):
        if not self.ruta:
            return self.guardar_como()
        try:
            core.guardar(self.ruta, self.fmt.a_modelo())
        except Exception as e:  # noqa: BLE001
            messagebox.showerror(NOMBRE_APP, f"No se pudo guardar:\n{e}")
            return False
        self.modificado = False
        self.actualizar_titulo()
        self.actualizar_estado("Documento guardado")
        return True

    def guardar_como(self):
        ruta = filedialog.asksaveasfilename(defaultextension=".docx", filetypes=core.FORMATOS,
                                            initialfile=Path(self.ruta).stem if self.ruta else "Documento")
        if not ruta:
            return False
        if Path(ruta).suffix.lower() == ".txt" and not messagebox.askokcancel(
                NOMBRE_APP, "El formato .txt guarda solo el texto: se perderán negrita, fuentes y alineación.\n¿Continuar?"):
            return False
        self.ruta = ruta
        return self.guardar()

    def salir(self):
        if self._confirmar_descartar():
            self.raiz.destroy()

    # ============================================================== edición
    def pegar(self):
        try:
            contenido = self.raiz.clipboard_get()
        except tk.TclError:
            return
        self._borrar_seleccion()
        self.fmt.insertar("insert", contenido, self.estilo)
        self.texto.see("insert")

    def seleccionar_todo(self):
        self.texto.tag_add("sel", "1.0", "end-1c")
        self.texto.mark_set("insert", "end-1c")

    def insertar_fecha(self):
        self._borrar_seleccion()
        self.fmt.insertar("insert", datetime.now().strftime("%d/%m/%Y %H:%M"), self.estilo)

    def buscar(self, reemplazar: bool):
        v = tk.Toplevel(self.raiz)
        v.title("Reemplazar" if reemplazar else "Buscar")
        v.transient(self.raiz)
        v.resizable(False, False)
        ttk.Label(v, text="Buscar:").grid(row=0, column=0, sticky="w", padx=8, pady=6)
        e_buscar = ttk.Entry(v, width=30)
        e_buscar.grid(row=0, column=1, padx=8)
        if self.texto.tag_ranges("sel"):
            e_buscar.insert(0, self.texto.get("sel.first", "sel.last"))
        e_buscar.focus_set()
        e_reemp = None
        if reemplazar:
            ttk.Label(v, text="Reemplazar con:").grid(row=1, column=0, sticky="w", padx=8)
            e_reemp = ttk.Entry(v, width=30)
            e_reemp.grid(row=1, column=1, padx=8)
        var_mayus = tk.BooleanVar()
        ttk.Checkbutton(v, text="Coincidir mayúsculas y minúsculas", variable=var_mayus).grid(row=2, column=1, sticky="w", padx=8)

        def siguiente():
            patron = e_buscar.get()
            if not patron:
                return None
            self.texto.tag_remove("encontrado", "1.0", "end")
            pos = self.texto.search(patron, "insert+1c" if self.texto.tag_ranges("sel") else "insert",
                                    stopindex="end", nocase=not var_mayus.get())
            if not pos:
                pos = self.texto.search(patron, "1.0", stopindex="end", nocase=not var_mayus.get())
            if not pos:
                messagebox.showinfo(NOMBRE_APP, f"No se encontró «{patron}».", parent=v)
                return None
            fin = f"{pos}+{len(patron)}c"
            self.texto.tag_remove("sel", "1.0", "end")
            self.texto.tag_add("sel", pos, fin)
            self.texto.tag_add("encontrado", pos, fin)
            self.texto.mark_set("insert", pos)
            self.texto.see(pos)
            return pos

        def reemplazar_uno():
            if not self.texto.tag_ranges("sel"):
                siguiente()
                return
            e = self.fmt.estilo_en("sel.first")
            ini = self.texto.index("sel.first")
            self.texto.delete("sel.first", "sel.last")
            self.fmt.insertar(ini, e_reemp.get(), e)
            siguiente()

        def reemplazar_todo():
            patron, nuevo = e_buscar.get(), e_reemp.get()
            if not patron:
                return
            n, pos = 0, "1.0"
            while True:
                pos = self.texto.search(patron, pos, stopindex="end", nocase=not var_mayus.get())
                if not pos:
                    break
                e = self.fmt.estilo_en(pos)
                self.texto.delete(pos, f"{pos}+{len(patron)}c")
                self.fmt.insertar(pos, nuevo, e)
                pos = f"{pos}+{len(nuevo)}c"
                n += 1
            messagebox.showinfo(NOMBRE_APP, f"Se reemplazaron {n} coincidencias.", parent=v)

        fila = ttk.Frame(v)
        fila.grid(row=3, column=0, columnspan=2, pady=8)
        ttk.Button(fila, text="Buscar siguiente", command=siguiente).pack(side="left", padx=3)
        if reemplazar:
            ttk.Button(fila, text="Reemplazar", command=reemplazar_uno).pack(side="left", padx=3)
            ttk.Button(fila, text="Reemplazar todo", command=reemplazar_todo).pack(side="left", padx=3)
        ttk.Button(fila, text="Cerrar", command=v.destroy).pack(side="left", padx=3)
        v.bind("<Return>", lambda e: siguiente())
        v.bind("<Escape>", lambda e: v.destroy())

    # ============================================================== formato
    def _rango(self):
        if self.texto.tag_ranges("sel"):
            return self.texto.index("sel.first"), self.texto.index("sel.last")
        return None

    def cambiar(self, atributo, valor):
        self.estilo = self.estilo.con(**{atributo: valor})
        r = self._rango()
        if r:
            self.fmt.cambiar_estilo(*r, lambda e: e.con(**{atributo: valor}))
            self.modificado = True
            self.actualizar_titulo()
        self.actualizar_botones()
        self.texto.focus_set()

    def _tamano_desde_combo(self):
        try:
            tam = max(1, min(400, int(float(self.var_tamano.get()))))
        except ValueError:
            return
        self.cambiar("tamano", tam)

    def alternar(self, atributo):
        r = self._rango()
        base = self.fmt.estilo_en(r[0]) if r else self.estilo
        self.cambiar(atributo, not getattr(base, atributo))

    def elegir_color(self):
        _, hexa = colorchooser.askcolor(color=self.estilo.color, title="Color de texto")
        if hexa:
            self.cambiar("color", hexa.lower())

    def alinear(self, alineacion):
        r = self._rango() or (self.texto.index("insert"), self.texto.index("insert"))
        self.fmt.alinear(r[0], r[1], alineacion)
        self.modificado = True
        self.actualizar_titulo()
        self.actualizar_botones()

    def cambiar_zoom(self, delta):
        self.zoom = 1.0 if delta is None else max(0.5, min(3.0, round(self.zoom + delta, 1)))
        self.fmt.aplicar_zoom(self.zoom)
        self._dibujar_regla()
        self.actualizar_estado()

    # ============================================================ estado UI
    def actualizar_botones(self):
        self.var_fuente.set(self.estilo.fuente)
        self.var_tamano.set(str(self.estilo.tamano))
        for clave, bt in self.btn_fmt.items():
            bt.configure(style="Activo.TButton" if getattr(self.estilo, clave) else "Herr.TButton")
        al = self.fmt.alineacion_en("insert")
        for a, bt in self.btn_al.items():
            bt.configure(style="Activo.TButton" if a == al else "Herr.TButton")

    def actualizar_estado(self, mensaje=""):
        if not self.texto.tag_ranges("sel"):
            antes = self.texto.index("insert-1c")
            if self.texto.compare("insert", ">", "1.0") and self.texto.get(antes) != "\n":
                self.estilo = self.fmt.estilo_en(antes)
        self.actualizar_botones()
        est = core.estadisticas(self.texto.get("1.0", "end-1c"))
        lin, col = self.texto.index("insert").split(".")
        extra = f"   ·   {mensaje}" if mensaje else ""
        self.var_estado.set(f"Línea {lin}, col. {int(col) + 1}   ·   {est['palabras']} palabras   ·   "
                            f"{est['caracteres']} caracteres   ·   Zoom {round(self.zoom * 100)} %{extra}")

    # =================================================================== IA
    def _motor_texto(self):
        return f"Gemini ({self.ia.modelo})" if self.ia.tiene_clave else "sin API Key (IA > Configurar API Key)"

    def _estado_ia_inicial(self):
        return "IA: lista" if self.ia.tiene_clave else "IA: sin API Key"

    def alternar_panel(self):
        if self.panel_visible:
            self.panel.forget(self.panel_ia)
        else:
            self.panel.add(self.panel_ia, weight=1)
        self.panel_visible = not self.panel_visible

    def usar_ia(self, tarea):
        if self.ia_ocupada:
            return
        if not self.panel_visible:
            self.alternar_panel()
        r = self._rango()
        texto = self.texto.get(*r) if r else self.texto.get("1.0", "end-1c")
        self.ultima_seleccion = r
        self.ia_ocupada = True
        self.barra_progreso.start(12)
        nombres = {"resumir": "Resumiendo", "corregir": "Corrigiendo", "continuar": "Autocompletando"}
        self.var_ia.set(f"✨ {nombres[tarea]}…")
        self.salida_ia.delete("1.0", "end")
        self.salida_ia.insert("1.0", f"{nombres[tarea]}… (puedes seguir escribiendo)")
        self.tarea_actual = tarea
        # La consulta corre en un hilo secundario; el hilo solo deja el resultado en una cola.
        # La interfaz revisa la cola cada 50 ms con root.after(): Tkinter nunca se toca desde otro hilo
        # y la ventana sigue respondiendo mientras la IA piensa.
        self.cola_ia = queue.Queue()
        self.ia.ejecutar(tarea, texto, self.cola_ia.put)
        self.raiz.after(50, self._revisar_ia)

    def _revisar_ia(self):
        try:
            res = self.cola_ia.get_nowait()
        except queue.Empty:
            self.raiz.after(50, self._revisar_ia)
            return
        self._resultado_ia(res)

    def _resultado_ia(self, res):
        """Se ejecuta en el hilo de la interfaz cuando la IA termina."""
        self.ia_ocupada = False
        self.barra_progreso.stop()
        self.salida_ia.delete("1.0", "end")
        if not res["ok"]:
            self.salida_ia.insert("1.0", "⚠ " + res["error"])
            self.var_ia.set("IA: error")
            self.lbl_ia.configure(text="Motor: " + self._motor_texto())
            messagebox.showwarning(NOMBRE_APP, res["error"])
            return
        self.ultimo_resultado = res["texto"]
        self.salida_ia.insert("1.0", res["texto"])
        self.lbl_ia.configure(text=f"Motor: Gemini ({res['modelo']})   ·   {res['segundos']:.2f} s")
        self.var_ia.set(f"IA: {NOMBRES[res['tarea']]} en {res['segundos']:.2f} s")

    def insertar_resultado(self):
        if not self.ultimo_resultado:
            return
        pos = self.ultima_seleccion[1] if self.ultima_seleccion else "insert"
        if getattr(self, "tarea_actual", "") == "continuar":
            pos = self.ultima_seleccion[1] if self.ultima_seleccion else "end-1c"
            texto = " " + self.ultimo_resultado
        else:
            texto = "\n" + self.ultimo_resultado
        self.fmt.insertar(pos, texto, self.estilo)

    def reemplazar_con_resultado(self):
        if not self.ultimo_resultado:
            return
        r = self.ultima_seleccion or ("1.0", "end-1c")
        e = self.fmt.estilo_en(r[0])
        self.texto.delete(*r)
        self.fmt.insertar(r[0], self.ultimo_resultado, e)
        self.ultima_seleccion = None

    def configurar_ia(self):
        v = tk.Toplevel(self.raiz)
        v.title("Configurar API Key de Gemini")
        v.transient(self.raiz)
        v.resizable(False, False)
        ttk.Label(v, text="Clave de API de Google AI Studio (aistudio.google.com):").grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=(10, 2))
        e_clave = ttk.Entry(v, width=48, show="•")
        e_clave.insert(0, self.ia.clave)
        e_clave.grid(row=1, column=0, columnspan=2, padx=10)
        ttk.Label(v, text="Modelo:").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        e_modelo = ttk.Combobox(v, width=30, values=MODELOS)
        e_modelo.set(self.ia.modelo)
        e_modelo.grid(row=2, column=1, sticky="w", padx=10)
        ttk.Label(v, text="Se guarda en el archivo .env de tu PC (no se sube a GitHub).", foreground="#666").grid(row=3, column=0, columnspan=2, padx=10, sticky="w")

        def guardar():
            if not e_clave.get().strip():
                messagebox.showwarning(NOMBRE_APP, "Pega una API Key válida.", parent=v)
                return
            try:
                self.ia.configurar(e_clave.get(), e_modelo.get())
            except OSError as e:
                messagebox.showerror(NOMBRE_APP, f"No se pudo guardar el archivo .env:\n{e}", parent=v)
                return
            self.lbl_ia.configure(text="Motor: " + self._motor_texto())
            self.var_ia.set(self._estado_ia_inicial())
            v.destroy()
            messagebox.showinfo(NOMBRE_APP, "API Key guardada correctamente.")
        ttk.Button(v, text="Guardar", command=guardar).grid(row=4, column=1, sticky="e", padx=10, pady=10)

    def acerca(self):
        messagebox.showinfo(NOMBRE_APP, "Procesador de Texto IA\nRéplica funcional inspirada en WordPad, reconstruida por "
                                        "ingeniería inversa, con asistente de IA (Gemini).\n\nUNAMAD · Inteligencia Artificial · 2026")
