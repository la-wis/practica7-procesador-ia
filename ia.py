"""
ia.py — Módulo de Inteligencia Artificial (Opción A de la guía).

Capacidades:
  1. corregir  -> corrector de estilo semántico (ortografía, gramática, claridad)
  2. resumir   -> resumen automático del texto seleccionado o del documento
  3. continuar -> autocompletado contextual (continúa el párrafo)

Motor: API de Google Gemini mediante el SDK oficial `google-genai`.
Cada consulta se ejecuta en un HILO secundario (threading) y el resultado vuelve
a la interfaz por un callback, que ui.py programa con root.after(0, ...),
así la ventana nunca se congela.

La clave se lee de la variable GEMINI_API_KEY del archivo .env (junto a este
archivo) y puede cambiarse desde el menú IA > Configurar API Key.
"""

import os
import threading
import time
from pathlib import Path

from dotenv import load_dotenv

RUTA_ENV = Path(__file__).resolve().parent / ".env"
load_dotenv(RUTA_ENV)

MODELO_POR_DEFECTO = "gemini-3.1-flash-lite"
MODELOS = ["gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-3.1-flash-lite"]
LIMITE_CARACTERES = 20000

INSTRUCCIONES = {
    "corregir": ("Eres un corrector de estilo profesional en español. Corrige ortografía, tildes, gramática y "
                 "puntuación, y mejora la claridad y fluidez sin cambiar el significado ni el registro. "
                 "Devuelve SOLO el texto corregido, sin comentarios ni comillas."),
    "resumir": ("Eres un asistente de redacción académica. Resume el texto en español en 2 a 4 oraciones "
                "claras, conservando las ideas principales y sin inventar datos. Devuelve solo el resumen."),
    "continuar": ("Eres un autocompletado contextual. Continúa el texto del usuario con 1 o 2 oraciones "
                  "coherentes con su tema, tono e idioma. Devuelve SOLO la continuación, sin repetir el texto."),
}

NOMBRES = {"corregir": "Corrector de estilo", "resumir": "Resumen automático", "continuar": "Autocompletado"}


class ErrorIA(Exception):
    """Error con un mensaje amigable para mostrar al usuario."""


class AsistenteIA:
    def __init__(self):
        self.clave = os.getenv("GEMINI_API_KEY", "").strip()
        self.modelo = os.getenv("GEMINI_MODEL", "").strip() or MODELO_POR_DEFECTO
        self._cliente = None

    # ---------------------------------------------------------- configuración
    @property
    def tiene_clave(self) -> bool:
        return bool(self.clave) and not self.clave.startswith("pega_aqui")

    def configurar(self, clave: str, modelo: str = ""):
        """Guarda la clave (y el modelo) en el archivo .env sin tocar las demás líneas."""
        self.clave = clave.strip()
        self.modelo = modelo.strip() or MODELO_POR_DEFECTO
        self._cliente = None
        lineas = RUTA_ENV.read_text(encoding="utf-8").splitlines() if RUTA_ENV.exists() else []
        valores = {"GEMINI_API_KEY": self.clave, "GEMINI_MODEL": self.modelo}
        nuevas, vistos = [], set()
        for linea in lineas:
            nombre = linea.split("=", 1)[0].strip()
            if nombre in valores:
                nuevas.append(f"{nombre}={valores[nombre]}")
                vistos.add(nombre)
            else:
                nuevas.append(linea)
        nuevas += [f"{k}={v}" for k, v in valores.items() if k not in vistos]
        RUTA_ENV.write_text("\n".join(nuevas) + "\n", encoding="utf-8")
        os.environ.update(valores)

    def _obtener_cliente(self):
        if self._cliente is None:
            from google import genai          # import diferido: la app abre aunque falte la librería
            self._cliente = genai.Client(api_key=self.clave)
        return self._cliente

    # ---------------------------------------------------- ejecución asíncrona
    def ejecutar(self, tarea: str, texto: str, al_terminar):
        """Lanza la tarea en un hilo secundario y llama a al_terminar(resultado) al acabar."""
        hilo = threading.Thread(target=lambda: al_terminar(self.procesar(tarea, texto)), daemon=True)
        hilo.start()
        return hilo

    def procesar(self, tarea: str, texto: str) -> dict:
        """Ejecuta la tarea (bloqueante). Siempre devuelve un dict, nunca lanza excepciones."""
        inicio = time.perf_counter()
        try:
            salida = self._consultar(tarea, texto)
            return {"ok": True, "tarea": tarea, "texto": salida, "modelo": self.modelo,
                    "segundos": round(time.perf_counter() - inicio, 2)}
        except ErrorIA as e:
            return {"ok": False, "tarea": tarea, "error": str(e),
                    "segundos": round(time.perf_counter() - inicio, 2)}
        except Exception as e:  # noqa: BLE001 — cualquier fallo imprevisto se informa sin cerrar la app
            return {"ok": False, "tarea": tarea, "error": _mensaje_error(e),
                    "segundos": round(time.perf_counter() - inicio, 2)}

    def _consultar(self, tarea: str, texto: str) -> str:
        if tarea not in INSTRUCCIONES:
            raise ErrorIA(f"Tarea desconocida: {tarea}")
        texto = (texto or "").strip()
        if not texto:
            raise ErrorIA("El documento está vacío. Escribe o selecciona algún texto primero.")
        if not self.tiene_clave:
            raise ErrorIA("Falta la API Key de Gemini.\n\nVe al menú IA > Configurar API Key y pega tu clave "
                          "de Google AI Studio (https://aistudio.google.com/apikey).")
        try:
            from google.genai import types
        except ImportError:
            raise ErrorIA("Falta la librería google-genai. Ejecuta:  pip install -r requirements.txt")

        config = types.GenerateContentConfig(
            system_instruction=INSTRUCCIONES[tarea],
            temperature=0.3 if tarea == "corregir" else 0.7,
            max_output_tokens=2048,
            http_options=types.HttpOptions(timeout=60_000),   # milisegundos
        )
        respuesta = self._obtener_cliente().models.generate_content(
            model=self.modelo, contents=texto[:LIMITE_CARACTERES], config=config)
        salida = (respuesta.text or "").strip()
        if not salida:
            raise ErrorIA("La IA no devolvió texto (respuesta vacía o bloqueada por el filtro de seguridad).")
        return salida


def _mensaje_error(e: Exception) -> str:
    """Traduce las excepciones de red y de la API a mensajes claros en español."""
    try:
        from google.genai import errors
        if isinstance(e, errors.APIError):
            codigo = getattr(e, "code", None)
            detalle = getattr(e, "message", "") or str(e)
            if codigo in (400, 401, 403) and "key" in detalle.lower():
                return "La API Key no es válida. Revísala en IA > Configurar API Key."
            if codigo == 404:
                return "El modelo configurado no existe o no está disponible. Prueba con otro en IA > Configurar API Key."
            if codigo == 429:
                return "Se agotó la cuota gratuita de Gemini por ahora. Espera un minuto e inténtalo de nuevo."
            if codigo and codigo >= 500:
                return "El servidor de Gemini tiene problemas en este momento. Inténtalo más tarde."
            return f"Error de la API de Gemini ({codigo}): {detalle[:200]}"
    except ImportError:
        pass
    nombre = type(e).__name__.lower()
    texto = str(e).lower()
    if any(p in nombre + texto for p in ("connect", "timeout", "network", "getaddrinfo", "resolve", "unreachable")):
        return "No hay conexión a internet o el servidor no respondió a tiempo. Revisa tu conexión."
    return f"Error inesperado: {type(e).__name__}: {str(e)[:200]}"
