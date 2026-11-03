# wake_word_listener.py
# =====================================================
# Listener de palabra de activacion para el asistente
# de voz del hogar.
#
# Responsabilidad: conectar las dos mitades del servicio.
#   - Un hilo de captura lee el microfono y corre el detector.
#     La lectura de audio y la inferencia son bloqueantes, asi
#     que viven fuera del event loop.
#   - El event loop atiende el servidor WebSocket y notifica a
#     Unity cuando el hilo reporta una deteccion.
#
# Arquitectura: este proceso actua como servidor WebSocket.
# Unity se conecta como cliente al arrancar.
# =====================================================

import asyncio
import logging
import threading

import websockets
from websockets.asyncio.server import ServerConnection

from wake_word.config import WAKE_WORD_DETECTED_MESSAGE, Settings, load_settings
from wake_word.detector import build_detector
from wake_word.microphone import MicrophoneStream

logger = logging.getLogger("it_wake_word")

# Espera entre intentos cuando el microfono no esta disponible
MICROPHONE_RETRY_SECONDS = 3.0

# Tiempo maximo que cleanup() espera al hilo de captura
SHUTDOWN_TIMEOUT_SECONDS = 2.0


class WakeWordListener:
    """
    Escucha el microfono y notifica a Unity al detectar el wake word.

    Attributes:
        _settings: configuracion efectiva del servicio.
        _detector: detector de wake word (se usa solo desde el hilo de captura).
        _clients: conexiones WebSocket activas (se usa solo desde el event loop).
    """

    def __init__(self, settings: Settings | None = None) -> None:
        """Carga el modelo una sola vez al instanciar."""
        self._settings = settings or load_settings()

        logger.info(f"Cargando modelo de wake word: '{self._settings.model_name}'")
        self._detector = build_detector(self._settings)
        logger.info("Modelo cargado correctamente.")

        self._clients: set[ServerConnection] = set()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._capture_failed: asyncio.Future | None = None

    async def start(self) -> None:
        """
        Inicia el servidor WebSocket y el hilo de captura.

        Corre hasta ser cancelado (Ctrl+C) o hasta que la captura falle
        con un error que no sea simplemente "microfono no disponible".
        """
        self._loop = asyncio.get_running_loop()
        self._capture_failed = self._loop.create_future()

        logger.info(
            f"Iniciando servidor WebSocket en "
            f"ws://{self._settings.host}:{self._settings.port}"
        )

        async with websockets.serve(
            self._handle_unity_connection,
            self._settings.host,
            self._settings.port,
        ):
            logger.info("Servidor WebSocket activo. Esperando Unity...")
            self._thread = threading.Thread(
                target=self._run_capture, name="audio-capture", daemon=True
            )
            self._thread.start()
            await self._capture_failed

    async def _handle_unity_connection(self, websocket: ServerConnection) -> None:
        """Registra al cliente mientras la conexion siga abierta."""
        address = websocket.remote_address
        self._clients.add(websocket)
        logger.info(f"Unity conectado desde: {address}. Clientes: {len(self._clients)}")

        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)
            logger.info(
                f"Unity desconectado: {address}. Clientes: {len(self._clients)}"
            )

    # ---------------------------------------------------------
    # Hilo de captura
    # ---------------------------------------------------------

    def _run_capture(self) -> None:
        """Punto de entrada del hilo: reporta al event loop si muere."""
        try:
            self._capture_loop()
        except Exception as exc:
            logger.exception("Fallo inesperado en la captura de audio.")
            self._loop.call_soon_threadsafe(self._fail, exc)

    def _fail(self, exc: Exception) -> None:
        if not self._capture_failed.done():
            self._capture_failed.set_exception(exc)

    def _capture_loop(self) -> None:
        """
        Lee el microfono y corre el detector. Si el microfono falla o
        desaparece, reintenta indefinidamente sin tumbar el servicio.
        """
        while not self._stop.is_set():
            try:
                with MicrophoneStream(self._settings.microphone_index) as mic:
                    logger.info(
                        f"Microfono activo. Umbral de deteccion: "
                        f"{self._settings.threshold}"
                    )
                    logger.info("Escuchando... Di la palabra de activacion.")

                    while not self._stop.is_set():
                        confidence = self._detector.process(mic.read())
                        if confidence is not None:
                            self._loop.call_soon_threadsafe(
                                self._notify_clients, confidence
                            )
            except OSError as exc:
                logger.warning(
                    f"Microfono no disponible ({exc}). "
                    f"Reintentando en {MICROPHONE_RETRY_SECONDS:.0f}s..."
                )
                self._stop.wait(MICROPHONE_RETRY_SECONDS)

    def _notify_clients(self, confidence: float) -> None:
        """Envia WAKE_WORD_DETECTED a todos los clientes (corre en el event loop)."""
        if not self._clients:
            logger.warning("Wake word detectado pero Unity no esta conectado.")
            return

        logger.info(
            f"Wake word detectado con confianza: {confidence:.3f}. "
            f"Notificando a {len(self._clients)} cliente(s)..."
        )
        # broadcast no bloquea y descarta por si solo las conexiones cerradas
        websockets.broadcast(self._clients, WAKE_WORD_DETECTED_MESSAGE)

    def cleanup(self) -> None:
        """Detiene el hilo de captura y libera el microfono."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=SHUTDOWN_TIMEOUT_SECONDS)
        logger.info("Recursos de audio liberados.")
