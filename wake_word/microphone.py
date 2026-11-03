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
# =====================================================

import numpy as np
import pyaudio

from wake_word.config import CHUNK_SIZE, SAMPLE_RATE


class MicrophoneStream:
    """Lectura bloqueante de chunks de audio mono int16 a 16 kHz."""

    def __init__(self, device_index: int | None = None) -> None:
        self._device_index = device_index
        self._audio = None
        self._stream = None

    def __enter__(self) -> "MicrophoneStream":
        self._audio = pyaudio.PyAudio()
        try:
            self._stream = self._audio.open(
                rate=SAMPLE_RATE,
                channels=1,
                format=pyaudio.paInt16,
                input=True,
                frames_per_buffer=CHUNK_SIZE,
                input_device_index=self._device_index,
            )
        except Exception:
            self._audio.terminate()
            raise
        return self

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
