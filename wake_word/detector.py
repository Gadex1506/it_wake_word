# detector.py
# =====================================================
# Logica de deteccion de la palabra de activacion.
#
# Recibe chunks de audio y decide si hubo wake word. No sabe
# nada de microfono ni de WebSocket: eso lo hace el listener.
#
# Tres filtros, de menor a mayor costo evitado:
#   - Compuerta de energia (opcional): en silencio no se ejecuta
#     el modelo. Es la mayor fuente de ahorro de CPU.
#   - Patience: exige N frames consecutivos sobre el umbral.
#   - Debounce: ignora detecciones repetidas del mismo evento.
# =====================================================

import time
from collections import deque

import numpy as np

from wake_word.config import MIN_SECONDS_BETWEEN_DETECTIONS, Settings
from wake_word.openwakeword_tuning import enable_ring_buffer, load_model_class

# La compuerta sigue abierta ~1.5 s tras el ultimo sonido, para que el
# modelo termine de evaluar la palabra.
GATE_HANGOVER_CHUNKS = 19

# Al abrirse la compuerta se re-alimenta el modelo con el audio previo
# (~1.3 s = la ventana de 16 embeddings que usa el clasificador), para que
# su estado interno no mezcle audio de antes y despues del silencio.
GATE_PREROLL_CHUNKS = 16


class WakeWordDetector:
    """Convierte chunks de audio int16 en eventos de wake word."""

    def __init__(self, settings: Settings, model, clock=time.monotonic) -> None:
        self._model = model
        self._key = settings.model_key
        self._threshold = settings.threshold
        self._patience = settings.patience
        self._gate_rms = settings.gate_rms
        self._clock = clock

        self._streak = 0
        self._last_detection = float("-inf")

        self._open_chunks = 0
        self._preroll: deque = deque(maxlen=GATE_PREROLL_CHUNKS)

    def process(self, chunk: np.ndarray) -> float | None:
        """
        Procesa un chunk. Devuelve la confianza si se detecto el wake word,
        o None en caso contrario.
        """
        if self._gate_rms > 0 and not self._gate_is_open(chunk):
            return None

        score = float(self._model.predict(chunk).get(self._key, 0.0))
        return self._evaluate(score)

    def _gate_is_open(self, chunk: np.ndarray) -> bool:
        """True si hay sonido suficiente como para correr el modelo."""
        rms = float(np.sqrt(np.mean(np.square(chunk, dtype=np.float32))))
        was_closed = self._open_chunks == 0

        if rms >= self._gate_rms:
            self._open_chunks = GATE_HANGOVER_CHUNKS
        elif self._open_chunks > 0:
            self._open_chunks -= 1

        if self._open_chunks == 0:
            self._preroll.append(chunk)
            self._streak = 0
            return False

        if was_closed:
            # Calentar el modelo con el audio previo; sus scores se descartan
            # porque son anteriores al inicio del sonido.
            for old_chunk in self._preroll:
                self._model.predict(old_chunk)
            self._preroll.clear()
        return True

    def _evaluate(self, score: float) -> float | None:
        """Aplica umbral, patience y debounce a un score."""
        self._streak = self._streak + 1 if score >= self._threshold else 0
        if self._streak < self._patience:
            return None

        now = self._clock()
        if now - self._last_detection < MIN_SECONDS_BETWEEN_DETECTIONS:
            return None

        self._last_detection = now
        self._streak = 0
        # El audio de la activacion sigue en los buffers del modelo ~10 s;
        # limpiarlos evita que contamine las siguientes evaluaciones.
        self._model.reset()
        return score


def build_detector(settings: Settings) -> WakeWordDetector:
    """Carga el modelo ONNX y arma el detector."""
    Model = load_model_class()
    model = Model(
        wakeword_models=[str(settings.model_path)],
        inference_framework="onnx",
    )
    enable_ring_buffer(model)
    return WakeWordDetector(settings, model)
