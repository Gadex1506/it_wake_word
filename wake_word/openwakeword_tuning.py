# openwakeword_tuning.py
# =====================================================
# Dos ajustes de rendimiento sobre openwakeword 0.6.0 que
# no se pueden hacer por configuracion:
#
# 1. load_model_class(): evita importar sklearn/scipy.
#    El __init__ de openwakeword importa su "custom verifier"
#    (sklearn) aunque no se use. Eso son ~1.5 s de CPU y
#    decenas de MB de RAM en cada arranque.
#
# 2. enable_ring_buffer(): reemplaza el buffer interno de audio.
#    Por cada chunk de 80 ms, la libreria hace
#    list(deque_de_160000_enteros)[-1760:], es decir copia 10 s
#    de audio como objetos Python para quedarse con 0.1 s.
#    Un ring buffer de numpy da el mismo resultado sin esa copia.
#
# Ambos son defensivos: si una version futura de openwakeword
# cambia sus internos, se deja el comportamiento original.
# =====================================================

import logging
import sys
import types

import numpy as np

from wake_word.config import SAMPLE_RATE

logger = logging.getLogger("it_wake_word")

# Capacidad del ring buffer. Debe superar (muestras por llamada + 480).
# Con chunks de 80 ms sobra; 2 s admite hasta ~24 chunks por llamada.
RING_CAPACITY = 2 * SAMPLE_RATE

# La libreria pide 3 frames de contexto (160 muestras c/u) antes del chunk
# para que el melspectrograma sea continuo entre chunks.
MELSPEC_CONTEXT_SAMPLES = 160 * 3


def load_model_class():
    """Devuelve openwakeword.model.Model sin arrastrar sklearn ni scipy."""
    if "openwakeword" not in sys.modules:
        stub = types.ModuleType("openwakeword.custom_verifier_model")
        stub.train_custom_verifier = None
        sys.modules.setdefault("openwakeword.custom_verifier_model", stub)

    from openwakeword.model import Model

    return Model


class _SampleRing:
    """Ultimas RING_CAPACITY muestras int16, sin copias de objetos Python."""

    def __init__(self, capacity: int) -> None:
        self._data = np.zeros(capacity, dtype=np.int16)
        self._filled = 0

    def append(self, samples) -> None:
        samples = np.asarray(samples, dtype=np.int16)
        n, cap = samples.shape[0], self._data.shape[0]
        if n >= cap:
            self._data[:] = samples[-cap:]
        else:
            self._data[:-n] = self._data[n:]
            self._data[-n:] = samples
        self._filled = min(cap, self._filled + n)

    def tail(self, n: int) -> np.ndarray:
        """Ultimas n muestras (o las que haya si aun no hay tantas)."""
        k = min(n, self._filled)
        return self._data[self._data.shape[0] - k:]

    def clear(self) -> None:
        self._data[:] = 0
        self._filled = 0


def enable_ring_buffer(model) -> bool:
    """
    Sustituye el buffer de audio del preprocesador de `model` por un ring
    buffer de numpy. Devuelve True si se aplico.
    """
    pre = model.preprocessor
    required = (
        "_buffer_raw_data", "_streaming_melspectrogram", "_get_melspectrogram",
        "melspectrogram_buffer", "melspectrogram_max_len", "reset",
    )
    if not all(hasattr(pre, name) for name in required):
        logger.warning(
            "Version de openwakeword no reconocida: se usa el buffer original."
        )
        return False

    ring = _SampleRing(RING_CAPACITY)
    original_reset = pre.reset

    def streaming_melspectrogram(n_samples: int) -> None:
        segment = ring.tail(n_samples + MELSPEC_CONTEXT_SAMPLES)
        pre.melspectrogram_buffer = np.vstack(
            (pre.melspectrogram_buffer, pre._get_melspectrogram(segment))
        )
        if pre.melspectrogram_buffer.shape[0] > pre.melspectrogram_max_len:
            pre.melspectrogram_buffer = pre.melspectrogram_buffer[
                -pre.melspectrogram_max_len:, :
            ]

    def reset() -> None:
        ring.clear()
        original_reset()

    pre._buffer_raw_data = ring.append
    pre._streaming_melspectrogram = streaming_melspectrogram
    pre.reset = reset
    return True
