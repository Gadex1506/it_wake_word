# test_wake_word_flow.py — verificacion temporal, borrar despues
# Simula el comportamiento de Unity conectandose al servidor
# WebSocket del proceso wake word.

import asyncio
import websockets
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Unity_Simulator")

WEBSOCKET_URL = "ws://127.0.0.1:9000"

async def simulate_unity_client() -> None:
    """
    Simula Unity conectandose al servidor WebSocket
    y esperando la notificacion de wake word
    """
    logger.info(f"Simulador Unity conectandose a {WEBSOCKET_URL}...")

    try:
        async with websockets.connect(WEBSOCKET_URL) as websocket:
            logger.info("Conectado al servidor wake word.")
            logger.info("Esperando deteccion de wake word.")
            logger.info("Di 'Emma' frente al microfono.")

            # Esperar mensajes del servidor
            while True:
                message = await websocket.recv()
                logger.info(f"Mensaje recibido de it_wake_word: '{message}'")

                if message == "WAKE_WORD_DETECTED":
                    logger.info(
                        "Wake word detectado. "
                        "Unity iniciaria grabacion del comando aqui."
                    )           
    except ConnectionRefusedError:
        logger.error(
            "No se pudo conectar. "
            "Asegurate de que it_wake_word/main.py esta corriendo correctamente."
        )

if __name__ == "__main__":
    asyncio.run(simulate_unity_client())