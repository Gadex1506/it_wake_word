# config.py
# =====================================================
# Configuracion del servicio de wake word.
#
# Lee las variables de entorno (.env) una sola vez y las
# expone como un objeto inmutable. Un valor vacio en el
# .env se trata como "no definido" y usa el valor por
# defecto, asi que copiar .env.example tal cual funciona.
# =====================================================

import importlib.util
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_DIR / "models"

# Se carga desde la carpeta del proyecto (no desde el cwd) para que
# funcione igual si Unity lanza el proceso desde otro directorio.
load_dotenv(PROJECT_DIR / ".env")


# =============================================================
# Constantes de audio (fijas: las impone OpenWakeWord)
# =============================================================

# Tasa de muestreo requerida por OpenWakeWord
SAMPLE_RATE = 16000

# 1280 muestras a 16 kHz = 80 ms de audio por chunk.
CHUNK_SIZE = 1280
CHUNK_SECONDS = CHUNK_SIZE / SAMPLE_RATE

# Mensaje que se envia a Unity cuando se detecta el wake word
WAKE_WORD_DETECTED_MESSAGE = "WAKE_WORD_DETECTED"

# Tiempo minimo entre detecciones para evitar activaciones multiples
# por el mismo evento de audio.
MIN_SECONDS_BETWEEN_DETECTIONS = 2.0


class ConfigError(ValueError):
    """Valor invalido en la configuracion (.env)."""


def _read(name: str, default: str, cast=str):
    """Lee una variable de entorno; vacia o ausente => default."""
    raw = os.getenv(name, "").strip()
    try:
        return cast(raw if raw else default)
    except ValueError as exc:
        raise ConfigError(f"{name}='{raw}' no es valido: {exc}") from exc


def _optional_int(raw: str):
    """'None' (o vacio) => None; cualquier otro valor => int."""
    return None if raw.lower() in ("none", "") else int(raw)


def _resolve_model_path(name: str) -> Path:
    """
    Busca el modelo .onnx. Orden: ruta directa, ./models/, y por ultimo
    los modelos preentrenados que trae el paquete openwakeword.
    """
    direct = Path(name)
    if direct.suffix == ".onnx" and direct.is_file():
        return direct

    searched = [MODELS_DIR / f"{name}.onnx"]

    # find_spec localiza el paquete sin importarlo (importarlo es caro).
    spec = importlib.util.find_spec("openwakeword")
    if spec and spec.origin:
        searched.append(
            Path(spec.origin).parent / "resources" / "models" / f"{name}.onnx"
        )

    for path in searched:
        if path.is_file():
            return path

    raise ConfigError(
        f"No se encontro el modelo '{name}'. Buscado en: "
        + ", ".join(str(p) for p in searched)
    )


@dataclass(frozen=True)
class Settings:
    """Configuracion efectiva del servicio."""

    model_name: str
    model_path: Path
    threshold: float
    patience: int
    host: str
    port: int
    microphone_index: int | None
    gate_rms: float

    @property
    def model_key(self) -> str:
        """Clave del modelo en el dict de predicciones (nombre sin extension)."""
        return self.model_path.stem


def load_settings() -> Settings:
    """Construye Settings desde el entorno, validando los rangos."""
    model_name = _read("WAKE_WORD_MODEL", "meeah")
    threshold = _read("WAKE_WORD_THRESHOLD", "0.5", float)
    patience = _read("WAKE_WORD_PATIENCE", "1", int)
    port = _read("UNITY_SOCKET_PORT", "9000", int)
    gate_rms = _read("ENERGY_GATE_RMS", "0", float)

    if not 0.0 < threshold <= 1.0:
        raise ConfigError(f"WAKE_WORD_THRESHOLD debe estar en (0, 1], era {threshold}")
    if patience < 1:
        raise ConfigError(f"WAKE_WORD_PATIENCE debe ser >= 1, era {patience}")
    if not 0 < port < 65536:
        raise ConfigError(f"UNITY_SOCKET_PORT fuera de rango: {port}")
    if gate_rms < 0:
        raise ConfigError(f"ENERGY_GATE_RMS no puede ser negativo, era {gate_rms}")

    return Settings(
        model_name=model_name,
        model_path=_resolve_model_path(model_name),
        threshold=threshold,
        patience=patience,
        host=_read("UNITY_SOCKET_HOST", "127.0.0.1"),
        port=port,
        microphone_index=_read("MICROPHONE_INDEX", "None", _optional_int),
        gate_rms=gate_rms,
    )
