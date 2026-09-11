#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=============================================================================
  EL BOSQUE DE LAS PALABRAS MAGICAS
  Juego educativo de conciencia fonologica e iniciacion a la lectoescritura
  Grado: 1o de primaria  |  Metodo: silabico-fonetico
  Autor: Anderson Mamian Chicangana
=============================================================================

REQUISITOS DE EJECUCION (ESCRITORIO)
------------------------------------
    pip install pygame
    (opcional, para voz en off)   pip install pyttsx3

    python main.py

Los efectos de sonido se sintetizan con la biblioteca estandar, asi que
suenan siempre, sin archivos de audio y sin numpy.

LA VOZ DE LINA
--------------
Lina la Lechuza lee los dialogos en voz alta y mueve el pico mientras habla.
Busca un motor de voz en este orden:

  1. pyttsx3, si esta instalado (pip install pyttsx3)
  2. la voz del sistema, sin instalar nada:
       Windows -> SAPI / System.Speech (elige una voz en espanol)
       macOS   -> say (Paulina o Monica)
       Linux   -> spd-say o espeak-ng en espanol
  3. en el navegador -> la voz en espanol del dispositivo
  4. si no hay ninguna -> su propia voz de lechuza, una nota por silaba

Si en Windows no se oye en espanol sino con acento ingles, falta la voz:
Configuracion > Hora e idioma > Voz > Agregar voces > Espanol.
Los subtitulos aparecen siempre, haya voz o no.

PUBLICAR EN INTERNET (PC Y ANDROID, POR ENLACE)
-----------------------------------------------
    pip install pygbag
    pygbag --build bosque/          (la carpeta que contiene este main.py)

Eso genera bosque/build/web/. Sube esa carpeta a itch.io, GitHub Pages o
Netlify y comparte el enlace: se abre en el navegador del PC y del celular
Android, sin instalar nada. Ver README_WEB.md para el paso a paso.

CONTROLES
---------
    Raton / pantalla tactil : toda la interaccion
    1..5                    : seleccionar opcion en el nivel 1
    ESPACIO                 : repetir instruccion (Lina la Lechuza)
    M                       : encender / apagar el sonido
    ESC                     : volver / pausar
    F11                     : pantalla completa (solo escritorio)
=============================================================================
"""

import array
import asyncio
import json
import math
import os
import queue
import random
import sys
import threading

import pygame

# --------------------------------------------------------------------------
#  ENTORNO: ESCRITORIO O NAVEGADOR (PC / ANDROID vía pygbag)
# --------------------------------------------------------------------------
ES_WEB = sys.platform == "emscripten"

_window = None
if ES_WEB:
    try:
        import platform as _plat          # pygbag expone platform.window
        _window = _plat.window
    except Exception:
        _window = None

# --------------------------------------------------------------------------
# DEPENDENCIAS OPCIONALES
# --------------------------------------------------------------------------
try:
    import numpy as _np
    TIENE_NUMPY = True
except ImportError:
    TIENE_NUMPY = False

try:
    if ES_WEB:
        raise ImportError            # en el navegador se usa la voz del sistema
    import pyttsx3 as _tts  # type: ignore[import-not-found]
    TIENE_TTS = True
except Exception:
    TIENE_TTS = False


# ==========================================================================
#  CONFIGURACION GLOBAL
# ==========================================================================
ANCHO, ALTO = 1280, 720
FPS = 60
TITULO = "El Bosque de las Palabras Magicas"
ARCHIVO_PROGRESO = os.path.join(
    os.path.expanduser("~"), ".bosque_palabras_progreso.json"
)
CLAVE_PROGRESO = "bosque_palabras_progreso"      # navegador (localStorage)

# Paleta -------------------------------------------------------------------
C_CIELO_ALTO = (126, 206, 244)
C_CIELO_BAJO = (200, 240, 232)
C_MONTE = (122, 168, 140)
C_BOSQUE_LEJOS = (108, 164, 128)
C_BOSQUE_MEDIO = (72, 138, 96)
C_BOSQUE_CERCA = (44, 106, 72)
C_SUELO = (126, 184, 104)
C_SUELO_OSCURO = (92, 150, 80)
C_TRONCO = (120, 82, 56)
C_TRONCO_OSCURO = (92, 62, 42)
C_AGUA = (92, 176, 214)
C_AGUA_CLARA = (152, 214, 236)
C_MADERA = (176, 126, 78)
C_MADERA_OSC = (138, 96, 58)
C_PIEDRA = (214, 210, 198)
C_PIEDRA_BORDE = (166, 160, 146)
C_BLANCO = (255, 255, 255)
C_CREMA = (255, 250, 235)
C_TEXTO = (48, 42, 38)
C_TEXTO_SUAVE = (96, 88, 82)
C_DORADO = (255, 198, 60)
C_DORADO_OSC = (226, 154, 30)
C_ROSA = (255, 138, 160)
C_MORADO = (150, 116, 200)
C_NARANJA = (255, 154, 74)
C_VERDE_OK = (96, 196, 122)
C_SOMBRA = (0, 0, 0, 60)

VOCALES = ["A", "E", "I", "O", "U"]


# ==========================================================================
#  UTILIDADES DE ANIMACION
# ==========================================================================
def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo, hi):
    return lo if v < lo else (hi if v > hi else v)


def ease_out_cubic(t):
    return 1 - (1 - t) ** 3


def ease_in_out(t):
    return 3 * t * t - 2 * t * t * t


def ease_out_back(t):
    c1, c3 = 1.70158, 2.70158
    return 1 + c3 * (t - 1) ** 3 + c1 * (t - 1) ** 2


def ease_out_elastic(t):
    if t <= 0:
        return 0.0
    if t >= 1:
        return 1.0
    p = 2 * math.pi / 3
    return 2 ** (-10 * t) * math.sin((t * 10 - 0.75) * p) + 1


def mezclar(c1, c2, t):
    return (
        int(lerp(c1[0], c2[0], t)),
        int(lerp(c1[1], c2[1], t)),
        int(lerp(c1[2], c2[2], t)),
    )


class Tween:
    """Animacion sencilla de un valor entre dos extremos."""

    def __init__(self, ini, fin, dur, easing=ease_out_cubic, retardo=0.0):
        self.ini, self.fin, self.dur = ini, fin, max(dur, 1e-6)
        self.easing, self.retardo = easing, retardo
        self.t = 0.0

    def update(self, dt):
        self.t += dt

    @property
    def valor(self):
        p = clamp((self.t - self.retardo) / self.dur, 0, 1)
        return lerp(self.ini, self.fin, self.easing(p))

    @property
    def terminado(self):
        return self.t >= self.retardo + self.dur


# ==========================================================================
#  AUDIO: VOZ EN OFF Y EFECTOS
# ==========================================================================
# --------------------------------------------------------------------------
#  VOZ DEL SISTEMA (sin instalar nada): SAPI en Windows, say en macOS,
#  espeak o spd-say en Linux. Se usa cuando no hay pyttsx3.
# --------------------------------------------------------------------------
PISTAS_VOZ_ES = ("spanish", "espanol", "español", "castilian", "es-", "es_",
                 "sabina", "helena", "laura", "pablo", "raul", "jorge",
                 "diego", "monica", "paulina", "mexico", "colombia")

_GUION_VOZ_WIN = """
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() |
     Where-Object { $_.VoiceInfo.Culture.Name -like 'es*' } |
     Select-Object -First 1
if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
$s.Rate = 0
while ($true) {
    $linea = [Console]::In.ReadLine()
    if ($linea -eq $null) { break }
    if ($linea.Length -eq 0) { continue }
    $txt = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($linea))
    $s.SpeakAsyncCancelAll()
    $s.SpeakAsync($txt) | Out-Null
}
"""


def _motor_windows():
    """Voz de Windows (SAPI) a traves de un PowerShell que queda abierto, para
    que cada frase salga al instante y no haya que arrancarlo cada vez.

    No se espera a que termine de cargarse: las frases quedan en la tuberia y
    se pronuncian en cuanto el motor esta listo, asi el juego abre sin pausas.
    """
    import base64
    import subprocess
    import tempfile
    import time
    try:
        ruta = os.path.join(tempfile.gettempdir(), "bosque_voz.ps1")
        with open(ruta, "w", encoding="utf-8-sig") as f:
            f.write(_GUION_VOZ_WIN)
        proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", ruta],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=0x08000000)          # sin ventana negra
        time.sleep(0.15)
        if proc.poll() is not None:            # murio de inmediato
            return None
    except Exception:
        return None

    def hablar(texto):
        try:
            dato = base64.b64encode(texto.encode("utf-8")).decode("ascii")
            proc.stdin.write((dato + "\n").encode("ascii"))
            proc.stdin.flush()
            return proc.poll() is None
        except Exception:
            return False

    return hablar


def _motor_consola(ordenes):
    """Motores de linea de comandos (macOS y Linux)."""
    import shutil
    import subprocess
    for orden in ordenes:
        if not shutil.which(orden[0]):
            continue

        def hablar(texto, base=orden):
            try:
                subprocess.Popen(base + [texto],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return True
            except Exception:
                return False

        return hablar
    return None


def _motor_sistema():
    if ES_WEB:
        return None
    try:
        if sys.platform.startswith("win"):
            return _motor_windows()
        if sys.platform == "darwin":
            return _motor_consola([["say", "-v", "Paulina"],
                                   ["say", "-v", "Monica"], ["say"]])
        return _motor_consola([["spd-say", "-l", "es", "-t", "female1"],
                               ["espeak-ng", "-v", "es-la", "-s", "150"],
                               ["espeak", "-v", "es", "-s", "150"]])
    except Exception:
        return None


class Voz:
    """Sintesis de voz en hilo aparte. Si no hay motor, solo subtitulos."""

    def __init__(self):
        self.cola = queue.Queue()
        self.subtitulo = ""
        self.subtitulo_t = 0.0
        self.web = ES_WEB and _window is not None
        # motor disponible: pyttsx3, la voz del sistema, o ninguno
        self.motor_sistema = None if (self.web or TIENE_TTS) else _motor_sistema()
        self.activa = TIENE_TTS or self.motor_sistema is not None
        self.fx = None              # lo asigna Juego al arrancar
        self.hablando = 0.0         # segundos que le quedan de habla
        self.boca = 0.0             # apertura del pico, 0 a 1
        self._notas = []            # balbuceo pendiente
        self._reloj = 0.0
        self._voces_web = False
        self._proceso = None
        if self.activa:
            self.hilo = threading.Thread(target=self._bucle, daemon=True)
            self.hilo.start()

    def _hay_voz_web(self):
        """El navegador carga las voces de forma diferida: se consulta cada vez
        hasta que aparezcan."""
        if self._voces_web:
            return True
        try:
            self._voces_web = bool(_window.eval(
                "(window.speechSynthesis && speechSynthesis.getVoices().length)"
                " || 0"))
        except Exception:
            self._voces_web = False
        return self._voces_web

    def _plan_balbuceo(self, texto, duracion):
        """Voz propia de Lina: una nota corta por cada silaba, con entonacion
        que sube al empezar la frase y baja al terminarla."""
        golpes = min(max(len([c for c in texto.upper() if c in "AEIOU"]), 1), 30)
        paso = max(duracion / (golpes + 1), 0.07)
        self._notas = []
        for i in range(golpes):
            p = i / max(golpes - 1, 1)
            tono = 1.0 + 0.16 * math.sin(p * math.pi) - 0.20 * p
            if texto.rstrip().endswith("?"):
                tono += 0.30 * p          # las preguntas terminan subiendo
            self._notas.append((0.05 + i * paso, tono))
        self._reloj = 0.0

    def _decir_web(self, texto):
        """Voz del navegador (funciona en PC y en Android)."""
        try:
            js = (
                "(function(t){try{"
                "var S=window.speechSynthesis;S.cancel();"
                "var u=new SpeechSynthesisUtterance(t);"
                "var vs=S.getVoices()||[];"
                "var v=vs.find(function(x){return x.lang&&"
                "x.lang.toLowerCase().indexOf('es')===0;});"
                "if(v){u.voice=v;u.lang=v.lang;}else{u.lang='es-ES';}"
                "u.rate=0.92;u.pitch=1.05;"
                "S.speak(u);"
                "}catch(e){}})(" + json.dumps(texto, ensure_ascii=False) + ")"
            )
            _window.eval(js)
        except Exception:
            pass

    def _iniciar_pyttsx3(self):
        """Motor pyttsx3 con voz en espanol si el equipo tiene alguna."""
        try:
            motor = _tts.init()
            motor.setProperty("rate", 150)
            mejor = None
            for v in motor.getProperty("voices"):
                etiqueta = (str(getattr(v, "name", "")) + " " +
                            str(getattr(v, "id", "")) + " " +
                            " ".join(getattr(v, "languages", []) or [])).lower()
                if any(p in etiqueta for p in PISTAS_VOZ_ES):
                    mejor = v.id
                    break
            if mejor:
                motor.setProperty("voice", mejor)
            return motor
        except Exception:
            return None

    def _bucle(self):
        """Hilo de voz: pronuncia las frases sin congelar el juego."""
        motor = self._iniciar_pyttsx3() if TIENE_TTS else None
        if motor is None and self.motor_sistema is None:
            self.activa = False
            return
        while True:
            texto = self.cola.get()
            if texto is None:
                break
            hablado = False
            if motor is not None:
                try:
                    motor.say(texto)
                    motor.runAndWait()
                    hablado = True
                except Exception:
                    motor = None
            if not hablado and self.motor_sistema is not None:
                hablado = self.motor_sistema(texto)
            if not hablado:
                # el motor fallo a mitad de camino: Lina sigue con su voz
                self.activa = False
                self.motor_sistema = None
                break

    def decir(self, texto, duracion=None):
        self.subtitulo = texto
        self.subtitulo_t = duracion or clamp(len(texto) * 0.07, 1.8, 6.0)
        self.hablando = self.subtitulo_t
        self._notas = []
        self._reloj = 0.0
        if self.web and self._hay_voz_web():
            self._decir_web(texto)
            return
        if self.activa:
            while not self.cola.empty():
                try:
                    self.cola.get_nowait()
                except queue.Empty:
                    break
            self.cola.put(texto)
            return
        # sin sintetizador: Lina habla con su propia voz de lechuza
        self._plan_balbuceo(texto, self.subtitulo_t)

    def update(self, dt):
        if self.subtitulo_t > 0:
            self.subtitulo_t -= dt
            if self.subtitulo_t <= 0:
                self.subtitulo = ""
        if self.hablando > 0:
            self.hablando -= dt
            self._reloj += dt
            self.boca = 0.5 + 0.5 * math.sin(self._reloj * 15.0)
            while self._notas and self._notas[0][0] <= self._reloj:
                _cuando, tono = self._notas.pop(0)
                if self.fx is not None:
                    self.fx.nota_voz(tono)
        else:
            self.boca = max(self.boca - dt * 6.0, 0.0)
            self._notas = []


# Formantes aproximados del espanol: (frecuencia, ancho de banda, ganancia)
FORMANTES = {
    "A": [(760, 110, 1.00), (1300, 130, 0.55), (2600, 190, 0.18)],
    "E": [(500, 90, 1.00), (1900, 130, 0.50), (2650, 190, 0.18)],
    "I": [(300, 80, 1.00), (2250, 140, 0.42), (3000, 210, 0.16)],
    "O": [(500, 90, 1.00), (900, 110, 0.55), (2600, 190, 0.12)],
    "U": [(330, 80, 1.00), (760, 100, 0.42), (2500, 190, 0.10)],
}


class Efectos:
    """Banco de sonidos sintetizados en tiempo de ejecucion.

    No necesita archivos de audio ni numpy: las muestras se generan con el
    modulo array de la biblioteca estandar, asi que suena igual en Windows,
    en Linux y dentro del navegador (PC y Android).
    """

    def __init__(self):
        self.ok = False
        self.sonidos = {}
        self.recetas = {}
        self.cache_vocal = {}
        self.notas = {}
        self.silencio = False
        self.volumen = 0.9
        self.sr, self.canales = 44100, 2
        self._intentos = 0
        self._despertar()

    def _despertar(self):
        """Abre el mezclador. En el navegador puede no estar listo hasta que
        el nino toca la pantalla, por eso se reintenta mas adelante."""
        if self.ok or self._intentos > 15:
            return self.ok
        self._intentos += 1
        try:
            if pygame.mixer.get_init() is None:
                pygame.mixer.init(frequency=44100, size=-16, channels=2,
                                  buffer=512)
            info = pygame.mixer.get_init()
            if not info:
                return False
            self.sr, _tam, self.canales = info
            self.ok = True
            self._construir_banco()
        except Exception:
            self.ok = False
        return self.ok

    # -- conversion a pygame.Sound ----------------------------------------
    def _sonido(self, muestras):
        datos = array.array("h")
        if self.canales >= 2:
            for v in muestras:
                s = int(max(-1.0, min(1.0, v)) * 31000)
                datos.append(s)
                datos.append(s)
        else:
            for v in muestras:
                datos.append(int(max(-1.0, min(1.0, v)) * 31000))
        snd = pygame.mixer.Sound(buffer=datos.tobytes())
        snd.set_volume(self.volumen)
        return snd

    # -- generadores basicos ----------------------------------------------
    def _tono(self, freq, dur, vol=0.25, freq_fin=None, ataque=0.012,
              armonicos=(1.0, 0.32, 0.10), vibrato=0.0):
        n = int(self.sr * dur)
        out = [0.0] * n
        fase = 0.0
        for i in range(n):
            p = i / n
            f = freq if freq_fin is None else freq + (freq_fin - freq) * p
            if vibrato:
                f *= 1.0 + vibrato * math.sin(2 * math.pi * 5.5 * i / self.sr)
            fase += 2 * math.pi * f / self.sr
            v = 0.0
            for k, a in enumerate(armonicos, start=1):
                if a:
                    v += a * math.sin(fase * k)
            env = min(p / max(ataque / dur, 1e-4), 1.0) * (1.0 - p) ** 1.5
            out[i] = v * env * vol
        return out

    def _ruido(self, dur, vol=0.2, corte=0.25, ataque=0.01, caida=2.0):
        n = int(self.sr * dur)
        out = [0.0] * n
        prev = 0.0
        for i in range(n):
            p = i / n
            bruto = random.uniform(-1.0, 1.0)
            prev += (bruto - prev) * corte
            env = min(p / max(ataque / dur, 1e-4), 1.0) * (1.0 - p) ** caida
            out[i] = prev * env * vol
        return out

    def _mezclar(self, *capas):
        n = max(len(c) for c in capas)
        out = [0.0] * n
        for c in capas:
            for i, v in enumerate(c):
                out[i] += v
        return out

    def _encadenar(self, bloques, paso):
        """bloques: lista de listas de muestras; paso en segundos."""
        salto = int(self.sr * paso)
        total = salto * (len(bloques) - 1) + max(len(b) for b in bloques)
        out = [0.0] * total
        for i, b in enumerate(bloques):
            ini = salto * i
            for j, v in enumerate(b):
                out[ini + j] += v
        return out

    def _arpegio(self, freqs, paso, vol=0.24, dur=0.42):
        return self._encadenar(
            [self._tono(f, dur, vol, ataque=0.006) for f in freqs], paso)

    # -- banco (recetas perezosas: se sintetizan al primer uso) ------------
    def _construir_banco(self):
        m, tn, rd, ar, en = (self._mezclar, self._tono, self._ruido,
                             self._arpegio, self._encadenar)
        self.recetas = {
            # interaccion
            "click": lambda: tn(520, 0.07, 0.16, ataque=0.004),
            "pop": lambda: m(tn(420, 0.12, 0.20, freq_fin=980, ataque=0.004),
                             rd(0.06, 0.10, corte=0.5)),
            "burbuja": lambda: tn(300, 0.22, 0.16, freq_fin=900, vibrato=0.05),
            "madera": lambda: m(tn(180, 0.16, 0.22, freq_fin=120,
                                   armonicos=(1.0, 0.5, 0.25)),
                                rd(0.09, 0.14, corte=0.35, caida=3.0)),
            "agua": lambda: m(rd(0.35, 0.16, corte=0.12, ataque=0.02,
                                 caida=1.6),
                              tn(240, 0.25, 0.08, freq_fin=520, vibrato=0.08)),
            "hoja": lambda: rd(0.40, 0.10, corte=0.55, ataque=0.08, caida=1.2),
            "paso": lambda: m(rd(0.10, 0.12, corte=0.3, caida=3.0),
                              tn(140, 0.09, 0.10)),
            "whoosh": lambda: rd(0.45, 0.14, corte=0.08, ataque=0.18,
                                 caida=1.4),
            # refuerzo positivo
            "acierto": lambda: ar([523, 659, 784, 1047], 0.085),
            "estrella": lambda: ar([784, 1047, 1319], 0.07, vol=0.22,
                                   dur=0.38),
            "magia": lambda: ar([1047, 1319, 1568, 2093], 0.055, vol=0.16,
                                dur=0.32),
            "nivel": lambda: ar([523, 659, 784, 1047, 1319], 0.11, vol=0.26,
                                dur=0.55),
            "fanfarria": lambda: en([
                tn(523, 0.30, 0.24, ataque=0.006),
                tn(523, 0.30, 0.22, ataque=0.006),
                tn(659, 0.30, 0.24, ataque=0.006),
                tn(784, 0.70, 0.26, ataque=0.008),
                tn(1047, 0.90, 0.24, ataque=0.008)], 0.16),
            # error amable (nunca estridente)
            "suave": lambda: ar([392, 330], 0.14, vol=0.15),
        }
        self.recetas["error"] = self.recetas["suave"]
        for nombre in ("click", "pop", "acierto", "suave"):
            self._obtener(nombre)

    def _obtener(self, nombre):
        if nombre in self.sonidos:
            return self.sonidos[nombre]
        receta = self.recetas.get(nombre)
        if receta is None:
            return None
        try:
            self.sonidos[nombre] = self._sonido(receta())
        except Exception:
            self.sonidos[nombre] = None
        return self.sonidos[nombre]

    # -- vocales sintetizadas (se generan la primera vez que se usan) ------
    def _sintetizar_vocal(self, letra, f0=170.0, dur=0.55):
        formantes = FORMANTES.get(letra)
        if not formantes:
            return None
        periodo = max(int(self.sr / f0), 8)
        ciclo = [0.0] * periodo
        for h in range(1, 36):
            fr = f0 * h
            if fr > self.sr * 0.45:
                break
            amp = 0.0
            for fc, bw, g in formantes:
                amp += g / (1.0 + ((fr - fc) / (bw * 0.5)) ** 2)
            amp /= h ** 0.9
            if amp < 0.004:
                continue
            for i in range(periodo):
                ciclo[i] += amp * math.sin(2 * math.pi * h * i / periodo)
        pico = max(abs(v) for v in ciclo) or 1.0
        ciclo = [v / pico for v in ciclo]
        n = int(self.sr * dur)
        out = [0.0] * n
        for i in range(n):
            p = i / n
            env = min(p / 0.07, 1.0) * min((1.0 - p) / 0.25, 1.0)
            out[i] = ciclo[i % periodo] * env * 0.34
        return self._sonido(out)

    def tocar_vocal(self, letra):
        """Eco del bosque: el sonido sostenido de la vocal."""
        if self.silencio or not self._despertar():
            return
        letra = (letra or "").upper()[:1]
        if letra not in FORMANTES:
            return
        if letra not in self.cache_vocal:
            try:
                self.cache_vocal[letra] = self._sintetizar_vocal(letra)
            except Exception:
                self.cache_vocal[letra] = None
        snd = self.cache_vocal.get(letra)
        if snd:
            try:
                snd.play()
            except Exception:
                pass

    def tocar_silaba(self, silaba):
        """Marca melodica de una silaba: consonante breve + vocal sostenida."""
        if self.silencio or not silaba or not self._despertar():
            return
        vocal = ""
        for c in reversed(silaba.upper()):
            if c in FORMANTES:
                vocal = c
                break
        self.tocar("click")
        if vocal:
            self.tocar_vocal(vocal)

    def nota_voz(self, tono=1.0):
        """Nota breve de la voz de Lina, una por silaba."""
        if self.silencio or not self._despertar():
            return
        clave = int(clamp(tono, 0.70, 1.50) * 20)
        if clave not in self.notas:
            f = 300.0 * (clave / 20.0)
            try:
                self.notas[clave] = self._sonido(
                    self._tono(f, 0.11, 0.14, freq_fin=f * 1.07, ataque=0.008,
                               armonicos=(1.0, 0.45, 0.16)))
            except Exception:
                self.notas[clave] = None
        snd = self.notas.get(clave)
        if snd:
            try:
                snd.play()
            except Exception:
                pass

    def alternar_silencio(self):
        self.silencio = not self.silencio
        if self.silencio:
            try:
                pygame.mixer.stop()
            except Exception:
                pass
        return self.silencio

    def tocar(self, nombre):
        if self.silencio or not self._despertar():
            return
        snd = self._obtener(nombre)
        if snd:
            try:
                snd.play()
            except Exception:
                pass


# ==========================================================================
#  PARTICULAS
# ==========================================================================
class Particula:
    __slots__ = ("x", "y", "vx", "vy", "vida", "vida_max", "col", "r", "tipo", "rot")

    def __init__(self, x, y, vx, vy, vida, col, r, tipo="circulo"):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.vida = self.vida_max = vida
        self.col, self.r, self.tipo = col, r, tipo
        self.rot = random.uniform(0, math.tau)


class SistemaParticulas:
    def __init__(self):
        self.items = []

    def estallido(self, x, y, col, n=26, fuerza=300, tipo="circulo"):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(fuerza * 0.35, fuerza)
            self.items.append(
                Particula(
                    x, y,
                    math.cos(a) * v, math.sin(a) * v - 60,
                    random.uniform(0.5, 1.1), col,
                    random.uniform(3, 8), tipo,
                )
            )

    def confeti(self, x, y, n=40):
        cols = [C_DORADO, C_ROSA, C_MORADO, C_VERDE_OK, C_NARANJA, C_AGUA_CLARA]
        for _ in range(n):
            a = random.uniform(-math.pi * 0.85, -math.pi * 0.15)
            v = random.uniform(220, 520)
            self.items.append(
                Particula(
                    x, y, math.cos(a) * v, math.sin(a) * v,
                    random.uniform(1.2, 2.2), random.choice(cols),
                    random.uniform(5, 10), "cuadro",
                )
            )

    def brillos(self, x, y, n=10):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            v = random.uniform(30, 120)
            self.items.append(
                Particula(
                    x, y, math.cos(a) * v, math.sin(a) * v,
                    random.uniform(0.4, 0.9), C_DORADO,
                    random.uniform(2, 5), "estrella",
                )
            )

    def update(self, dt):
        vivos = []
        for p in self.items:
            p.vida -= dt
            if p.vida <= 0:
                continue
            p.x += p.vx * dt
            p.y += p.vy * dt
            p.vy += 620 * dt
            p.vx *= 0.985
            p.rot += dt * 5
            vivos.append(p)
        self.items = vivos

    def dibujar(self, surf):
        for p in self.items:
            a = clamp(p.vida / p.vida_max, 0, 1)
            r = max(int(p.r * a), 1)
            col = mezclar(C_BLANCO, p.col, a)
            if p.tipo == "cuadro":
                s = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.rect(s, col + (int(255 * a),), (0, 0, r * 2, r * 2),
                                 border_radius=2)
                s = pygame.transform.rotate(s, math.degrees(p.rot))
                surf.blit(s, s.get_rect(center=(p.x, p.y)))
            elif p.tipo == "estrella":
                dibujar_estrella(surf, p.x, p.y, r * 1.7, r * 0.7, col, p.rot)
            else:
                pygame.draw.circle(surf, col, (int(p.x), int(p.y)), r)


def dibujar_estrella(surf, cx, cy, r_ext, r_int, color, rot=0.0, puntas=5):
    pts = []
    for i in range(puntas * 2):
        r = r_ext if i % 2 == 0 else r_int
        a = rot - math.pi / 2 + i * math.pi / puntas
        pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    pygame.draw.polygon(surf, color, pts)


# ==========================================================================
#  TIPOGRAFIA
# ==========================================================================
class Fuentes:
    def __init__(self):
        base = ["Verdana", "DejaVu Sans", "Arial", "Tahoma"]
        red = ["Comic Sans MS", "Verdana", "DejaVu Sans", "Arial"]
        self.titulo = self._crear(red, 68, True)
        self.h1 = self._crear(red, 46, True)
        self.h2 = self._crear(red, 34, True)
        self.letra = self._crear(red, 56, True)
        self.silaba = self._crear(red, 40, True)
        self.cuerpo = self._crear(base, 26)
        self.chico = self._crear(base, 21)
        self.mini = self._crear(base, 17)

    def _crear(self, familias, tam, negrita=False):
        for f in familias:
            try:
                fuente = pygame.font.SysFont(f, tam, bold=negrita)
                if fuente:
                    return fuente
            except Exception:
                continue
        return pygame.font.Font(None, tam)


def texto(surf, fuente, txt, x, y, col=C_TEXTO, centro=True, sombra=False):
    if sombra:
        s = fuente.render(txt, True, (0, 0, 0))
        s.set_alpha(70)
        r = s.get_rect(center=(x + 2, y + 3)) if centro else s.get_rect(topleft=(x + 2, y + 3))
        surf.blit(s, r)
    img = fuente.render(txt, True, col)
    rect = img.get_rect(center=(x, y)) if centro else img.get_rect(topleft=(x, y))
    surf.blit(img, rect)
    return rect


def texto_envuelto(surf, fuente, txt, x, y, ancho_max, col=C_TEXTO, centro=True,
                   interlineado=6):
    palabras, lineas, actual = txt.split(" "), [], ""
    for p in palabras:
        prueba = (actual + " " + p).strip()
        if fuente.size(prueba)[0] <= ancho_max:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = p
    if actual:
        lineas.append(actual)
    alto = fuente.get_height() + interlineado
    y0 = y - (len(lineas) - 1) * alto / 2 if centro else y
    for i, ln in enumerate(lineas):
        texto(surf, fuente, ln, x, y0 + i * alto, col, centro)
    return len(lineas) * alto


# ==========================================================================
#  ILUSTRACIONES VECTORIALES (sin archivos externos)
# ==========================================================================
def _elipse(surf, col, cx, cy, rx, ry):
    pygame.draw.ellipse(surf, col, (cx - rx, cy - ry, rx * 2, ry * 2))


def dibujar_icono(surf, nombre, cx, cy, s, t=0.0):
    """Dibuja la ilustracion asociada a una palabra. s = tamano base."""
    lat = 1 + 0.03 * math.sin(t * 2.6)
    s = s * lat
    n = nombre.lower()

    if n == "avion":
        pygame.draw.polygon(surf, (238, 242, 250), [
            (cx - s * .62, cy), (cx + s * .40, cy - s * .18),
            (cx + s * .66, cy), (cx + s * .40, cy + s * .18)])
        pygame.draw.polygon(surf, (200, 214, 236), [
            (cx - s * .12, cy - s * .05), (cx + s * .18, cy - s * .52),
            (cx + s * .34, cy - s * .50), (cx + s * .16, cy - s * .02)])
        pygame.draw.polygon(surf, (200, 214, 236), [
            (cx - s * .12, cy + s * .05), (cx + s * .18, cy + s * .52),
            (cx + s * .34, cy + s * .50), (cx + s * .16, cy + s * .02)])
        pygame.draw.polygon(surf, (170, 190, 220), [
            (cx - s * .60, cy - s * .02), (cx - s * .40, cy - s * .34),
            (cx - s * .26, cy - s * .02)])
        _elipse(surf, (120, 180, 230), cx + s * .30, cy - s * .04, s * .09, s * .07)

    elif n == "elefante":
        _elipse(surf, (158, 162, 176), cx, cy + s * .08, s * .52, s * .40)
        _elipse(surf, (158, 162, 176), cx - s * .44, cy - s * .18, s * .30, s * .28)
        _elipse(surf, (136, 140, 156), cx - s * .70, cy - s * .22, s * .22, s * .26)
        pygame.draw.lines(surf, (158, 162, 176), False, [
            (cx - s * .58, cy + s * .02), (cx - s * .74, cy + s * .26),
            (cx - s * .58, cy + s * .46)], int(s * .16))
        for dx in (-.28, -.02, .26, .46):
            pygame.draw.rect(surf, (140, 144, 160),
                             (cx + s * dx, cy + s * .34, s * .16, s * .26),
                             border_radius=int(s * .05))
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .40), int(cy - s * .24)),
                           max(int(s * .05), 2))

    elif n == "iglu":
        _elipse(surf, (240, 248, 255), cx, cy + s * .20, s * .62, s * .52)
        pygame.draw.rect(surf, (240, 248, 255),
                         (cx - s * .62, cy + s * .18, s * 1.24, s * .26))
        pygame.draw.arc(surf, (176, 206, 230),
                        (cx - s * .60, cy - s * .32, s * 1.2, s * 1.0),
                        0.35, math.pi - 0.35, max(int(s * .04), 2))
        _elipse(surf, (150, 186, 216), cx, cy + s * .40, s * .20, s * .24)
        _elipse(surf, (108, 150, 188), cx, cy + s * .44, s * .15, s * .19)

    elif n == "oso":
        _elipse(surf, (150, 106, 72), cx - s * .38, cy - s * .40, s * .17, s * .17)
        _elipse(surf, (150, 106, 72), cx + s * .38, cy - s * .40, s * .17, s * .17)
        _elipse(surf, (198, 152, 112), cx - s * .38, cy - s * .40, s * .09, s * .09)
        _elipse(surf, (198, 152, 112), cx + s * .38, cy - s * .40, s * .09, s * .09)
        _elipse(surf, (164, 118, 82), cx, cy, s * .54, s * .50)
        _elipse(surf, (214, 176, 138), cx, cy + s * .16, s * .30, s * .24)
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .20), int(cy - s * .12)),
                           max(int(s * .06), 2))
        pygame.draw.circle(surf, C_TEXTO, (int(cx + s * .20), int(cy - s * .12)),
                           max(int(s * .06), 2))
        _elipse(surf, (70, 52, 44), cx, cy + s * .10, s * .09, s * .07)

    elif n == "uvas":
        pygame.draw.line(surf, (110, 140, 70),
                         (cx, cy - s * .62), (cx, cy - s * .34), max(int(s * .05), 2))
        pygame.draw.polygon(surf, (126, 176, 92), [
            (cx + s * .04, cy - s * .52), (cx + s * .44, cy - s * .62),
            (cx + s * .26, cy - s * .34)])
        filas = [(-.24, 3), (-.02, 4), (.20, 3), (.40, 2)]
        for dy, cant in filas:
            for i in range(cant):
                ox = (i - (cant - 1) / 2) * s * .26
                _elipse(surf, (132, 92, 176), cx + ox, cy + s * dy, s * .14, s * .14)
                _elipse(surf, (168, 132, 208), cx + ox - s * .04, cy + s * dy - s * .04,
                        s * .05, s * .05)

    elif n == "arana":
        for lado in (-1, 1):
            for i, dy in enumerate((-.16, .02, .20)):
                pygame.draw.lines(surf, (60, 52, 62), False, [
                    (cx, cy + s * dy),
                    (cx + lado * s * .42, cy + s * (dy - .18 + i * .06)),
                    (cx + lado * s * .60, cy + s * (dy + .22))],
                    max(int(s * .05), 2))
        _elipse(surf, (70, 60, 74), cx, cy + s * .06, s * .34, s * .30)
        _elipse(surf, (52, 44, 56), cx, cy - s * .22, s * .22, s * .20)
        for dx in (-.09, .09):
            pygame.draw.circle(surf, C_BLANCO,
                               (int(cx + s * dx), int(cy - s * .26)), max(int(s * .06), 2))
            pygame.draw.circle(surf, C_TEXTO,
                               (int(cx + s * dx), int(cy - s * .26)), max(int(s * .03), 1))

    elif n == "estrella":
        dibujar_estrella(surf, cx, cy, s * .66, s * .28, C_DORADO, t * .6)
        dibujar_estrella(surf, cx, cy, s * .50, s * .20, (255, 226, 140), t * .6)

    elif n == "iman":
        pygame.draw.arc(surf, (222, 74, 74),
                        (cx - s * .52, cy - s * .58, s * 1.04, s * 1.04),
                        0.0, math.pi, int(s * .30))
        pygame.draw.rect(surf, (222, 74, 74),
                         (cx - s * .52, cy - s * .06, s * .30, s * .48))
        pygame.draw.rect(surf, (222, 74, 74),
                         (cx + s * .22, cy - s * .06, s * .30, s * .48))
        pygame.draw.rect(surf, (238, 240, 246),
                         (cx - s * .52, cy + s * .26, s * .30, s * .22))
        pygame.draw.rect(surf, (238, 240, 246),
                         (cx + s * .22, cy + s * .26, s * .30, s * .22))

    elif n == "mapa":
        pygame.draw.polygon(surf, (246, 232, 198), [
            (cx - s * .62, cy - s * .40), (cx - s * .04, cy - s * .52),
            (cx + s * .62, cy - s * .34), (cx + s * .62, cy + s * .46),
            (cx - s * .04, cy + s * .56), (cx - s * .62, cy + s * .42)])
        pygame.draw.lines(surf, (198, 172, 130), False, [
            (cx - s * .04, cy - s * .52), (cx - s * .04, cy + s * .56)], 2)
        pygame.draw.lines(surf, (206, 96, 76), False, [
            (cx - s * .44, cy + s * .26), (cx - s * .16, cy - s * .04),
            (cx + s * .14, cy + s * .18), (cx + s * .42, cy - s * .18)], 3)
        pygame.draw.circle(surf, (206, 96, 76),
                           (int(cx + s * .42), int(cy - s * .18)), max(int(s * .07), 3))

    elif n == "mesa":
        pygame.draw.rect(surf, C_MADERA,
                         (cx - s * .66, cy - s * .26, s * 1.32, s * .20),
                         border_radius=int(s * .06))
        pygame.draw.rect(surf, C_MADERA_OSC,
                         (cx - s * .66, cy - s * .10, s * 1.32, s * .07))
        for dx in (-.54, .40):
            pygame.draw.rect(surf, C_MADERA_OSC,
                             (cx + s * dx, cy - s * .06, s * .14, s * .60),
                             border_radius=int(s * .04))

    elif n == "luna":
        _elipse(surf, (255, 238, 176), cx, cy, s * .56, s * .56)
        _elipse(surf, (234, 244, 255), cx + s * .22, cy - s * .12, s * .46, s * .46)
        for dx, dy, r in ((-.20, .16, .09), (-.06, -.24, .06), (-.30, -.06, .05)):
            _elipse(surf, (238, 214, 140), cx + s * dx, cy + s * dy, s * r, s * r)

    elif n == "pato":
        _elipse(surf, (252, 214, 96), cx, cy + s * .10, s * .50, s * .38)
        _elipse(surf, (252, 214, 96), cx + s * .34, cy - s * .26, s * .26, s * .25)
        pygame.draw.polygon(surf, (248, 152, 58), [
            (cx + s * .54, cy - s * .26), (cx + s * .84, cy - s * .18),
            (cx + s * .54, cy - s * .10)])
        pygame.draw.circle(surf, C_TEXTO,
                           (int(cx + s * .40), int(cy - s * .32)), max(int(s * .05), 2))
        _elipse(surf, (240, 196, 80), cx - s * .10, cy + s * .10, s * .26, s * .18)
        pygame.draw.polygon(surf, (248, 152, 58), [
            (cx - s * .16, cy + s * .44), (cx + s * .10, cy + s * .44),
            (cx - s * .04, cy + s * .58)])

    elif n == "sapo":
        _elipse(surf, (118, 190, 108), cx, cy + s * .14, s * .58, s * .38)
        _elipse(surf, (118, 190, 108), cx, cy - s * .12, s * .44, s * .32)
        for dx in (-.22, .22):
            _elipse(surf, (140, 208, 126), cx + s * dx, cy - s * .34, s * .16, s * .16)
            pygame.draw.circle(surf, C_BLANCO,
                               (int(cx + s * dx), int(cy - s * .34)), max(int(s * .10), 3))
            pygame.draw.circle(surf, C_TEXTO,
                               (int(cx + s * dx), int(cy - s * .34)), max(int(s * .05), 2))
        pygame.draw.arc(surf, (70, 130, 70),
                        (cx - s * .30, cy - s * .22, s * .60, s * .40),
                        math.pi + 0.3, math.tau - 0.3, max(int(s * .05), 2))
        for lado in (-1, 1):
            _elipse(surf, (100, 172, 96), cx + lado * s * .50, cy + s * .34,
                    s * .18, s * .12)

    elif n == "pala":
        pygame.draw.rect(surf, C_MADERA,
                         (cx - s * .07, cy - s * .58, s * .14, s * .74),
                         border_radius=int(s * .04))
        pygame.draw.circle(surf, C_MADERA, (int(cx), int(cy - s * .58)),
                           int(s * .16), int(s * .07))
        pygame.draw.polygon(surf, (176, 182, 192), [
            (cx - s * .30, cy + s * .10), (cx + s * .30, cy + s * .10),
            (cx + s * .22, cy + s * .56), (cx - s * .22, cy + s * .56)])
        pygame.draw.polygon(surf, (206, 212, 222), [
            (cx - s * .30, cy + s * .10), (cx + s * .30, cy + s * .10),
            (cx + s * .26, cy + s * .26), (cx - s * .26, cy + s * .26)])

    elif n == "lupa":
        pygame.draw.line(surf, C_MADERA_OSC,
                         (cx + s * .18, cy + s * .18), (cx + s * .56, cy + s * .58),
                         int(s * .16))
        pygame.draw.circle(surf, (206, 232, 246), (int(cx - s * .10), int(cy - s * .12)),
                           int(s * .38))
        pygame.draw.circle(surf, (110, 120, 136), (int(cx - s * .10), int(cy - s * .12)),
                           int(s * .38), max(int(s * .08), 3))
        pygame.draw.arc(surf, C_BLANCO,
                        (cx - s * .38, cy - s * .40, s * .40, s * .40),
                        0.6, 2.0, max(int(s * .05), 2))

    elif n == "puma":
        _elipse(surf, (212, 158, 100), cx, cy + s * .12, s * .54, s * .34)
        _elipse(surf, (212, 158, 100), cx - s * .40, cy - s * .18, s * .26, s * .24)
        for dx in (-.54, -.26):
            pygame.draw.polygon(surf, (212, 158, 100), [
                (cx + s * dx, cy - s * .34), (cx + s * (dx + .10), cy - s * .56),
                (cx + s * (dx + .18), cy - s * .32)])
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .48), int(cy - s * .20)),
                           max(int(s * .04), 2))
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .30), int(cy - s * .20)),
                           max(int(s * .04), 2))
        pygame.draw.lines(surf, (212, 158, 100), False, [
            (cx + s * .50, cy + s * .06), (cx + s * .70, cy - s * .16),
            (cx + s * .62, cy - s * .40)], int(s * .10))
        for dx in (-.30, .00, .30):
            pygame.draw.rect(surf, (190, 138, 84),
                             (cx + s * dx, cy + s * .36, s * .14, s * .20),
                             border_radius=int(s * .04))

    # ---------------------------------------------------------- VOCAL A ---
    elif n == "abeja":
        al = math.sin(t * 14) * s * .06
        _elipse(surf, (232, 244, 252), cx - s * .14, cy - s * .34 + al, s * .26, s * .15)
        _elipse(surf, (232, 244, 252), cx + s * .14, cy - s * .34 - al, s * .26, s * .15)
        _elipse(surf, (250, 204, 72), cx, cy + s * .06, s * .46, s * .32)
        for dx, rx in ((-.10, .10), (.10, .09), (.28, .06)):
            _elipse(surf, (76, 60, 44), cx + s * dx, cy + s * .06, s * rx, s * .30)
        _elipse(surf, (250, 204, 72), cx - s * .44, cy - s * .04, s * .20, s * .20)
        pygame.draw.polygon(surf, (76, 60, 44), [
            (cx + s * .44, cy + s * .04), (cx + s * .62, cy + s * .10),
            (cx + s * .44, cy + s * .14)])
        for lado in (-1, 1):
            pygame.draw.line(surf, (76, 60, 44),
                             (cx - s * .48, cy - s * .16),
                             (cx - s * .58, cy - s * .40 + lado * s * .06),
                             max(int(s * .04), 2))
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .48), int(cy - s * .06)),
                           max(int(s * .05), 2))

    elif n == "arbol":
        pygame.draw.rect(surf, C_TRONCO,
                         (cx - s * .10, cy + s * .10, s * .20, s * .52),
                         border_radius=int(s * .05))
        _elipse(surf, (62, 148, 92), cx, cy - s * .28, s * .40, s * .34)
        _elipse(surf, (76, 168, 104), cx - s * .32, cy - s * .02, s * .30, s * .26)
        _elipse(surf, (76, 168, 104), cx + s * .32, cy - s * .02, s * .30, s * .26)
        _elipse(surf, (98, 190, 118), cx - s * .10, cy - s * .34, s * .18, s * .14)
        _elipse(surf, (110, 82, 56), cx, cy + s * .62, s * .34, s * .08)

    elif n == "anillo":
        pygame.draw.circle(surf, C_DORADO_OSC, (int(cx), int(cy + s * .14)),
                           int(s * .40))
        pygame.draw.circle(surf, C_DORADO, (int(cx), int(cy + s * .14)),
                           int(s * .40), int(s * .12))
        pygame.draw.polygon(surf, (150, 226, 246), [
            (cx, cy - s * .62), (cx + s * .22, cy - s * .36),
            (cx, cy - s * .14), (cx - s * .22, cy - s * .36)])
        pygame.draw.polygon(surf, (208, 244, 252), [
            (cx, cy - s * .62), (cx + s * .10, cy - s * .36),
            (cx, cy - s * .14)])
        dibujar_estrella(surf, cx + s * .18, cy - s * .52, s * .10, s * .04, C_BLANCO)

    # ---------------------------------------------------------- VOCAL E ---
    elif n == "erizo":
        for i in range(15):
            a = math.pi + i * math.pi / 14
            x1 = cx + math.cos(a) * s * .38
            y1 = cy + math.sin(a) * s * .34
            pygame.draw.line(surf, (96, 70, 52),
                             (x1, y1 + s * .06),
                             (cx + math.cos(a) * s * .68,
                              cy + math.sin(a) * s * .62 + s * .06),
                             max(int(s * .05), 2))
        _elipse(surf, (176, 134, 96), cx, cy + s * .14, s * .46, s * .34)
        _elipse(surf, (226, 196, 158), cx + s * .34, cy + s * .16, s * .22, s * .20)
        pygame.draw.polygon(surf, (70, 56, 48), [
            (cx + s * .52, cy + s * .12), (cx + s * .64, cy + s * .18),
            (cx + s * .52, cy + s * .24)])
        pygame.draw.circle(surf, C_TEXTO, (int(cx + s * .34), int(cy + s * .08)),
                           max(int(s * .05), 2))

    elif n == "escoba":
        pygame.draw.line(surf, C_MADERA_OSC, (cx - s * .26, cy - s * .62),
                         (cx + s * .06, cy + s * .10), max(int(s * .09), 3))
        pygame.draw.polygon(surf, (226, 182, 96), [
            (cx - s * .10, cy + s * .06), (cx + s * .22, cy + s * .06),
            (cx + s * .44, cy + s * .60), (cx - s * .30, cy + s * .60)])
        for i in range(6):
            x = cx - s * .26 + i * s * .14
            pygame.draw.line(surf, (198, 152, 70), (x + s * .12, cy + s * .12),
                             (x, cy + s * .58), max(int(s * .03), 1))
        pygame.draw.rect(surf, (170, 120, 70),
                         (cx - s * .14, cy - s * .02, s * .30, s * .12),
                         border_radius=int(s * .04))

    # ---------------------------------------------------------- VOCAL I ---
    elif n == "isla":
        _elipse(surf, C_AGUA, cx, cy + s * .50, s * .74, s * .22)
        _elipse(surf, C_AGUA_CLARA, cx, cy + s * .46, s * .60, s * .14)
        _elipse(surf, (240, 220, 160), cx, cy + s * .34, s * .46, s * .18)
        pygame.draw.line(surf, C_TRONCO, (cx, cy + s * .34),
                         (cx - s * .10, cy - s * .28), max(int(s * .07), 3))
        for a, larg in ((-2.6, .40), (-2.0, .34), (-1.1, .34), (-.5, .40)):
            pygame.draw.polygon(surf, (68, 158, 98), [
                (cx - s * .10, cy - s * .30),
                (cx - s * .10 + math.cos(a) * s * larg,
                 cy - s * .30 + math.sin(a) * s * larg),
                (cx - s * .10 + math.cos(a + .5) * s * (larg * .8),
                 cy - s * .30 + math.sin(a + .5) * s * (larg * .8))])
        pygame.draw.circle(surf, (200, 120, 70), (int(cx - s * .02), int(cy - s * .30)),
                           max(int(s * .05), 2))

    elif n == "iguana":
        pygame.draw.polygon(surf, (86, 170, 96), [
            (cx + s * .20, cy + s * .04), (cx + s * .68, cy - s * .18),
            (cx + s * .66, cy + s * .02), (cx + s * .24, cy + s * .20)])
        for i in range(5):
            x = cx - s * .28 + i * s * .14
            pygame.draw.polygon(surf, (58, 132, 74), [
                (x, cy - s * .16), (x + s * .06, cy - s * .40),
                (x + s * .12, cy - s * .16)])
        _elipse(surf, (96, 186, 108), cx, cy + s * .06, s * .44, s * .26)
        _elipse(surf, (110, 200, 120), cx - s * .46, cy - s * .04, s * .24, s * .18)
        for dx in (-.18, .16):
            pygame.draw.line(surf, (72, 156, 88), (cx + s * dx, cy + s * .22),
                             (cx + s * dx - s * .06, cy + s * .44),
                             max(int(s * .06), 2))
        pygame.draw.circle(surf, C_CREMA, (int(cx - s * .54), int(cy - s * .10)),
                           max(int(s * .06), 2))
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .54), int(cy - s * .10)),
                           max(int(s * .03), 1))

    # ---------------------------------------------------------- VOCAL O ---
    elif n == "ojo":
        _elipse(surf, C_BLANCO, cx, cy + s * .04, s * .58, s * .34)
        pygame.draw.ellipse(surf, (120, 110, 104),
                            (cx - s * .58, cy - s * .30, s * 1.16, s * .68), 
                            max(int(s * .04), 2))
        pygame.draw.circle(surf, (74, 142, 196), (int(cx), int(cy + s * .04)),
                           int(s * .24))
        pygame.draw.circle(surf, C_TEXTO, (int(cx), int(cy + s * .04)),
                           int(s * .11))
        pygame.draw.circle(surf, C_BLANCO, (int(cx - s * .08), int(cy - s * .06)),
                           max(int(s * .06), 2))
        pygame.draw.arc(surf, (90, 72, 60),
                        (cx - s * .56, cy - s * .58, s * 1.12, s * .50),
                        0.35, math.pi - 0.35, max(int(s * .06), 2))

    elif n == "oveja":
        for dx, dy, r in ((-.34, .0, .24), (.34, .0, .24), (-.16, -.24, .26),
                          (.16, -.24, .26), (0, .06, .34)):
            pygame.draw.circle(surf, C_BLANCO,
                               (int(cx + s * dx), int(cy + s * dy)), int(s * r))
        for dx in (-.26, .0, .26):
            pygame.draw.line(surf, (70, 62, 60), (cx + s * dx, cy + s * .34),
                             (cx + s * dx, cy + s * .58), max(int(s * .06), 2))
        _elipse(surf, (86, 78, 76), cx - s * .44, cy - s * .10, s * .20, s * .22)
        _elipse(surf, (70, 62, 60), cx - s * .62, cy - s * .18, s * .10, s * .06)
        _elipse(surf, (70, 62, 60), cx - s * .28, cy - s * .22, s * .10, s * .06)
        pygame.draw.circle(surf, C_BLANCO, (int(cx - s * .48), int(cy - s * .12)),
                           max(int(s * .04), 2))

    elif n == "ola":
        _elipse(surf, (86, 168, 206), cx, cy + s * .52, s * .80, s * .14)
        pygame.draw.polygon(surf, C_AGUA, [
            (cx + s * .76, cy + s * .50), (cx + s * .66, cy + s * .02),
            (cx + s * .50, cy - s * .34), (cx + s * .26, cy - s * .54),
            (cx - s * .26, cy - s * .36), (cx + s * .04, cy - s * .18),
            (cx + s * .26, cy - s * .08), (cx + s * .08, cy + s * .16),
            (cx - s * .32, cy + s * .38), (cx - s * .76, cy + s * .50)])
        pygame.draw.polygon(surf, C_AGUA_CLARA, [
            (cx + s * .26, cy - s * .54), (cx + s * .50, cy - s * .34),
            (cx + s * .66, cy + s * .02), (cx + s * .50, cy - s * .04),
            (cx + s * .34, cy - s * .30)])
        for dx, dy, r in ((-.24, -.38, .11), (.02, -.50, .13), (.28, -.56, .12),
                          (.46, -.40, .09)):
            _elipse(surf, C_BLANCO, cx + s * dx, cy + s * dy, s * r, s * (r * .85))
        for dx, dy in ((-.50, .38), (-.14, .44), (.28, .40)):
            _elipse(surf, C_BLANCO, cx + s * dx, cy + s * dy, s * .11, s * .05)

    elif n == "oruga":
        for i in range(5):
            x = cx - s * .44 + i * s * .24
            y = cy + math.sin(t * 3 + i * .9) * s * .06
            pygame.draw.circle(surf, (118, 194, 96) if i % 2 else (96, 176, 80),
                               (int(x), int(y + s * .10)), int(s * .19))
        pygame.draw.circle(surf, (150, 210, 110),
                           (int(cx + s * .58), int(cy + s * .06)), int(s * .22))
        for lado in (-1, 1):
            pygame.draw.line(surf, (96, 176, 80),
                             (cx + s * .58, cy - s * .10),
                             (cx + s * .66, cy - s * .40 + lado * s * .10),
                             max(int(s * .04), 2))
        pygame.draw.circle(surf, C_TEXTO, (int(cx + s * .64), int(cy + s * .02)),
                           max(int(s * .04), 2))
        pygame.draw.arc(surf, C_TEXTO,
                        (cx + s * .48, cy + s * .04, s * .22, s * .18),
                        math.pi, 2 * math.pi, max(int(s * .03), 1))

    # ---------------------------------------------------------- VOCAL U ---
    elif n == "uno":
        pygame.draw.rect(surf, C_CREMA,
                         (cx - s * .40, cy - s * .60, s * .80, s * 1.20),
                         border_radius=int(s * .14))
        pygame.draw.rect(surf, C_NARANJA,
                         (cx - s * .40, cy - s * .60, s * .80, s * 1.20),
                         max(int(s * .06), 2), border_radius=int(s * .14))
        pygame.draw.polygon(surf, C_NARANJA, [
            (cx - s * .18, cy - s * .20), (cx + s * .04, cy - s * .40),
            (cx + s * .12, cy - s * .40), (cx + s * .12, cy + s * .30),
            (cx - s * .02, cy + s * .30), (cx - s * .02, cy - s * .20)])
        pygame.draw.rect(surf, C_NARANJA,
                         (cx - s * .20, cy + s * .30, s * .46, s * .12),
                         border_radius=int(s * .04))

    elif n == "unicornio":
        _elipse(surf, C_BLANCO, cx, cy + s * .10, s * .40, s * .34)
        _elipse(surf, C_BLANCO, cx - s * .34, cy + s * .28, s * .24, s * .18)
        pygame.draw.polygon(surf, C_BLANCO, [
            (cx + s * .18, cy - s * .24), (cx + s * .34, cy - s * .58),
            (cx + s * .40, cy - s * .20)])
        pygame.draw.polygon(surf, C_DORADO, [
            (cx - s * .04, cy - s * .30), (cx + s * .10, cy - s * .78),
            (cx + s * .16, cy - s * .28)])
        for i in range(3):
            pygame.draw.line(surf, C_DORADO_OSC,
                             (cx - s * .02 + i * s * .05, cy - s * (.36 + i * .14)),
                             (cx + s * .14 - i * s * .03, cy - s * (.40 + i * .14)),
                             max(int(s * .03), 1))
        for i, col in enumerate((C_ROSA, C_MORADO, (120, 200, 236))):
            pygame.draw.arc(surf, col,
                            (cx + s * (.10 + i * .08), cy - s * .30,
                             s * .40, s * .84), 1.2, 3.0, max(int(s * .07), 3))
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .14), int(cy + s * .06)),
                           max(int(s * .05), 2))
        _elipse(surf, (240, 200, 208), cx - s * .40, cy + s * .28, s * .07, s * .05)

    # ------------------------------------------------- PALABRAS SILABICAS --
    elif n == "sopa":
        _elipse(surf, (198, 202, 210), cx, cy + s * .50, s * .56, s * .12)
        pygame.draw.polygon(surf, (96, 172, 208), [
            (cx - s * .58, cy - s * .06), (cx + s * .58, cy - s * .06),
            (cx + s * .36, cy + s * .46), (cx - s * .36, cy + s * .46)])
        pygame.draw.polygon(surf, (70, 146, 186), [
            (cx - s * .58, cy + s * .16), (cx + s * .58, cy + s * .16),
            (cx + s * .36, cy + s * .46), (cx - s * .36, cy + s * .46)])
        _elipse(surf, (232, 236, 242), cx, cy - s * .06, s * .58, s * .17)
        _elipse(surf, (240, 168, 72), cx, cy - s * .04, s * .48, s * .13)
        _elipse(surf, (252, 206, 118), cx - s * .14, cy - s * .06, s * .14, s * .05)
        for dx in (-.16, .14):
            _elipse(surf, (226, 118, 96), cx + s * dx, cy - s * .02, s * .06, s * .03)
        for i, dx in enumerate((-.22, .02, .26)):
            pygame.draw.arc(surf, (220, 226, 230),
                            (cx + s * dx - s * .10, cy - s * .54 +
                             math.sin(t * 2 + i) * s * .04, s * .22, s * .40),
                            0.4, 3.2, max(int(s * .04), 2))

    elif n == "pino":
        pygame.draw.rect(surf, C_TRONCO_OSCURO,
                         (cx - s * .09, cy + s * .34, s * .18, s * .30))
        for i, (dy, w) in enumerate(((-.56, .26), (-.22, .38), (.14, .50))):
            pygame.draw.polygon(surf, (54, 136, 84) if i % 2 else (68, 156, 96), [
                (cx, cy + s * dy - s * .26), (cx - s * w, cy + s * dy + s * .18),
                (cx + s * w, cy + s * dy + s * .18)])
        dibujar_estrella(surf, cx, cy - s * .82, s * .12, s * .05, C_DORADO, t)

    elif n == "mono":
        _elipse(surf, (150, 108, 74), cx - s * .48, cy - s * .12, s * .18, s * .18)
        _elipse(surf, (150, 108, 74), cx + s * .48, cy - s * .12, s * .18, s * .18)
        _elipse(surf, (206, 170, 132), cx - s * .48, cy - s * .12, s * .10, s * .10)
        _elipse(surf, (206, 170, 132), cx + s * .48, cy - s * .12, s * .10, s * .10)
        _elipse(surf, (150, 108, 74), cx, cy, s * .46, s * .44)
        _elipse(surf, (226, 196, 160), cx, cy + s * .14, s * .34, s * .30)
        _elipse(surf, (226, 196, 160), cx, cy - s * .22, s * .28, s * .16)
        for dx in (-.16, .16):
            pygame.draw.circle(surf, C_TEXTO,
                               (int(cx + s * dx), int(cy - s * .08)),
                               max(int(s * .06), 2))
        _elipse(surf, (120, 88, 64), cx, cy + s * .10, s * .08, s * .05)
        pygame.draw.arc(surf, C_TEXTO,
                        (cx - s * .18, cy + s * .12, s * .36, s * .24),
                        math.pi, 2 * math.pi, max(int(s * .04), 2))

    elif n == "dado":
        pygame.draw.rect(surf, C_BLANCO,
                         (cx - s * .48, cy - s * .48, s * .96, s * .96),
                         border_radius=int(s * .16))
        pygame.draw.rect(surf, (206, 200, 190),
                         (cx - s * .48, cy - s * .48, s * .96, s * .96),
                         max(int(s * .05), 2), border_radius=int(s * .16))
        for dx, dy in ((-.26, -.26), (.26, -.26), (0, 0), (-.26, .26), (.26, .26)):
            pygame.draw.circle(surf, (200, 64, 72),
                               (int(cx + s * dx), int(cy + s * dy)),
                               max(int(s * .09), 3))

    elif n == "nido":
        _elipse(surf, (128, 90, 54), cx, cy + s * .28, s * .64, s * .30)
        for dx, dy in ((-.26, -.12), (.26, -.12), (.00, -.24)):
            _elipse(surf, (236, 230, 214), cx + s * dx, cy + s * dy,
                    s * .18, s * .22)
            pygame.draw.ellipse(surf, (192, 182, 160),
                                (cx + s * dx - s * .18, cy + s * dy - s * .22,
                                 s * .36, s * .44), max(int(s * .03), 1))
            _elipse(surf, C_BLANCO, cx + s * dx - s * .05, cy + s * dy - s * .08,
                    s * .06, s * .07)
        _elipse(surf, (158, 116, 70), cx, cy + s * .28, s * .64, s * .22)
        _elipse(surf, (132, 94, 56), cx, cy + s * .34, s * .50, s * .12)
        for i in range(9):
            a = math.pi + i * math.pi / 8
            pygame.draw.line(surf, (110, 78, 46),
                             (cx + math.cos(a) * s * .60, cy + s * .26 +
                              math.sin(a) * s * .16),
                             (cx + math.cos(a) * s * .70, cy + s * .30 +
                              math.sin(a) * s * .22), max(int(s * .035), 1))

    elif n == "taza":
        pygame.draw.arc(surf, (220, 96, 92),
                        (cx + s * .20, cy - s * .16, s * .46, s * .46),
                        -1.4, 1.4, max(int(s * .09), 3))
        _elipse(surf, (212, 216, 222), cx - s * .06, cy + s * .52, s * .48, s * .10)
        pygame.draw.rect(surf, (226, 108, 102),
                         (cx - s * .48, cy - s * .24, s * .80, s * .70),
                         border_radius=int(s * .14))
        pygame.draw.rect(surf, C_CREMA,
                         (cx - s * .48, cy + s * .04, s * .80, s * .14))
        _elipse(surf, (246, 248, 250), cx - s * .08, cy - s * .24, s * .40, s * .11)
        _elipse(surf, (170, 116, 78), cx - s * .08, cy - s * .23, s * .31, s * .07)
        for i, dx in enumerate((-.18, .06)):
            pygame.draw.arc(surf, (218, 224, 228),
                            (cx + s * dx - s * .08, cy - s * .66 +
                             math.sin(t * 2 + i) * s * .04, s * .20, s * .36),
                            0.4, 3.2, max(int(s * .04), 2))

    elif n == "lata":
        _elipse(surf, (206, 210, 216), cx, cy + s * .46, s * .34, s * .12)
        pygame.draw.rect(surf, (226, 230, 236),
                         (cx - s * .34, cy - s * .46, s * .68, s * .92))
        pygame.draw.rect(surf, (222, 86, 86),
                         (cx - s * .34, cy - s * .14, s * .68, s * .38))
        _elipse(surf, (246, 248, 250), cx, cy - s * .46, s * .34, s * .12)
        _elipse(surf, (196, 200, 208), cx, cy - s * .46, s * .22, s * .07)
        pygame.draw.line(surf, (240, 244, 248), (cx - s * .18, cy - s * .40),
                         (cx - s * .18, cy + s * .40), max(int(s * .04), 2))

    elif n == "mano":
        for i, (dx, alto) in enumerate(((-.30, .44), (-.10, .58), (.10, .54),
                                        (.30, .44))):
            pygame.draw.rect(surf, (244, 202, 170),
                             (cx + s * dx - s * .09, cy - s * alto,
                              s * .18, s * (alto + .30)),
                             border_radius=int(s * .09))
        pygame.draw.rect(surf, (244, 202, 170),
                         (cx - s * .40, cy - s * .16, s * .80, s * .56),
                         border_radius=int(s * .16))
        pygame.draw.rect(surf, (238, 188, 156),
                         (cx - s * .62, cy - s * .12, s * .30, s * .20),
                         border_radius=int(s * .10))
        pygame.draw.arc(surf, (226, 172, 142),
                        (cx - s * .26, cy - s * .04, s * .52, s * .34),
                        3.5, 6.0, max(int(s * .04), 2))

    elif n == "loro":
        pygame.draw.polygon(surf, (72, 166, 96), [
            (cx + s * .10, cy + s * .18), (cx + s * .58, cy + s * .58),
            (cx + s * .26, cy + s * .48)])
        _elipse(surf, (96, 190, 110), cx, cy + s * .10, s * .38, s * .44)
        _elipse(surf, (72, 166, 96), cx + s * .16, cy + s * .12, s * .20, s * .30)
        _elipse(surf, (236, 196, 72), cx - s * .16, cy - s * .30, s * .28, s * .28)
        _elipse(surf, (220, 90, 84), cx - s * .20, cy - s * .44, s * .20, s * .14)
        pygame.draw.polygon(surf, (244, 152, 60), [
            (cx - s * .36, cy - s * .28), (cx - s * .62, cy - s * .16),
            (cx - s * .34, cy - s * .08)])
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .18), int(cy - s * .32)),
                           max(int(s * .05), 2))
        pygame.draw.line(surf, (198, 140, 60), (cx - s * .06, cy + s * .50),
                         (cx - s * .06, cy + s * .64), max(int(s * .05), 2))

    elif n == "moto":
        for dx in (-.44, .44):
            pygame.draw.circle(surf, (58, 54, 56),
                               (int(cx + s * dx), int(cy + s * .28)), int(s * .26))
            pygame.draw.circle(surf, (170, 174, 180),
                               (int(cx + s * dx), int(cy + s * .28)), int(s * .10))
        pygame.draw.lines(surf, (210, 70, 70), False, [
            (cx - s * .44, cy + s * .28), (cx - s * .06, cy - s * .02),
            (cx + s * .44, cy + s * .28)], max(int(s * .09), 3))
        pygame.draw.rect(surf, (52, 52, 58),
                         (cx - s * .34, cy - s * .18, s * .44, s * .16),
                         border_radius=int(s * .06))
        pygame.draw.line(surf, (90, 92, 98), (cx + s * .12, cy - s * .10),
                         (cx + s * .40, cy - s * .34), max(int(s * .06), 2))
        pygame.draw.line(surf, (52, 52, 58), (cx + s * .28, cy - s * .38),
                         (cx + s * .54, cy - s * .30), max(int(s * .06), 2))

    elif n == "maleta":
        pygame.draw.arc(surf, (92, 62, 42),
                        (cx - s * .22, cy - s * .62, s * .44, s * .34),
                        0.15, math.pi - 0.15, max(int(s * .07), 3))
        pygame.draw.rect(surf, C_MADERA,
                         (cx - s * .56, cy - s * .40, s * 1.12, s * .86),
                         border_radius=int(s * .10))
        pygame.draw.rect(surf, C_MADERA_OSC,
                         (cx - s * .56, cy - s * .40, s * 1.12, s * .86),
                         max(int(s * .05), 2), border_radius=int(s * .10))
        for dx in (-.28, .28):
            pygame.draw.rect(surf, (86, 62, 46),
                             (cx + s * dx - s * .06, cy - s * .40, s * .12, s * .86))
        pygame.draw.rect(surf, C_DORADO,
                         (cx - s * .08, cy - s * .04, s * .16, s * .14),
                         border_radius=int(s * .04))

    elif n == "pelota":
        pygame.draw.circle(surf, C_BLANCO, (int(cx), int(cy)), int(s * .52))
        pygame.draw.circle(surf, (170, 174, 182), (int(cx), int(cy)),
                           int(s * .52), max(int(s * .04), 2))
        pts = [(cx + math.cos(a) * s * .18, cy + math.sin(a) * s * .18)
               for a in [(-math.pi / 2) + i * 2 * math.pi / 5 for i in range(5)]]
        pygame.draw.polygon(surf, (46, 46, 52), pts)
        for i in range(5):
            a = (-math.pi / 2) + i * 2 * math.pi / 5 + math.pi / 5
            pygame.draw.polygon(surf, (46, 46, 52), [
                (cx + math.cos(a - .32) * s * .34, cy + math.sin(a - .32) * s * .34),
                (cx + math.cos(a) * s * .52, cy + math.sin(a) * s * .52),
                (cx + math.cos(a + .32) * s * .34, cy + math.sin(a + .32) * s * .34)])

    elif n == "tomate":
        pygame.draw.circle(surf, (214, 62, 56), (int(cx), int(cy + s * .08)),
                           int(s * .48))
        pygame.draw.circle(surf, (238, 96, 84), (int(cx - s * .14),
                                                 int(cy - s * .06)), int(s * .16))
        for a in range(5):
            ang = a * 2 * math.pi / 5 - math.pi / 2
            pygame.draw.polygon(surf, (84, 166, 82), [
                (cx, cy - s * .40),
                (cx + math.cos(ang) * s * .32, cy - s * .40 + math.sin(ang) * s * .18),
                (cx + math.cos(ang + .6) * s * .22,
                 cy - s * .40 + math.sin(ang + .6) * s * .14)])
        pygame.draw.line(surf, (96, 148, 72), (cx, cy - s * .40),
                         (cx, cy - s * .62), max(int(s * .06), 2))

    elif n == "paloma":
        pygame.draw.polygon(surf, (216, 226, 240), [
            (cx + s * .20, cy + s * .04), (cx + s * .74, cy - s * .12),
            (cx + s * .74, cy + s * .22), (cx + s * .22, cy + s * .22)])
        _elipse(surf, C_BLANCO, cx, cy + s * .10, s * .46, s * .30)
        _elipse(surf, C_BLANCO, cx - s * .40, cy - s * .20, s * .21, s * .21)
        pygame.draw.polygon(surf, (246, 176, 74), [
            (cx - s * .56, cy - s * .22), (cx - s * .78, cy - s * .14),
            (cx - s * .54, cy - s * .06)])
        pygame.draw.polygon(surf, (238, 244, 252), [
            (cx - s * .16, cy + s * .00), (cx + s * .10, cy - s * .46),
            (cx + s * .30, cy - s * .34), (cx + s * .22, cy + s * .10)])
        pygame.draw.polygon(surf, (206, 218, 234), [
            (cx - s * .10, cy + s * .02), (cx + s * .12, cy - s * .30),
            (cx + s * .20, cy + s * .06)])
        pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .44), int(cy - s * .24)),
                           max(int(s * .04), 2))
        for dx in (-.10, .06):
            pygame.draw.line(surf, (246, 176, 74), (cx + s * dx, cy + s * .36),
                             (cx + s * dx, cy + s * .54), max(int(s * .04), 2))

    else:  # marcador generico
        pygame.draw.circle(surf, C_MORADO, (int(cx), int(cy)), int(s * .5))


# --------------------------------------------------------------------------
#  PERSONAJES
# --------------------------------------------------------------------------
def dibujar_lina(surf, cx, cy, s, t, animo="normal", boca=0.0):
    """Lina la Lechuza, guia del jugador. boca = cuanto abre el pico al hablar."""
    flap = math.sin(t * 5.5) if animo == "aplaude" else math.sin(t * 1.6) * 0.3
    bob = math.sin(t * 2.2) * s * 0.03
    cy += bob
    boca = clamp(boca, 0.0, 1.0)
    if boca > 0.02:                      # al hablar acompana con la cabeza
        cy += math.sin(t * 14.0) * s * 0.012

    pygame.draw.ellipse(surf, (0, 0, 0, 40),
                        (cx - s * .5, cy + s * .78, s, s * .16))
    # alas
    for lado in (-1, 1):
        ang = flap * 0.6 * lado
        px = cx + lado * s * .52
        pts = [(cx + lado * s * .30, cy - s * .10),
               (px + lado * s * .22, cy + s * .10 - abs(flap) * s * .26),
               (cx + lado * s * .34, cy + s * .44)]
        pygame.draw.polygon(surf, (168, 122, 78), pts)
    # cuerpo
    _elipse(surf, (196, 148, 96), cx, cy + s * .10, s * .48, s * .56)
    _elipse(surf, (238, 214, 172), cx, cy + s * .22, s * .32, s * .40)
    # cabeza
    _elipse(surf, (196, 148, 96), cx, cy - s * .36, s * .46, s * .40)
    for lado in (-1, 1):  # penachos
        pygame.draw.polygon(surf, (168, 122, 78), [
            (cx + lado * s * .18, cy - s * .66),
            (cx + lado * s * .40, cy - s * .90),
            (cx + lado * s * .42, cy - s * .58)])
    # ojos
    cerrado = animo == "aplaude" and math.sin(t * 5.5) > 0.7
    for lado in (-1, 1):
        ox = cx + lado * s * .18
        oy = cy - s * .38
        _elipse(surf, C_BLANCO, ox, oy, s * .17, s * .17)
        if cerrado:
            pygame.draw.arc(surf, C_TEXTO,
                            (ox - s * .14, oy - s * .10, s * .28, s * .20),
                            0.2, math.pi - 0.2, max(int(s * .04), 2))
        else:
            mir = math.sin(t * 0.9) * s * .04
            pygame.draw.circle(surf, (60, 52, 48), (int(ox + mir), int(oy)),
                               max(int(s * .08), 2))
            pygame.draw.circle(surf, C_BLANCO, (int(ox + mir - s * .03),
                                                int(oy - s * .03)),
                               max(int(s * .03), 1))
    # pico: se abre y se cierra mientras Lina habla
    ab = boca * s * .15
    if ab > s * .012:
        _elipse(surf, (122, 62, 54), cx, cy - s * .15 + ab * .45,
                s * .075, ab * .75)
    pygame.draw.polygon(surf, C_NARANJA, [
        (cx - s * .08, cy - s * .26), (cx + s * .08, cy - s * .26),
        (cx, cy - s * .12)])
    if ab > s * .012:
        pygame.draw.polygon(surf, (224, 126, 56), [
            (cx - s * .065, cy - s * .12 + ab * .35),
            (cx + s * .065, cy - s * .12 + ab * .35),
            (cx, cy - s * .10 + ab)])
    # patas
    for lado in (-1, 1):
        pygame.draw.line(surf, C_NARANJA,
                         (cx + lado * s * .16, cy + s * .60),
                         (cx + lado * s * .16, cy + s * .76), max(int(s * .06), 2))


def dibujar_burbuja_duende(surf, cx, cy, s, t):
    """Burbuja, el duende travieso que desordeno las letras."""
    bob = math.sin(t * 3.0) * s * 0.06
    cy += bob
    # gorro
    pygame.draw.polygon(surf, (126, 92, 176), [
        (cx - s * .34, cy - s * .28), (cx + s * .34, cy - s * .28),
        (cx + s * .52 + math.sin(t * 2) * s * .06, cy - s * .86)])
    pygame.draw.circle(surf, C_DORADO,
                       (int(cx + s * .52 + math.sin(t * 2) * s * .06),
                        int(cy - s * .86)), max(int(s * .08), 3))
    # cara
    _elipse(surf, (188, 226, 168), cx, cy - s * .06, s * .34, s * .32)
    for lado in (-1, 1):  # orejas puntiagudas
        pygame.draw.polygon(surf, (168, 210, 148), [
            (cx + lado * s * .30, cy - s * .16),
            (cx + lado * s * .52, cy - s * .24),
            (cx + lado * s * .30, cy + s * .04)])
    for lado in (-1, 1):
        pygame.draw.circle(surf, C_TEXTO,
                           (int(cx + lado * s * .12), int(cy - s * .10)),
                           max(int(s * .05), 2))
    pygame.draw.arc(surf, C_TEXTO,
                    (cx - s * .16, cy - s * .04, s * .32, s * .22),
                    math.pi + 0.35, math.tau - 0.35, max(int(s * .04), 2))
    # cuerpo
    _elipse(surf, (126, 92, 176), cx, cy + s * .38, s * .28, s * .32)
    for lado in (-1, 1):
        pygame.draw.line(surf, (126, 92, 176),
                         (cx + lado * s * .22, cy + s * .28),
                         (cx + lado * s * .46, cy + s * (.10 + .2 * math.sin(t * 4))),
                         max(int(s * .08), 3))


def dibujar_explorador(surf, cx, cy, s, t, caminando=False):
    paso = math.sin(t * 9) if caminando else 0.0
    bob = abs(paso) * s * .05
    cy -= bob
    # piernas
    for lado, fase in ((-1, paso), (1, -paso)):
        pygame.draw.line(surf, (78, 96, 150),
                         (cx + lado * s * .10, cy + s * .34),
                         (cx + lado * s * .10 + fase * s * .18, cy + s * .70),
                         max(int(s * .10), 3))
    # cuerpo
    pygame.draw.rect(surf, (236, 118, 96),
                     (cx - s * .22, cy - s * .06, s * .44, s * .44),
                     border_radius=int(s * .10))
    # brazos
    for lado, fase in ((-1, -paso), (1, paso)):
        pygame.draw.line(surf, (236, 118, 96),
                         (cx + lado * s * .20, cy + s * .04),
                         (cx + lado * s * .34, cy + s * (.24 + .1 * fase)),
                         max(int(s * .09), 3))
    # cabeza
    _elipse(surf, (246, 208, 170), cx, cy - s * .26, s * .22, s * .22)
    pygame.draw.circle(surf, C_TEXTO, (int(cx - s * .07), int(cy - s * .28)),
                       max(int(s * .035), 1))
    pygame.draw.circle(surf, C_TEXTO, (int(cx + s * .07), int(cy - s * .28)),
                       max(int(s * .035), 1))
    # sombrero de explorador
    pygame.draw.ellipse(surf, (150, 122, 78),
                        (cx - s * .34, cy - s * .44, s * .68, s * .14))
    pygame.draw.ellipse(surf, (168, 138, 90),
                        (cx - s * .20, cy - s * .56, s * .40, s * .22))


# ==========================================================================
#  ESCENARIO ANIMADO
# ==========================================================================
class Bosque:
    """Fondo con parallax, luciernagas y hojas cayendo."""

    def __init__(self):
        self.t = 0.0
        random.seed(7)
        self.arboles_lejos = [(random.randint(-40, ANCHO + 40),
                               random.randint(190, 260),
                               random.randint(46, 78)) for _ in range(16)]
        self.arboles_medio = [(random.randint(-60, ANCHO + 60),
                               random.randint(280, 340),
                               random.randint(70, 116)) for _ in range(12)]
        self.arbustos = [(random.randint(-30, ANCHO + 30),
                          random.randint(470, 660),
                          random.randint(30, 62)) for _ in range(18)]
        self.luces = [[random.uniform(0, ANCHO), random.uniform(180, 620),
                       random.uniform(0, math.tau), random.uniform(.4, 1.0)]
                      for _ in range(34)]
        self.hojas = [[random.uniform(0, ANCHO), random.uniform(-200, ALTO),
                       random.uniform(.5, 1.4), random.uniform(0, math.tau)]
                      for _ in range(16)]
        random.seed()
        self.cache = None

    def _fondo_estatico(self):
        surf = pygame.Surface((ANCHO, ALTO))
        for y in range(ALTO):
            p = y / ALTO
            surf.fill(mezclar(C_CIELO_ALTO, C_CIELO_BAJO, min(p * 1.5, 1)),
                      (0, y, ANCHO, 1))
        # montanas
        pygame.draw.polygon(surf, C_MONTE, [
            (-50, 300), (180, 150), (380, 300), (620, 130), (900, 300),
            (1120, 170), (ANCHO + 50, 300), (ANCHO + 50, ALTO), (-50, ALTO)])
        for x, y, r in self.arboles_lejos:
            pygame.draw.polygon(surf, C_BOSQUE_LEJOS,
                                [(x - r * .6, y), (x, y - r * 1.5), (x + r * .6, y)])
            pygame.draw.polygon(surf, C_BOSQUE_LEJOS,
                                [(x - r * .5, y - r * .6), (x, y - r * 2.0),
                                 (x + r * .5, y - r * .6)])
        for x, y, r in self.arboles_medio:
            pygame.draw.rect(surf, C_TRONCO_OSCURO,
                             (x - r * .10, y - r * .30, r * .20, r * .60))
            pygame.draw.polygon(surf, C_BOSQUE_MEDIO,
                                [(x - r * .7, y), (x, y - r * 1.7), (x + r * .7, y)])
            pygame.draw.polygon(surf, C_BOSQUE_CERCA,
                                [(x - r * .55, y - r * .7), (x, y - r * 2.2),
                                 (x + r * .55, y - r * .7)])
        # suelo
        pygame.draw.ellipse(surf, C_SUELO, (-200, 380, ANCHO + 400, 700))
        pygame.draw.ellipse(surf, C_SUELO_OSCURO, (-200, 560, ANCHO + 400, 520))
        for x, y, r in self.arbustos:
            pygame.draw.circle(surf, C_BOSQUE_MEDIO, (x, y), r)
            pygame.draw.circle(surf, C_BOSQUE_CERCA, (x - r // 3, y - r // 4), r // 2)
        return surf

    def update(self, dt):
        self.t += dt
        for l in self.luces:
            l[0] += math.sin(self.t * .7 + l[2]) * 14 * dt
            l[1] += math.cos(self.t * .5 + l[2]) * 10 * dt
        for h in self.hojas:
            h[1] += 26 * h[2] * dt
            h[0] += math.sin(self.t * 1.2 + h[3]) * 24 * dt
            h[3] += dt * 1.4
            if h[1] > ALTO + 30:
                h[1] = -30
                h[0] = random.uniform(0, ANCHO)

    def dibujar(self, surf):
        if self.cache is None:
            self.cache = self._fondo_estatico()
        surf.blit(self.cache, (0, 0))
        cap = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        for l in self.luces:
            br = (math.sin(self.t * 2.4 + l[2]) * .5 + .5) * l[3]
            r = int(3 + br * 4)
            pygame.draw.circle(cap, (255, 244, 160, int(60 + br * 130)),
                               (int(l[0]), int(l[1])), r)
            pygame.draw.circle(cap, (255, 252, 210, int(30 + br * 60)),
                               (int(l[0]), int(l[1])), r * 2)
        for h in self.hojas:
            s = pygame.Surface((16, 10), pygame.SRCALPHA)
            pygame.draw.ellipse(s, (188, 214, 128, 170), (0, 0, 16, 10))
            s = pygame.transform.rotate(s, math.degrees(h[3]))
            cap.blit(s, (h[0], h[1]))
        surf.blit(cap, (0, 0))


# ==========================================================================
#  WIDGETS
# ==========================================================================
class Boton:
    def __init__(self, rect, etiqueta, color=C_DORADO, icono=None, fuente=None):
        self.rect = pygame.Rect(rect)
        self.etiqueta = etiqueta
        self.color = color
        self.icono = icono
        self.fuente = fuente
        self.hover = False
        self.presion = 0.0
        self.pulso = random.uniform(0, math.tau)
        self.habilitado = True

    def update(self, dt, pos):
        self.hover = self.habilitado and self.rect.collidepoint(pos)
        obj = 1.0 if self.hover else 0.0
        self.presion += (obj - self.presion) * min(dt * 12, 1)
        self.pulso += dt * 2

    def dibujar(self, surf, fuentes):
        f = self.fuente or fuentes.h2
        crec = int(self.presion * 6)
        r = self.rect.inflate(crec, crec)
        col = self.color if self.habilitado else (190, 190, 190)
        sombra = pygame.Surface((r.w + 10, r.h + 14), pygame.SRCALPHA)
        pygame.draw.rect(sombra, (0, 0, 0, 55), (5, 10, r.w, r.h),
                         border_radius=22)
        surf.blit(sombra, (r.x - 5, r.y - 5))
        pygame.draw.rect(surf, mezclar(col, (0, 0, 0), .22), r, border_radius=22)
        pygame.draw.rect(surf, col, (r.x, r.y, r.w, r.h - 7), border_radius=22)
        pygame.draw.rect(surf, mezclar(col, C_BLANCO, .45),
                         (r.x + 8, r.y + 6, r.w - 16, r.h * .35), border_radius=16)
        texto(surf, f, self.etiqueta, r.centerx, r.centery - 3, C_TEXTO)

    def click(self, pos):
        return self.habilitado and self.rect.collidepoint(pos)


class Tarjeta:
    """Tarjeta con la ilustracion de la palabra objetivo."""

    def __init__(self, cx, cy, w, h):
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (cx, cy)
        self.icono = ""
        self.entrada = Tween(0, 1, .55, ease_out_back)

    def poner(self, icono):
        self.icono = icono
        self.entrada = Tween(0, 1, .55, ease_out_back)

    def update(self, dt):
        self.entrada.update(dt)

    def dibujar(self, surf, t):
        e = self.entrada.valor
        w, h = int(self.rect.w * e), int(self.rect.h * e)
        if w < 4 or h < 4:
            return
        r = pygame.Rect(0, 0, w, h)
        r.center = self.rect.center
        sombra = pygame.Surface((r.w + 16, r.h + 20), pygame.SRCALPHA)
        pygame.draw.rect(sombra, (0, 0, 0, 60), (8, 14, r.w, r.h), border_radius=24)
        surf.blit(sombra, (r.x - 8, r.y - 8))
        pygame.draw.rect(surf, C_CREMA, r, border_radius=24)
        pygame.draw.rect(surf, C_DORADO, r, 5, border_radius=24)
        if self.icono and e > .5:
            dibujar_icono(surf, self.icono, r.centerx, r.centery,
                          min(r.w, r.h) * .34, t)


# ==========================================================================
#  CONTENIDO PEDAGOGICO
# ==========================================================================
# --------------------------------------------------------------------------
#  NIVEL 1: (palabra, icono, vocal inicial)
#  Hay varias imagenes por vocal; cada partida sortea una distinta.
# --------------------------------------------------------------------------
NIVEL1_ITEMS = [
    ("AVION", "avion", "A"),
    ("ARANA", "arana", "A"),
    ("ABEJA", "abeja", "A"),
    ("ARBOL", "arbol", "A"),
    ("ANILLO", "anillo", "A"),
    ("ELEFANTE", "elefante", "E"),
    ("ESTRELLA", "estrella", "E"),
    ("ERIZO", "erizo", "E"),
    ("ESCOBA", "escoba", "E"),
    ("IGLU", "iglu", "I"),
    ("IMAN", "iman", "I"),
    ("ISLA", "isla", "I"),
    ("IGUANA", "iguana", "I"),
    ("OSO", "oso", "O"),
    ("OJO", "ojo", "O"),
    ("OVEJA", "oveja", "O"),
    ("OLA", "ola", "O"),
    ("ORUGA", "oruga", "O"),
    ("UVAS", "uvas", "U"),
    ("UNO", "uno", "U"),
    ("UNICORNIO", "unicornio", "U"),
]


def sortear_nivel1(cantidad):
    """Sortea palabras cubriendo primero las cinco vocales, sin repetir."""
    por_vocal = {v: [it for it in NIVEL1_ITEMS if it[2] == v] for v in VOCALES}
    orden = VOCALES[:]
    random.shuffle(orden)
    elegidos, usados = [], set()
    for v in orden:
        if len(elegidos) >= cantidad:
            break
        opciones = [it for it in por_vocal[v] if it[0] not in usados]
        if opciones:
            it = random.choice(opciones)
            elegidos.append(it)
            usados.add(it[0])
    resto = [it for it in NIVEL1_ITEMS if it[0] not in usados]
    random.shuffle(resto)
    while len(elegidos) < cantidad and resto:
        elegidos.append(resto.pop())
    random.shuffle(elegidos)
    return elegidos


# --------------------------------------------------------------------------
#  NIVELES 2 y 3: (palabra, icono, silabas)
#  Solo silabas directas con m, p, s, l, n, t, d (metodo silabico-fonetico).
# --------------------------------------------------------------------------
PALABRAS_2_SILABAS = [
    ("OSO", "oso", ["O", "SO"]),
    ("OLA", "ola", ["O", "LA"]),
    ("MAPA", "mapa", ["MA", "PA"]),
    ("MESA", "mesa", ["ME", "SA"]),
    ("LUNA", "luna", ["LU", "NA"]),
    ("LUPA", "lupa", ["LU", "PA"]),
    ("PATO", "pato", ["PA", "TO"]),
    ("PALA", "pala", ["PA", "LA"]),
    ("PUMA", "puma", ["PU", "MA"]),
    ("SAPO", "sapo", ["SA", "PO"]),
    ("SOPA", "sopa", ["SO", "PA"]),
    ("PINO", "pino", ["PI", "NO"]),
    ("MONO", "mono", ["MO", "NO"]),
    ("MANO", "mano", ["MA", "NO"]),
    ("MOTO", "moto", ["MO", "TO"]),
    ("DADO", "dado", ["DA", "DO"]),
    ("NIDO", "nido", ["NI", "DO"]),
    ("LATA", "lata", ["LA", "TA"]),
]

PALABRAS_3_SILABAS = [
    ("PELOTA", "pelota", ["PE", "LO", "TA"]),
    ("MALETA", "maleta", ["MA", "LE", "TA"]),
    ("TOMATE", "tomate", ["TO", "MA", "TE"]),
    ("PALOMA", "paloma", ["PA", "LO", "MA"]),
]

# Palabras de ampliacion: usan z y r, fuera del grupo inicial de consonantes.
# Si quieres usarlas, agregalas a PALABRAS_2_SILABAS.
PALABRAS_OPCIONALES = [
    ("TAZA", "taza", ["TA", "ZA"]),
    ("LORO", "loro", ["LO", "RO"]),
]

BANCO_SILABAS = [c + v for c in "MPSLTND" for v in "AEIOU"]


def distractores_silaba(objetivo, cantidad, evitar=()):
    """Distractores con criterio fonologico: misma consonante o misma vocal."""
    evitar = set(evitar) | {objetivo}
    if len(objetivo) == 1:                      # silaba formada por una vocal
        pool = [v for v in VOCALES if v not in evitar]
        random.shuffle(pool)
        return pool[:cantidad]
    con, voc = objetivo[:-1], objetivo[-1]
    misma_con = [s for s in BANCO_SILABAS if s[:-1] == con and s not in evitar]
    misma_voc = [s for s in BANCO_SILABAS if s[-1] == voc and s not in evitar]
    otros = [s for s in BANCO_SILABAS if s not in evitar]
    for grupo in (misma_con, misma_voc, otros):
        random.shuffle(grupo)
    elegidos = []
    for grupo in (misma_con, misma_voc, otros):
        for s in grupo:
            if len(elegidos) >= cantidad:
                break
            if s not in elegidos:
                elegidos.append(s)
    return elegidos[:cantidad]

FONEMAS = {
    "A": "aaa", "E": "eee", "I": "iii", "O": "ooo", "U": "uuu",
    "M": "mmm", "P": "p", "S": "sss", "L": "lll",
}

ELOGIOS = [
    "Excelente trabajo, encontraste el sonido correcto.",
    "Muy bien, el bosque recupera su voz.",
    "Lo lograste, sigue asi pequeno explorador.",
    "Perfecto, ese es el sonido que buscabamos.",
]


def pista_error(objetivo):
    son = FONEMAS.get(objetivo[0], objetivo)
    return f"Casi lo logras. Escucha bien como suena: {son}. Intentalo otra vez."


# ==========================================================================
#  ESCENAS
# ==========================================================================
class Escena:
    def __init__(self, juego):
        self.juego = juego
        self.t = 0.0

    def entrar(self):
        pass

    def evento(self, ev):
        pass

    def update(self, dt):
        self.t += dt

    def dibujar(self, surf):
        pass


# ------------------------------------------------------------------ PORTADA
class EscenaPortada(Escena):
    def entrar(self):
        j = self.juego
        cx = ANCHO // 2
        self.botones = [
            Boton((cx - 180, 380, 360, 82), "Jugar", C_DORADO),
            Boton((cx - 180, 478, 360, 70), "Mi cuaderno", C_ROSA,
                  fuente=j.fuentes.cuerpo),
            Boton((cx - 180, 562, 360, 60), "Salir", (214, 210, 200),
                  fuente=j.fuentes.cuerpo),
        ]
        j.voz.decir(
            "Bienvenido al Bosque de las Palabras Magicas. Soy Lina la Lechuza "
            "y sere tu guia.", 6.0)

    def evento(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.botones[0].click(ev.pos):
                self.juego.fx.tocar("click")
                self.juego.ir_a(EscenaMapa(self.juego))
            elif self.botones[1].click(ev.pos):
                self.juego.fx.tocar("click")
                self.juego.ir_a(EscenaAlbum(self.juego))
            elif self.botones[2].click(ev.pos):
                self.juego.salir()

    def update(self, dt):
        super().update(dt)
        pos = pygame.mouse.get_pos()
        for b in self.botones:
            b.update(dt, pos)
        if random.random() < dt * 2.2:
            self.juego.particulas.brillos(
                random.uniform(200, ANCHO - 200), random.uniform(120, 260), 2)

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        y = 150 + math.sin(self.t * 1.4) * 8
        panel = pygame.Surface((820, 190), pygame.SRCALPHA)
        pygame.draw.rect(panel, (255, 255, 255, 130), (0, 0, 820, 190),
                         border_radius=40)
        surf.blit(panel, (ANCHO // 2 - 410, y - 95))
        texto(surf, j.fuentes.titulo, "El Bosque de las", ANCHO // 2, y - 36,
              (46, 92, 66), sombra=True)
        texto(surf, j.fuentes.titulo, "Palabras Magicas", ANCHO // 2, y + 38,
              (46, 92, 66), sombra=True)
        texto(surf, j.fuentes.chico,
              "Conciencia fonologica e iniciacion a la lectoescritura  -  Grado 1o",
              ANCHO // 2, y + 92, C_TEXTO_SUAVE)
        dibujar_lina(surf, 250, 470, 150, self.t, boca=j.voz.boca)
        dibujar_burbuja_duende(surf, ANCHO - 230, 450, 120, self.t)
        for b in self.botones:
            b.dibujar(surf, j.fuentes)
        texto(surf, j.fuentes.mini,
              "Voz en off: " + ("activa" if j.voz.activa else "subtitulos") +
              "   |   ESPACIO repite la instruccion   |   F11 pantalla completa",
              ANCHO // 2, ALTO - 28, C_TEXTO_SUAVE)


# --------------------------------------------------------------- MAPA/SENDEROS
class EscenaMapa(Escena):
    def entrar(self):
        j = self.juego
        self.nodos = [
            (270, 430, 1, "El Rio de las Vocales", "Sonidos iniciales A E I O U"),
            (640, 350, 2, "El Puente Silabico", "Une consonante + vocal"),
            (1010, 430, 3, "El Gran Arbol", "Forma palabras completas"),
        ]
        self.volver = Boton((30, 30, 150, 54), "Volver", (214, 210, 200),
                            fuente=j.fuentes.chico)
        j.voz.decir("Elige un sendero magico para continuar.", 3.0)

    def _desbloqueado(self, n):
        return n <= self.juego.progreso["nivel_max"]

    def evento(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.volver.click(ev.pos):
                self.juego.ir_a(EscenaPortada(self.juego))
                return
            for x, y, n, nom, _ in self.nodos:
                if math.hypot(ev.pos[0] - x, ev.pos[1] - y) < 62:
                    if self._desbloqueado(n):
                        self.juego.fx.tocar("click")
                        self.juego.ir_a(EscenaIntroNivel(self.juego, n))
                    else:
                        self.juego.voz.decir(
                            "Primero completa el sendero anterior.", 2.5)
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.juego.ir_a(EscenaPortada(self.juego))

    def update(self, dt):
        super().update(dt)
        self.volver.update(dt, pygame.mouse.get_pos())

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        texto(surf, j.fuentes.h1, "Senderos magicos", ANCHO // 2, 90,
              (46, 92, 66), sombra=True)
        pts = [(n[0], n[1]) for n in self.nodos]
        for i in range(len(pts) - 1):
            pygame.draw.line(surf, (236, 224, 186), pts[i], pts[i + 1], 12)
            pygame.draw.line(surf, (206, 188, 148), pts[i], pts[i + 1], 4)
        mx, my = pygame.mouse.get_pos()
        for x, y, n, nom, sub in self.nodos:
            abierto = self._desbloqueado(n)
            hov = math.hypot(mx - x, my - y) < 62
            r = 54 + (6 if hov and abierto else 0) + math.sin(self.t * 2 + n) * 3
            pygame.draw.circle(surf, (0, 0, 0, 40), (int(x), int(y + 8)), int(r))
            col = C_DORADO if abierto else (178, 178, 172)
            pygame.draw.circle(surf, mezclar(col, (0, 0, 0), .2), (x, y), int(r))
            pygame.draw.circle(surf, col, (x, y - 4), int(r))
            texto(surf, j.fuentes.h1, str(n), x, y - 6, C_TEXTO)
            texto(surf, j.fuentes.cuerpo, nom, x, y + 86, C_TEXTO, sombra=True)
            texto(surf, j.fuentes.mini, sub if abierto else "Bloqueado",
                  x, y + 114, C_TEXTO_SUAVE)
            est = j.progreso["estrellas"].get(str(n), 0)
            for i in range(3):
                col_e = C_DORADO if i < est else (255, 255, 255, 120)
                dibujar_estrella(surf, x - 32 + i * 32, y + 146, 13, 6,
                                 C_DORADO if i < est else (206, 206, 200))
        dibujar_lina(surf, 130, ALTO - 140, 110, self.t, boca=j.voz.boca)
        self.volver.dibujar(surf, j.fuentes)


# ------------------------------------------------------------ INTRO DE NIVEL
class EscenaIntroNivel(Escena):
    """Clip breve: Burbuja el duende esconde las letras."""

    TEXTOS = {
        1: "Burbuja solto las vocales al rio. Revienta la burbuja que tenga "
           "la vocal con la que empieza el dibujo.",
        2: "El puente perdio una tabla. Arrastra la silaba que falta para "
           "completar el nombre del animal.",
        3: "El cofre del gran arbol pide palabras completas. Ordena las "
           "silabas para escribirlas.",
    }

    def __init__(self, juego, nivel):
        super().__init__(juego)
        self.nivel = nivel
        self.saliendo = False

    def entrar(self):
        self.juego.voz.decir(self.TEXTOS[self.nivel], 7.0)
        self.dur = 7.5              # deja que Lina termine de explicar
        self.saliendo = False

    def evento(self, ev):
        if ev.type in (pygame.MOUSEBUTTONDOWN, pygame.KEYDOWN):
            self._continuar()

    def _continuar(self):
        if self.saliendo:           # una sola vez: si no, la transicion
            return                  # se reiniciaba en cada fotograma
        self.saliendo = True
        clases = {1: EscenaNivel1, 2: EscenaNivel2, 3: EscenaNivel3}
        self.juego.ir_a(clases[self.nivel](self.juego))

    def update(self, dt):
        super().update(dt)
        if self.t > self.dur:
            self._continuar()
        if random.random() < dt * 8:
            self.juego.particulas.brillos(
                ANCHO * .62 + random.uniform(-80, 80),
                300 + random.uniform(-60, 60), 1)

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((20, 30, 40, 120))
        surf.blit(velo, (0, 0))
        dibujar_burbuja_duende(surf, ANCHO * .62, 300, 180, self.t)
        # letras robadas volando
        for i, L in enumerate("MAPESOLU"):
            ang = self.t * 1.6 + i * .8
            x = ANCHO * .62 + math.cos(ang) * (140 + i * 12)
            y = 300 + math.sin(ang) * (70 + i * 6)
            img = j.fuentes.silaba.render(L, True, C_CREMA)
            img.set_alpha(200)
            surf.blit(img, img.get_rect(center=(x, y)))
        panel = pygame.Surface((940, 170), pygame.SRCALPHA)
        pygame.draw.rect(panel, (255, 255, 255, 240), (0, 0, 940, 170),
                         border_radius=30)
        surf.blit(panel, (ANCHO // 2 - 470, ALTO - 250))
        texto_envuelto(surf, j.fuentes.cuerpo, self.TEXTOS[self.nivel],
                       ANCHO // 2 + 60, ALTO - 170, 700)
        dibujar_lina(surf, ANCHO // 2 - 380, ALTO - 168, 110, self.t,
                     boca=j.voz.boca)
        texto(surf, j.fuentes.mini, "Toca la pantalla para comenzar",
              ANCHO // 2, ALTO - 42, C_CREMA)


# --------------------------------------------------------------- BASE NIVEL
class EscenaNivelBase(Escena):
    TOTAL_RONDAS = 5
    NUM = 1
    NOMBRE = ""

    def __init__(self, juego):
        super().__init__(juego)
        self.ronda = 0
        self.aciertos = 0
        self.errores = 0
        self.bloqueo = 0.0
        self.mensaje = ""
        self.mensaje_t = 0.0
        self.animo_lina = "normal"
        self.estrellas_vol = []

    def entrar(self):
        j = self.juego
        self.btn_volver = Boton((26, 24, 130, 50), "Salir", (214, 210, 200),
                                fuente=j.fuentes.chico)
        self.btn_repite = Boton((ANCHO - 226, 24, 200, 50), "Repetir audio",
                                C_AGUA_CLARA, fuente=j.fuentes.chico)
        self.nueva_ronda()

    def nueva_ronda(self):
        raise NotImplementedError

    def instruccion(self):
        return ""

    def acierto(self, x, y):
        j = self.juego
        self.aciertos += 1
        j.fx.tocar("acierto")
        j.particulas.confeti(x, y, 34)
        self.animo_lina = "aplaude"
        self.mensaje = random.choice(ELOGIOS)
        self.mensaje_t = 2.4
        j.voz.decir(self.mensaje, 2.4)
        self.estrellas_vol.append({"x": x, "y": y, "t": 0.0})
        self.bloqueo = 1.5

    def error(self, objetivo):
        j = self.juego
        self.errores += 1
        j.fx.tocar("suave")
        self.mensaje = pista_error(objetivo)
        self.mensaje_t = 3.0
        j.voz.decir(self.mensaje, 3.0)

    def avanzar(self):
        self.ronda += 1
        self.animo_lina = "normal"
        if self.ronda >= self.TOTAL_RONDAS:
            est = 3 if self.errores == 0 else (2 if self.errores <= 2 else 1)
            self.juego.ir_a(EscenaFinNivel(self.juego, self.NUM, est,
                                           self.aciertos, self.errores))
        else:
            self.nueva_ronda()

    def evento(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if self.btn_volver.click(ev.pos):
                self.juego.ir_a(EscenaMapa(self.juego))
            elif self.btn_repite.click(ev.pos):
                self.juego.voz.decir(self.instruccion(), 4.0)
        if ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                self.juego.ir_a(EscenaMapa(self.juego))
            elif ev.key == pygame.K_SPACE:
                self.juego.voz.decir(self.instruccion(), 4.0)

    def update(self, dt):
        super().update(dt)
        pos = pygame.mouse.get_pos()
        self.btn_volver.update(dt, pos)
        self.btn_repite.update(dt, pos)
        if self.mensaje_t > 0:
            self.mensaje_t -= dt
        if self.bloqueo > 0:
            self.bloqueo -= dt
            if self.bloqueo <= 0:
                self.avanzar()
        for e in self.estrellas_vol:
            e["t"] += dt * 1.6
        self.estrellas_vol = [e for e in self.estrellas_vol if e["t"] < 1]

    def dibujar_hud(self, surf):
        j = self.juego
        barra = pygame.Surface((ANCHO, 96), pygame.SRCALPHA)
        pygame.draw.rect(barra, (255, 255, 255, 170), (0, 0, ANCHO, 96))
        surf.blit(barra, (0, 0))
        texto(surf, j.fuentes.h2, self.NOMBRE, ANCHO // 2, 34, (46, 92, 66))
        # progreso
        x0, y0, w = ANCHO // 2 - 150, 66, 300
        pygame.draw.rect(surf, (222, 222, 214), (x0, y0, w, 14), border_radius=7)
        p = self.ronda / self.TOTAL_RONDAS
        pygame.draw.rect(surf, C_VERDE_OK, (x0, y0, int(w * p), 14),
                         border_radius=7)
        texto(surf, j.fuentes.mini, f"{self.ronda}/{self.TOTAL_RONDAS}",
              x0 + w + 34, y0 + 7, C_TEXTO_SUAVE)
        self.btn_volver.dibujar(surf, j.fuentes)
        self.btn_repite.dibujar(surf, j.fuentes)
        # estrellas ganadas volando al marcador
        destino = (ANCHO - 70, 130)
        for e in self.estrellas_vol:
            p = ease_in_out(e["t"])
            x = lerp(e["x"], destino[0], p)
            y = lerp(e["y"], destino[1], p) - math.sin(p * math.pi) * 90
            dibujar_estrella(surf, x, y, 20 * (1 - p * .4), 9, C_DORADO, self.t * 4)
        dibujar_estrella(surf, destino[0], destino[1], 22, 10, C_DORADO_OSC)
        texto(surf, j.fuentes.cuerpo, str(self.aciertos), destino[0], destino[1] + 40,
              C_TEXTO, sombra=True)

    def dibujar_guia(self, surf, x=118, y=None):
        j = self.juego
        y = y or ALTO - 120
        dibujar_lina(surf, x, y, 118, self.t, self.animo_lina, j.voz.boca)
        if self.mensaje_t > 0:
            a = clamp(self.mensaje_t, 0, 1)
            globo = pygame.Surface((640, 104), pygame.SRCALPHA)
            pygame.draw.rect(globo, (255, 255, 255, int(240 * a)),
                             (0, 0, 640, 104), border_radius=26)
            surf.blit(globo, (x + 78, y - 96))
            texto_envuelto(surf, j.fuentes.chico, self.mensaje,
                           x + 398, y - 44, 590)


# ----------------------------------------------------- NIVEL 1: RIO VOCALES
class Burbujita:
    """Burbuja con una vocal. Sube desde el rio y se queda flotando dentro de
    la pantalla: nunca se va, para que el nino pueda pensar sin apuro."""

    ALTURA_BASE = 452          # linea donde se quedan flotando

    def __init__(self, letra, x, y, r, vel):
        self.letra, self.x, self.r, self.vel = letra, x, r, vel
        self.base_x, self.base_y = x, y
        self.y = ALTO + 120                 # entra desde abajo
        self.fase = random.uniform(0, math.tau)
        self.entrada = Tween(0, 1, 0.75, ease_out_back,
                             retardo=random.uniform(0, 0.35))
        self.viva = True
        self.sacudida = 0.0
        self.t = 0.0

    def update(self, dt):
        self.t += dt
        self.entrada.update(dt)
        e = self.entrada.valor
        flote = math.sin(self.t * 1.3 + self.fase) * 12
        self.y = lerp(ALTO + 120, self.base_y, e) + flote * e
        self.x = self.base_x + math.sin(self.t * .9 + self.fase) * 14
        if self.sacudida > 0:
            self.sacudida -= dt

    def dibujar(self, surf, fuentes, t):
        ox = math.sin(t * 30) * 7 if self.sacudida > 0 else 0
        x, y, r = int(self.x + ox), int(self.y), int(self.r)
        cap = pygame.Surface((r * 2 + 8, r * 2 + 8), pygame.SRCALPHA)
        pygame.draw.circle(cap, (170, 226, 246, 190), (r + 4, r + 4), r)
        pygame.draw.circle(cap, (255, 255, 255, 210), (r + 4, r + 4), r, 4)
        pygame.draw.circle(cap, (255, 255, 255, 160),
                           (int(r * .62), int(r * .58)), max(int(r * .20), 3))
        surf.blit(cap, (x - r - 4, y - r - 4))
        texto(surf, fuentes.letra, self.letra, x, y, (36, 76, 104))

    def contiene(self, pos):
        return math.hypot(pos[0] - self.x, pos[1] - self.y) <= self.r


class EscenaNivel1(EscenaNivelBase):
    NUM, NOMBRE = 1, "Nivel 1 - El Rio de las Vocales"
    TOTAL_RONDAS = 5

    def entrar(self):
        self.tarjeta = Tarjeta(ANCHO // 2, 250, 250, 250)
        self.burbujas = []
        self.pool = sortear_nivel1(self.TOTAL_RONDAS)
        super().entrar()

    def nueva_ronda(self):
        self.palabra, self.icono, self.objetivo = self.pool[self.ronda]
        self.tarjeta.poner(self.icono)
        self.burbujas = []
        self.juego.fx.tocar("agua")
        distractores = [v for v in VOCALES if v != self.objetivo]
        letras = [self.objetivo] + random.sample(distractores, 3)
        random.shuffle(letras)
        # fila fija a la derecha de Lina, siempre visible y alcanzable
        x_ini, x_fin = 310, ANCHO - 120
        sep = (x_fin - x_ini) / max(len(letras) - 1, 1)
        for i, L in enumerate(letras):
            self.burbujas.append(
                Burbujita(L, x_ini + i * sep,
                          Burbujita.ALTURA_BASE + (i % 2) * 48, 62, 0))
        self.juego.voz.decir(self.instruccion(), 4.0)

    def instruccion(self):
        return f"Con que vocal empieza {self.palabra}. Revienta esa burbuja."

    def evento(self, ev):
        super().evento(ev)
        if self.bloqueo > 0:
            return
        elegido = None
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in self.burbujas:
                if b.viva and b.contiene(ev.pos):
                    elegido = b
                    break
        if ev.type == pygame.KEYDOWN and pygame.K_1 <= ev.key <= pygame.K_5:
            idx = ev.key - pygame.K_1
            vivas = [b for b in self.burbujas if b.viva]
            if idx < len(vivas):
                elegido = vivas[idx]
        if (ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1
                and elegido is None and self.tarjeta.rect.collidepoint(ev.pos)):
            # tocar la tarjeta vuelve a decir la palabra y su vocal
            self.juego.voz.decir(self.palabra, 1.6)
            self.juego.fx.tocar_vocal(self.objetivo)
            return
        if elegido:
            if elegido.letra == self.objetivo:
                elegido.viva = False
                self.juego.fx.tocar("pop")
                self.juego.fx.tocar_vocal(self.objetivo)
                self.juego.particulas.estallido(elegido.x, elegido.y,
                                                C_AGUA_CLARA, 30, 340)
                self.acierto(elegido.x, elegido.y)
            else:
                elegido.sacudida = .45
                self.juego.fx.tocar("burbuja")
                self.error(self.objetivo)

    def update(self, dt):
        super().update(dt)
        self.tarjeta.update(dt)
        for b in self.burbujas:
            b.update(dt)

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        # rio
        rio = pygame.Surface((ANCHO, 240), pygame.SRCALPHA)
        pygame.draw.ellipse(rio, C_AGUA + (210,), (-120, 40, ANCHO + 240, 210))
        for i in range(9):
            y = 90 + i * 16
            off = math.sin(self.t * 1.4 + i) * 26
            pygame.draw.arc(rio, C_AGUA_CLARA + (150,),
                            (-120 + off, y, ANCHO + 240, 60), .2, math.pi - .2, 3)
        surf.blit(rio, (0, ALTO - 240))
        self.tarjeta.dibujar(surf, self.t)
        texto(surf, j.fuentes.cuerpo, "Con que vocal empieza?",
              ANCHO // 2, 396, C_TEXTO, sombra=True)
        self.dibujar_hud(surf)
        self.dibujar_guia(surf)
        for b in self.burbujas:          # siempre encima del globo de Lina
            if b.viva:
                b.dibujar(surf, j.fuentes, self.t)


# --------------------------------------------------- NIVEL 2: PUENTE SILABICO
class Piedra:
    def __init__(self, silaba, x, y, w=132, h=92):
        self.silaba = silaba
        self.rect = pygame.Rect(0, 0, w, h)
        self.rect.center = (x, y)
        self.origen = (x, y)
        self.arrastrando = False
        self.off = (0, 0)
        self.sacudida = 0.0
        self.colocada = False

    def dibujar(self, surf, fuentes, t):
        r = self.rect.copy()
        if self.sacudida > 0:
            r.x += int(math.sin(t * 34) * 8)
        alto = 10 if self.arrastrando else 5
        sombra = pygame.Surface((r.w + 18, r.h + 22), pygame.SRCALPHA)
        pygame.draw.ellipse(sombra, (0, 0, 0, 70),
                            (9, r.h - 2 + alto, r.w, 20))
        surf.blit(sombra, (r.x - 9, r.y))
        pygame.draw.rect(surf, C_PIEDRA_BORDE, r, border_radius=20)
        pygame.draw.rect(surf, C_PIEDRA, (r.x, r.y, r.w, r.h - 7),
                         border_radius=20)
        pygame.draw.rect(surf, (240, 238, 232),
                         (r.x + 10, r.y + 8, r.w - 20, r.h * .32),
                         border_radius=14)
        texto(surf, fuentes.silaba, self.silaba, r.centerx, r.centery - 4,
              (72, 64, 58))


class EscenaNivel2(EscenaNivelBase):
    NUM, NOMBRE = 2, "Nivel 2 - El Puente Silabico"
    TOTAL_RONDAS = 4

    def entrar(self):
        self.tarjeta = Tarjeta(ANCHO // 2, 210, 210, 210)
        self.pool = random.sample(PALABRAS_2_SILABAS,
                                  min(self.TOTAL_RONDAS, len(PALABRAS_2_SILABAS)))
        self.piedras = []
        self.caminata = 0.0
        super().entrar()

    def nueva_ronda(self):
        self.palabra, self.icono, self.silabas = self.pool[self.ronda]
        # la silaba que falta tambien cambia en cada partida
        self.falta = random.randrange(len(self.silabas))
        self.objetivo = self.silabas[self.falta]
        self.tarjeta.poner(self.icono)
        self.caminata = 0.0
        # ranuras del puente
        n = len(self.silabas)
        ancho_t, sep = 150, 28
        total = n * ancho_t + (n - 1) * sep
        x0 = ANCHO // 2 - total // 2
        self.slots = []
        for i in range(n):
            r = pygame.Rect(x0 + i * (ancho_t + sep), 400, ancho_t, 100)
            self.slots.append({"rect": r, "silaba": self.silabas[i],
                               "vacio": i == self.falta})
        # opciones: la correcta y dos distractores parecidos
        ops = [self.objetivo] + distractores_silaba(self.objetivo, 2,
                                                    evitar=self.silabas)
        random.shuffle(ops)
        self.piedras = [Piedra(s, ANCHO // 2 - 220 + i * 220, 600)
                        for i, s in enumerate(ops)]
        self.juego.fx.tocar("hoja")
        self.juego.voz.decir(self.instruccion(), 4.5)

    def instruccion(self):
        return (f"Completa el nombre. Arrastra la silaba que falta para formar "
                f"{self.palabra}.")

    def evento(self, ev):
        super().evento(ev)
        if self.bloqueo > 0:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for p in reversed(self.piedras):
                if p.rect.collidepoint(ev.pos) and not p.colocada:
                    p.arrastrando = True
                    p.off = (p.rect.centerx - ev.pos[0], p.rect.centery - ev.pos[1])
                    self.piedras.remove(p)
                    self.piedras.append(p)
                    self.juego.fx.tocar("click")
                    break
        elif ev.type == pygame.MOUSEMOTION:
            for p in self.piedras:
                if p.arrastrando:
                    p.rect.center = (ev.pos[0] + p.off[0], ev.pos[1] + p.off[1])
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            for p in self.piedras:
                if not p.arrastrando:
                    continue
                p.arrastrando = False
                hueco = self.slots[self.falta]
                if hueco["rect"].inflate(70, 70).collidepoint(p.rect.center):
                    if p.silaba == self.objetivo:
                        p.colocada = True
                        p.rect.center = hueco["rect"].center
                        hueco["vacio"] = False
                        self.juego.fx.tocar("madera")
                        self.juego.fx.tocar_silaba(p.silaba)
                        self.acierto(*hueco["rect"].center)
                        self.bloqueo = 2.3
                    else:
                        p.sacudida = .5
                        p.rect.center = p.origen
                        self.juego.fx.tocar("madera")
                        self.error(self.objetivo)
                else:
                    p.rect.center = p.origen

    def update(self, dt):
        super().update(dt)
        self.tarjeta.update(dt)
        for p in self.piedras:
            if p.sacudida > 0:
                p.sacudida -= dt
        if self.bloqueo > 0 and not self.slots[self.falta]["vacio"]:
            self.caminata = min(self.caminata + dt * .55, 1.0)

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        # barranco y agua
        pygame.draw.rect(surf, (58, 92, 76), (0, 500, ANCHO, ALTO - 500))
        agua = pygame.Surface((ANCHO, 120), pygame.SRCALPHA)
        pygame.draw.rect(agua, C_AGUA + (200,), (0, 0, ANCHO, 120))
        for i in range(6):
            pygame.draw.arc(agua, C_AGUA_CLARA + (140,),
                            (-100 + math.sin(self.t + i) * 40, 10 + i * 16,
                             ANCHO + 200, 50), .2, math.pi - .2, 3)
        surf.blit(agua, (0, ALTO - 120))
        # cuerdas del puente
        izq, der = self.slots[0]["rect"], self.slots[-1]["rect"]
        for dy in (-58, 62):
            pygame.draw.line(surf, C_MADERA_OSC,
                             (izq.left - 130, izq.centery + dy),
                             (der.right + 130, der.centery + dy), 7)
        self.tarjeta.dibujar(surf, self.t)
        # tablones / ranuras
        for s in self.slots:
            r = s["rect"]
            if s["vacio"]:
                hueco = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
                pygame.draw.rect(hueco, (255, 255, 255, 90), (0, 0, r.w, r.h),
                                 border_radius=18)
                pygame.draw.rect(hueco, (255, 255, 255, 200), (0, 0, r.w, r.h),
                                 4, border_radius=18)
                surf.blit(hueco, r.topleft)
                texto(surf, j.fuentes.h1, "?", r.centerx, r.centery, (255, 255, 255))
            else:
                pygame.draw.rect(surf, C_MADERA_OSC, r, border_radius=16)
                pygame.draw.rect(surf, C_MADERA, (r.x, r.y, r.w, r.h - 7),
                                 border_radius=16)
                texto(surf, j.fuentes.silaba, s["silaba"], r.centerx,
                      r.centery - 4, (250, 244, 232))
        # explorador cruzando
        x = lerp(izq.left - 150, der.right + 120, ease_in_out(self.caminata))
        dibujar_explorador(surf, x, 360, 92, self.t, self.caminata > 0)
        for p in self.piedras:
            if not p.colocada:
                p.dibujar(surf, j.fuentes, self.t)
        self.dibujar_hud(surf)
        self.dibujar_guia(surf, 118, ALTO - 110)


# ------------------------------------------------- NIVEL 3: GRAN ARBOL
class Bloque:
    def __init__(self, silaba, x, y):
        self.silaba = silaba
        self.rect = pygame.Rect(0, 0, 140, 100)
        self.rect.center = (x, y)
        self.origen = (x, y)
        self.arrastrando = False
        self.off = (0, 0)
        self.colocado = False
        self.sacudida = 0.0
        self.giro = random.uniform(-.06, .06)

    def dibujar(self, surf, fuentes, t):
        r = self.rect.copy()
        if self.sacudida > 0:
            r.x += int(math.sin(t * 34) * 8)
        cap = pygame.Surface((r.w + 16, r.h + 24), pygame.SRCALPHA)
        pygame.draw.rect(cap, (0, 0, 0, 60), (8, 18, r.w, r.h), border_radius=18)
        pygame.draw.rect(cap, C_MADERA_OSC, (8, 8, r.w, r.h), border_radius=18)
        pygame.draw.rect(cap, (206, 158, 104), (8, 8, r.w, r.h - 8),
                         border_radius=18)
        pygame.draw.rect(cap, (226, 184, 132), (18, 16, r.w - 20, r.h * .34),
                         border_radius=12)
        img = fuentes.silaba.render(self.silaba, True, (86, 56, 34))
        cap.blit(img, img.get_rect(center=(8 + r.w // 2, 8 + r.h // 2 - 4)))
        if not self.arrastrando:
            cap = pygame.transform.rotate(cap, math.degrees(self.giro))
        surf.blit(cap, cap.get_rect(center=r.center))


class EscenaNivel3(EscenaNivelBase):
    NUM, NOMBRE = 3, "Nivel 3 - El Gran Arbol de las Palabras"
    TOTAL_RONDAS = 4

    def entrar(self):
        self.tarjeta = Tarjeta(250, 300, 230, 230)
        # mezcla palabras de dos y de tres silabas, en orden aleatorio
        dos = random.sample(PALABRAS_2_SILABAS, max(self.TOTAL_RONDAS - 2, 1))
        tres = random.sample(PALABRAS_3_SILABAS,
                             min(2, len(PALABRAS_3_SILABAS)))
        self.pool = (dos + tres)[:self.TOTAL_RONDAS]
        random.shuffle(self.pool)
        self.bloques = []
        self.brillo_arbol = 0.0
        super().entrar()

    def nueva_ronda(self):
        self.palabra, self.icono, self.silabas = self.pool[self.ronda]
        self.tarjeta.poner(self.icono)
        self.indice = 0
        self.brillo_arbol = 0.0
        n = len(self.silabas)
        ancho_s, sep = 150, 26
        total = n * ancho_s + (n - 1) * sep
        x0 = ANCHO // 2 + 120 - total // 2
        self.slots = [{"rect": pygame.Rect(x0 + i * (ancho_s + sep), 290,
                                           ancho_s, 106),
                       "silaba": self.silabas[i], "lleno": False}
                      for i in range(n)]
        opciones = list(self.silabas)
        extra = 2 if n == 2 else 1          # 4 fichas para 2 silabas, 4 para 3
        for s in distractores_silaba(self.silabas[0], extra,
                                     evitar=self.silabas):
            if s not in opciones:
                opciones.append(s)
        random.shuffle(opciones)
        self.bloques = []
        total_b = len(opciones)
        ancho_b, sep_b = 140, 22
        x0 = (ANCHO // 2 + 120) - (total_b * ancho_b + (total_b - 1) * sep_b) // 2
        for i, s in enumerate(opciones):
            x = x0 + i * (ancho_b + sep_b) + ancho_b // 2
            self.bloques.append(Bloque(s, x, 560))
        self.juego.fx.tocar("hoja")
        self.juego.voz.decir(self.instruccion(), 4.5)

    def instruccion(self):
        return (f"Ordena las silabas para escribir la palabra {self.palabra}. "
                f"Empieza por la primera.")

    @property
    def objetivo(self):
        if self.indice < len(self.silabas):
            return self.silabas[self.indice]
        return self.silabas[-1]

    def evento(self, ev):
        super().evento(ev)
        if self.bloqueo > 0:
            return
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for b in reversed(self.bloques):
                if b.rect.collidepoint(ev.pos) and not b.colocado:
                    b.arrastrando = True
                    b.off = (b.rect.centerx - ev.pos[0], b.rect.centery - ev.pos[1])
                    self.bloques.remove(b)
                    self.bloques.append(b)
                    self.juego.fx.tocar("click")
                    break
        elif ev.type == pygame.MOUSEMOTION:
            for b in self.bloques:
                if b.arrastrando:
                    b.rect.center = (ev.pos[0] + b.off[0], ev.pos[1] + b.off[1])
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            for b in self.bloques:
                if not b.arrastrando:
                    continue
                b.arrastrando = False
                destino = None
                for i, s in enumerate(self.slots):
                    if (not s["lleno"] and
                            s["rect"].inflate(60, 60).collidepoint(b.rect.center)):
                        destino = i
                        break
                if destino is None:
                    b.rect.center = b.origen
                    continue
                if destino == self.indice and b.silaba == self.slots[destino]["silaba"]:
                    b.colocado = True
                    b.giro = 0
                    b.rect.center = self.slots[destino]["rect"].center
                    self.slots[destino]["lleno"] = True
                    self.indice += 1
                    self.juego.fx.tocar("estrella")
                    self.juego.particulas.brillos(*b.rect.center, 14)
                    if self.indice >= len(self.silabas):
                        self.acierto(*self.slots[-1]["rect"].center)
                        self.bloqueo = 2.6
                        self.juego.voz.decir(
                            f"{self.palabra}. Lo lograste, el animal desperto.", 3.0)
                else:
                    b.sacudida = .5
                    b.rect.center = b.origen
                    self.error(self.slots[self.indice]["silaba"])

    def update(self, dt):
        super().update(dt)
        self.tarjeta.update(dt)
        for b in self.bloques:
            if b.sacudida > 0:
                b.sacudida -= dt
        if self.indice >= len(self.silabas):
            self.brillo_arbol = min(self.brillo_arbol + dt * 1.4, 1.0)
            if random.random() < dt * 22:
                self.juego.particulas.brillos(
                    ANCHO - 210 + random.uniform(-150, 150),
                    280 + random.uniform(-150, 150), 1)

    def _dibujar_arbol(self, surf):
        cx, base = ANCHO - 190, 560
        pygame.draw.polygon(surf, C_TRONCO, [
            (cx - 46, base), (cx - 26, base - 240), (cx + 26, base - 240),
            (cx + 46, base)])
        pygame.draw.polygon(surf, C_TRONCO_OSCURO, [
            (cx + 10, base), (cx + 16, base - 240), (cx + 26, base - 240),
            (cx + 46, base)])
        col = mezclar(C_BOSQUE_CERCA, (150, 226, 140), self.brillo_arbol)
        for dx, dy, r in ((-70, -260, 84), (70, -270, 88), (0, -330, 96),
                          (-40, -200, 66), (46, -196, 62)):
            pygame.draw.circle(surf, col,
                               (int(cx + dx), int(base + dy +
                                                  math.sin(self.t * 1.2 + dx) * 4)),
                               r)
        if self.brillo_arbol > 0:
            halo = pygame.Surface((460, 460), pygame.SRCALPHA)
            pygame.draw.circle(halo, (255, 240, 160,
                                      int(70 * self.brillo_arbol)),
                               (230, 230), 210)
            surf.blit(halo, (cx - 230, base - 500))
        # cofre
        pygame.draw.rect(surf, C_MADERA_OSC, (cx - 54, base - 6, 108, 62),
                         border_radius=10)
        pygame.draw.rect(surf, C_MADERA, (cx - 54, base - 6, 108, 24),
                         border_radius=10)
        pygame.draw.rect(surf, C_DORADO, (cx - 12, base + 10, 24, 22),
                         border_radius=5)

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        self._dibujar_arbol(surf)
        self.tarjeta.dibujar(surf, self.t)
        for i, s in enumerate(self.slots):
            r = s["rect"]
            if s["lleno"]:
                continue
            col_b = (255, 255, 255, 235) if i == self.indice else (255, 255, 255, 120)
            hueco = pygame.Surface((r.w, r.h), pygame.SRCALPHA)
            pygame.draw.rect(hueco, (255, 255, 255, 80), (0, 0, r.w, r.h),
                             border_radius=18)
            pygame.draw.rect(hueco, col_b, (0, 0, r.w, r.h), 5, border_radius=18)
            surf.blit(hueco, r.topleft)
            if i == self.indice:
                p = abs(math.sin(self.t * 3))
                pygame.draw.rect(surf, C_DORADO, r.inflate(12 * p, 12 * p),
                                 3, border_radius=20)
        texto(surf, j.fuentes.cuerpo, "Ordena las silabas",
              ANCHO // 2 + 120, 232, C_TEXTO, sombra=True)
        for b in self.bloques:
            b.dibujar(surf, j.fuentes, self.t)
        self.dibujar_hud(surf)
        self.dibujar_guia(surf, 118, ALTO - 110)


# ------------------------------------------------------------- FIN DE NIVEL
class EscenaFinNivel(Escena):
    def __init__(self, juego, nivel, estrellas, aciertos, errores):
        super().__init__(juego)
        self.nivel, self.estrellas = nivel, estrellas
        self.aciertos, self.errores = aciertos, errores
        self.animadas = [Tween(0, 1, .5, ease_out_back, .5 + i * .45)
                         for i in range(3)]
        self.sonadas = [False] * 3

    def entrar(self):
        j = self.juego
        j.guardar_resultado(self.nivel, self.estrellas)
        j.fx.tocar("nivel")
        j.particulas.confeti(ANCHO // 2, 300, 70)
        self.btn = Boton((ANCHO // 2 - 170, ALTO - 140, 340, 76), "Continuar",
                         C_DORADO)
        j.voz.decir(
            f"Sendero completado. Ganaste {self.estrellas} estrellas y una "
            f"estampa nueva para tu cuaderno.", 5.0)

    def evento(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.btn.click(ev.pos):
            self.juego.ir_a(EscenaMapa(self.juego))
        if ev.type == pygame.KEYDOWN and ev.key in (pygame.K_RETURN, pygame.K_ESCAPE):
            self.juego.ir_a(EscenaMapa(self.juego))

    def update(self, dt):
        super().update(dt)
        self.btn.update(dt, pygame.mouse.get_pos())
        for i, tw in enumerate(self.animadas):
            tw.update(dt)
            if i < self.estrellas and not self.sonadas[i] and tw.valor > .3:
                self.sonadas[i] = True
                self.juego.fx.tocar("estrella")
                self.juego.particulas.brillos(
                    ANCHO // 2 - 130 + i * 130, 320, 16)

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((255, 255, 255, 110))
        surf.blit(velo, (0, 0))
        panel = pygame.Surface((760, 430), pygame.SRCALPHA)
        pygame.draw.rect(panel, (255, 255, 255, 245), (0, 0, 760, 430),
                         border_radius=40)
        surf.blit(panel, (ANCHO // 2 - 380, 120))
        texto(surf, j.fuentes.h1, "Sendero completado", ANCHO // 2, 190,
              (46, 92, 66))
        for i, tw in enumerate(self.animadas):
            e = tw.valor if i < self.estrellas else 0
            x = ANCHO // 2 - 130 + i * 130
            dibujar_estrella(surf, x, 320, 54, 24, (222, 222, 214))
            if e > 0:
                dibujar_estrella(surf, x, 320, 54 * e, 24 * e, C_DORADO,
                                 self.t * 1.4)
        texto(surf, j.fuentes.cuerpo,
              f"Aciertos: {self.aciertos}     Intentos extra: {self.errores}",
              ANCHO // 2, 410, C_TEXTO_SUAVE)
        texto(surf, j.fuentes.chico,
              "Nueva estampa desbloqueada para tu cuaderno del explorador",
              ANCHO // 2, 462, C_TEXTO)
        dibujar_lina(surf, 200, 470, 150, self.t, "aplaude", j.voz.boca)
        self.btn.dibujar(surf, j.fuentes)


# ----------------------------------------------------------------- ALBUM
class EscenaAlbum(Escena):
    ESTAMPAS = [("oso", "OSO"), ("pato", "PATO"), ("sapo", "SAPO"),
                ("luna", "LUNA"), ("mesa", "MESA"), ("lupa", "LUPA"),
                ("puma", "PUMA"), ("mapa", "MAPA")]

    def entrar(self):
        self.btn = Boton((30, 30, 150, 54), "Volver", (214, 210, 200),
                         fuente=self.juego.fuentes.chico)
        self.juego.voz.decir("Este es tu cuaderno del explorador.", 3.0)

    def evento(self, ev):
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.btn.click(ev.pos):
            self.juego.ir_a(EscenaPortada(self.juego))
        if ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
            self.juego.ir_a(EscenaPortada(self.juego))

    def update(self, dt):
        super().update(dt)
        self.btn.update(dt, pygame.mouse.get_pos())

    def dibujar(self, surf):
        j = self.juego
        j.bosque.dibujar(surf)
        panel = pygame.Surface((1080, 470), pygame.SRCALPHA)
        pygame.draw.rect(panel, (255, 252, 242, 245), (0, 0, 1080, 470),
                         border_radius=36)
        surf.blit(panel, (100, 150))
        texto(surf, j.fuentes.h1, "Cuaderno del explorador", ANCHO // 2, 200,
              (46, 92, 66))
        total = sum(j.progreso["estrellas"].values())
        texto(surf, j.fuentes.cuerpo, f"Estrellas reunidas: {total}",
              ANCHO // 2, 250, C_TEXTO_SUAVE)
        desbloq = j.progreso["nivel_max"] * 3
        for i, (ic, nom) in enumerate(self.ESTAMPAS):
            x = 220 + (i % 4) * 240
            y = 340 + (i // 4) * 170
            abierto = i < desbloq
            pygame.draw.circle(surf, (238, 232, 216), (x, y), 62)
            if abierto:
                pygame.draw.circle(surf, C_DORADO, (x, y), 62, 5)
                dibujar_icono(surf, ic, x, y, 62, self.t + i)
                texto(surf, j.fuentes.chico, nom, x, y + 84, C_TEXTO)
            else:
                pygame.draw.circle(surf, (206, 200, 186), (x, y), 62, 5)
                texto(surf, j.fuentes.h1, "?", x, y, (186, 180, 168))
        self.btn.dibujar(surf, j.fuentes)


# ==========================================================================
#  NUCLEO DEL JUEGO
# ==========================================================================
class Juego:
    def __init__(self):
        pygame.init()
        try:
            pygame.mixer.pre_init(44100, -16, 2, 512)
        except Exception:
            pass
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO))
        pygame.display.set_caption(TITULO)
        self.reloj = pygame.time.Clock()
        self.fuentes = Fuentes()
        self.voz = Voz()
        self.fx = Efectos()
        self.voz.fx = self.fx
        self.bosque = Bosque()
        self.particulas = SistemaParticulas()
        self.progreso = self.cargar_progreso()
        self.corriendo = True
        self.pantalla_completa = False
        self.escena = None
        self.transicion = 1.0
        self.siguiente = None
        self.ir_a(EscenaPortada(self))

    # -- progreso ----------------------------------------------------------
    def _leer_almacen(self):
        """En el navegador usa localStorage; en escritorio, un archivo JSON."""
        if ES_WEB and _window is not None:
            try:
                crudo = _window.localStorage.getItem(CLAVE_PROGRESO)
                return json.loads(crudo) if crudo else None
            except Exception:
                return None
        try:
            with open(ARCHIVO_PROGRESO, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _escribir_almacen(self, datos):
        if ES_WEB and _window is not None:
            try:
                _window.localStorage.setItem(
                    CLAVE_PROGRESO, json.dumps(datos, ensure_ascii=False))
            except Exception:
                pass
            return
        try:
            with open(ARCHIVO_PROGRESO, "w", encoding="utf-8") as f:
                json.dump(datos, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def cargar_progreso(self):
        base = {"nivel_max": 1, "estrellas": {}}
        datos = self._leer_almacen()
        if isinstance(datos, dict):
            base.update({k: datos.get(k, v) for k, v in base.items()})
        return base

    def guardar_resultado(self, nivel, estrellas):
        clave = str(nivel)
        prev = self.progreso["estrellas"].get(clave, 0)
        self.progreso["estrellas"][clave] = max(prev, estrellas)
        self.progreso["nivel_max"] = max(self.progreso["nivel_max"],
                                         min(nivel + 1, 3))
        self._escribir_almacen(self.progreso)

    # -- escenas -----------------------------------------------------------
    def ir_a(self, escena):
        if self.escena is None:
            self.escena = escena
            escena.entrar()
        elif self.siguiente is None:
            self.siguiente = escena
            self.transicion = 0.0
        # si ya hay una transicion en curso se ignora la peticion: repetirla
        # cada fotograma dejaba el juego congelado en la pantalla anterior

    def salir(self):
        self.corriendo = False

    def alternar_pantalla(self):
        if ES_WEB:
            return                      # en el navegador lo hace el propio boton
        self.pantalla_completa = not self.pantalla_completa
        flags = pygame.FULLSCREEN | pygame.SCALED if self.pantalla_completa else 0
        self.pantalla = pygame.display.set_mode((ANCHO, ALTO), flags)

    # -- bucle -------------------------------------------------------------
    async def ejecutar(self):
        """Bucle principal asincrono: igual en escritorio y en navegador."""
        while self.corriendo:
            dt = min(self.reloj.tick(FPS) / 1000.0, 1 / 25)
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.corriendo = False
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_F11:
                    self.alternar_pantalla()
                elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_m:
                    callado = self.fx.alternar_silencio()
                    self.voz.decir("Sonido apagado." if callado
                                   else "Sonido encendido.", 1.4)
                elif self.siguiente is None:
                    self.escena.evento(ev)

            self.bosque.update(dt)
            self.particulas.update(dt)
            self.voz.update(dt)
            self.escena.update(dt)

            if self.siguiente is not None:
                self.transicion += dt * 2.6
                if self.transicion >= 1.0:
                    self.escena = self.siguiente
                    self.escena.entrar()
                    self.siguiente = None
                    self.transicion = 0.0
            elif self.transicion < 1.0:
                self.transicion = min(self.transicion + dt * 2.6, 1.0)

            self.escena.dibujar(self.pantalla)
            self.particulas.dibujar(self.pantalla)
            self.dibujar_subtitulo(self.pantalla)
            self.dibujar_transicion(self.pantalla)
            pygame.display.flip()

            # imprescindible para pygbag: devuelve el control al navegador
            await asyncio.sleep(0)

        pygame.quit()
        if not ES_WEB:
            sys.exit(0)

    def dibujar_subtitulo(self, surf):
        if not self.voz.subtitulo:
            return
        a = clamp(self.voz.subtitulo_t, 0, 1)
        f = self.fuentes.chico
        ancho = min(f.size(self.voz.subtitulo)[0] + 60, ANCHO - 120)
        caja = pygame.Surface((ancho, 52), pygame.SRCALPHA)
        pygame.draw.rect(caja, (24, 28, 32, int(190 * a)), (0, 0, ancho, 52),
                         border_radius=18)
        surf.blit(caja, (ANCHO // 2 - ancho // 2, ALTO - 66))
        texto(surf, f, self.voz.subtitulo, ANCHO // 2, ALTO - 40, C_CREMA)

    def dibujar_transicion(self, surf):
        if self.siguiente is not None:
            p = clamp(self.transicion, 0, 1)
        elif self.transicion < 1.0:
            p = 1.0 - clamp(self.transicion, 0, 1)
        else:
            return
        velo = pygame.Surface((ANCHO, ALTO), pygame.SRCALPHA)
        velo.fill((26, 44, 38, int(235 * p)))
        surf.blit(velo, (0, 0))
        if p > .25:
            for i in range(7):
                x = ANCHO / 2 + math.cos(self.escena.t * 2 + i) * 90
                y = ALTO / 2 + math.sin(self.escena.t * 2 + i) * 40
                dibujar_estrella(velo, x, y, 12, 5, C_DORADO)
            surf.blit(velo, (0, 0))


# ==========================================================================
async def main():
    await Juego().ejecutar()


if __name__ == "__main__":
    asyncio.run(main())