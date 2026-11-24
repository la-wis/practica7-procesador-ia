"""
main.py — Punto de entrada del Procesador de Texto IA.

Uso:
    python main.py                 abre un documento nuevo
    python main.py archivo.docx    abre un archivo (.docx o .txt)
"""

import sys
import tkinter as tk

from ui import ProcesadorIA


def main():
    raiz = tk.Tk()
    app = ProcesadorIA(raiz)
    if len(sys.argv) > 1:
        app.abrir(sys.argv[1])
    raiz.mainloop()


if __name__ == "__main__":
    main()
