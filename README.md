# Procesador de Texto IA — Práctica 7: Ingeniería Inversa Funcional (Opción A)

Réplica funcional inspirada en **WordPad / OpenOffice Writer**, reconstruida por ingeniería inversa de caja negra
y caja gris, con un **módulo de IA (Gemini)**: corrector de estilo semántico, resumen automático y autocompletado contextual.

UNAMAD · Inteligencia Artificial · Estudiante: Deydids Chaparrea Gonzales

## Instalación y ejecución (PowerShell, Windows 11, Python 3.11)

```powershell
cd "C:\Users\DD\Desktop\n6\ss23 Inge-Inversa\procesador_ia"
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python main.py
```

> Si PowerShell bloquea la activación del entorno, ejecuta una vez:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

La API Key se puede pegar desde la app: **IA > Configurar API Key** (se guarda en `.env`, que no se sube a GitHub).
Clave gratuita: https://aistudio.google.com/apikey

## Estructura
| Archivo | Rol |
|---|---|
| `main.py` | Punto de entrada |
| `ui.py` | Interfaz Tkinter/ttk: menús, barra de herramientas, regla, hoja, barra de estado y panel IA |
| `core.py` | Lógica: formato por carácter/párrafo, abrir/guardar `.docx` y `.txt`, buscar/reemplazar, estadísticas |
| `ia.py` | Gemini (`google-genai`) en hilo secundario, manejo de errores y medición de latencia |

## Funciones
| # | Función | Atajo |
|---|---|---|
| 1 | Nuevo (avisa si hay cambios sin guardar) | Ctrl+N |
| 2 | Abrir `.docx` / `.txt` | Ctrl+O |
| 3 | Guardar / Guardar como `.docx` / `.txt` | Ctrl+S / Ctrl+Shift+S |
| 4 | Negrita, cursiva, subrayado | Ctrl+B / Ctrl+I / Ctrl+U |
| 5 | Fuente, tamaño y color | barra de herramientas |
| 6 | Alinear izquierda, centro, derecha, justificar | Ctrl+L / Ctrl+Shift+C / Ctrl+R / Ctrl+J |
| 7 | Buscar / Reemplazar | Ctrl+F / Ctrl+H |
| 8 | Deshacer / Rehacer | Ctrl+Z / Ctrl+Y |
| 9 | Barra de estado: palabras, caracteres, estado y latencia de la IA | tiempo real |
| IA | Corrector de estilo · Resumen · Autocompletado | Ctrl+Shift+E · Ctrl+Shift+R · Ctrl+Espacio |

## Ética
No se descompiló ningún binario ni se usan íconos o recursos de Microsoft: la réplica se basa solo en la
observación del comportamiento y en el estándar abierto Office Open XML (.docx).
