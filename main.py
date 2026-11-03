# main.py — punto de entrada del proceso wake word
# =====================================================
# Configura el proceso, inicia el listener de palabra de
# activacion y garantiza el apagado ordenado.
# =====================================================

import asyncio
import ctypes
import logging
import os
import sys

from wake_word.config import ConfigError
from wake_word.wake_word_listener import WakeWordListener

logger = logging.getLogger("it_wake_word")


def configure_logging() -> None:
    """Logs a stdout, con el formato que documenta el README."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    # Evita duplicar mensajes en el logger raiz
    logger.propagate = False


def lower_process_priority() -> None:
    """
    Baja la prioridad del proceso. Este servicio convive con Unity y otros
    servicios: con prioridad normal podria competir con ellos por CPU.
    El wake word solo necesita ~5% de un nucleo, asi que no se resiente.
    """
    try:
        if os.name == "nt":
            from ctypes import wintypes

            BELOW_NORMAL_PRIORITY_CLASS = 0x00004000
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = wintypes.HANDLE
            kernel32.SetPriorityClass.argtypes = [wintypes.HANDLE, wintypes.DWORD]
            kernel32.SetPriorityClass(
                kernel32.GetCurrentProcess(), BELOW_NORMAL_PRIORITY_CLASS
            )
        else:
            os.nice(5)
    except Exception as exc:  # optimizacion opcional: nunca debe impedir arrancar
        logger.warning(f"No se pudo bajar la prioridad del proceso: {exc}")


async def main() -> None:
    """
    Crea el listener y lo corre hasta que se cancele (Ctrl+C).
    El finally asegura que el microfono se libere siempre.
    """
    listener = WakeWordListener()
    try:
        await listener.start()
    finally:
        listener.cleanup()


def run() -> None:
    configure_logging()
    lower_process_priority()
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Proceso wake word detenido por el usuario.")
    except ConfigError as exc:
        logger.error(f"Configuracion invalida: {exc}")
        sys.exit(2)


if __name__ == "__main__":
    run()
