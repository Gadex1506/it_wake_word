# microphone.py
# =====================================================
# Acceso al microfono con PyAudio.
#
# MicrophoneStream es un context manager que crea PyAudio,
# abre el stream y los libera al salir. Se crea PyAudio de
# nuevo en cada apertura a proposito: PortAudio cachea la
# lista de dispositivos al inicializarse, asi que solo
# re-inicializandolo se recupera un microfono que se
# desconecto y volvio (USB, reinicio de SteelSeries Sonar).
#
# Seleccion del microfono (de mayor a menor prioridad):
#   1. device_index: indice exacto (varia entre PCs).
#   2. device_name: fragmento del nombre, para usar el mismo
#      microfono que el proyecto de Unity en cualquier PC.
#      Si no hay coincidencia se usa el predeterminado.
#   3. Predeterminado de Windows.
# =====================================================

import logging
import unicodedata

import numpy as np
import pyaudio

from wake_word.config import CHUNK_SIZE, SAMPLE_RATE

logger = logging.getLogger("it_wake_word")

# La API MME de Windows recorta los nombres de dispositivo a 31 caracteres.
MME_NAME_LIMIT = 31


def accepts_format(audio: pyaudio.PyAudio, index: int) -> bool:
    """True si el dispositivo acepta 16 kHz, mono, int16."""
    try:
        return audio.is_format_supported(
            SAMPLE_RATE,
            input_device=index,
            input_channels=1,
            input_format=pyaudio.paInt16,
        )
    except ValueError:
        return False


def clean_device_name(name: str) -> str:
    """
    Repara el nombre que PyAudio devuelve en Windows: PortAudio lo entrega en
    UTF-8 pero PyAudio lo decodifica como cp1252, y "Microfono" con tilde
    llega como "MicrÃ³fono". Los nombres solo ASCII no cambian.
    """
    for encoding in ("cp1252", "latin-1"):
        try:
            return name.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
    return name


def _normalize(text: str) -> str:
    """Minusculas y sin tildes, para comparar nombres sin sorpresas."""
    decomposed = unicodedata.normalize("NFKD", clean_device_name(text))
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold().strip()


def match_device_index(query: str, devices) -> int | None:
    """
    Devuelve el indice del primer dispositivo cuyo nombre coincide con `query`.

    `devices` es un iterable de (indice, nombre). Coincide si `query` es un
    fragmento del nombre, o si el nombre es un recorte MME (31 caracteres)
    del inicio de `query` (caso: se pega el nombre completo que muestra Unity).
    """
    wanted = _normalize(query)
    if not wanted:
        return None
    for index, name in devices:
        candidate = _normalize(name)
        truncated = len(candidate) >= MME_NAME_LIMIT and wanted.startswith(candidate)
        if wanted in candidate or truncated:
            return index
    return None


class MicrophoneStream:
    """Lectura bloqueante de chunks de audio mono int16 a 16 kHz."""

    def __init__(
        self, device_index: int | None = None, device_name: str | None = None
    ) -> None:
        self._device_index = device_index
        self._requested_name = device_name
        self._audio = None
        self._stream = None
        self.device_name = ""  # nombre del dispositivo realmente abierto

    def __enter__(self) -> "MicrophoneStream":
        self._audio = pyaudio.PyAudio()
        try:
            index = self._resolve_device_index()
            info = (
                self._audio.get_device_info_by_index(index)
                if index is not None
                else self._audio.get_default_input_device_info()
            )
            self.device_name = clean_device_name(info["name"])
            self._stream = self._audio.open(
                rate=SAMPLE_RATE,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                input_device_index=index,
            )
        except Exception:
            self._audio.terminate()
            raise
        return self

    def _resolve_device_index(self) -> int | None:
        """Indice a abrir, o None para usar el predeterminado del sistema."""
        if self._device_index is not None:
            return self._device_index
        if not self._requested_name:
            return None

        candidates = []
        for i in range(self._audio.get_device_count()):
            info = self._audio.get_device_info_by_index(i)
            if info["maxInputChannels"] >= 1 and accepts_format(self._audio, i):
                candidates.append((i, info["name"]))

        index = match_device_index(self._requested_name, candidates)
        if index is None:
            logger.warning(
                f"No se encontro un microfono que coincida con "
                f"'{self._requested_name}'. Usando el predeterminado del sistema."
            )
        return index

    def read(self) -> np.ndarray:
        """Bloquea ~80 ms y devuelve un chunk de CHUNK_SIZE muestras."""
        data = self._stream.read(CHUNK_SIZE, exception_on_overflow=False)
        return np.frombuffer(data, dtype=np.int16)

    def __exit__(self, exc_type, exc, traceback) -> None:
        try:
            self._stream.stop_stream()
            self._stream.close()
        except Exception:
            pass  # el dispositivo pudo haber desaparecido; igual hay que liberar
        finally:
            self._audio.terminate()
