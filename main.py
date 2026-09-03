# main.py — punto de entrada del proceso wake word
# =====================================================
# Inicia el listener de palabra de activacion y
# maneja el ciclo de vida del proceso.
# =====================================================

import asyncio
import logging
from wake_word_listener import WakeWordListener

logger = logging.getLogger("it_wake_word")

async def main() -> None:
    """
    Punto de entrada principal del proceso wake word.
    
    Crea el listener, lo inicia y maneja el apagado
    ordenado cuando el usuario presiona CTRL+C.

    Returns:
        None.
    """
    listener = WakeWordListener()

    try:
        await listener.start()
    except KeyboardInterrupt:
        logger.info("Proceso wake word detenido por el usuario.")
    finally:
        listener.cleanup()

if __name__ == "__main__":
    asyncio.run(main())