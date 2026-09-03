# wake_word_listener.py
# =====================================================
# Listener de palabra de activacion para el asistente
# de voz del hogar ARIA.
#
# Responsabilidad: escuchar el microfono continuamente,
# detectar la palabra de activacion con OpenWakeWord
# y notificar a Unity via socket cuando se detecta.
#
# Arquitectura: este proceso actua como servidor WebSocket.
# Unity se conecta como cliente al arrancar.
# =====================================================

import os
import asyncio
import pyaudio
import numpy as np
import websockets
import logging
import openwakeword
from openwakeword.model import Model
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("it_wake_word")
logger.setLevel(logging.INFO)

if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

# Evitar que el logger propague mensajes al logger raiz
# que podria tener un formato incompatible con librerias externas
logger.propagate = False


# =============================================================
# Constantes de configuracion de audio
# =============================================================

# Tasa de muestreo requerida por OpenWakeWord
SAMPLE_RATE = 16000

# Tamanio del chunk de audio procesado por iteracion.
# 1280 muestras a 16Khz = 80ms de audio por chunk.
CHUNK_SIZE = 1280

# Formato de audio: enteros de 16 bits sin signo
AUDIO_FORMAT = pyaudio.paInt16

# Canal mono (1 canal) requerido por OpenWakeWord
AUDIO_CHANNELS = 1


# =============================================================
# Configuracion desde .env
# =============================================================

WAKE_WORD_MODEL = os.getenv("WAKE_WORD_MODEL", "emma")
WAKE_WORD_THRESHOLD = float(os.getenv("WAKE_WORD_THRESHOLD", "0.4"))
WEBSOCKET_HOST = os.getenv("UNITY_SOCKET_HOST", "127.0.0.1")
WEBSOCKET_PORT = int(os.getenv("UNITY_SOCKET_PORT", "9000"))
MICROPHONE_INDEX = os.getenv("MICROPHONE_INDEX", "None")

# Convertir MICROPHONE_INDEX a int o None segun el valor del .env
MICROPHONE_INDEX = (
    None if MICROPHONE_INDEX == "None"
    else int(MICROPHONE_INDEX)
)

# Construir ruta completa al modelo para soportar modelos personalizados.
# OpenWakeWord solo encuentra modelos preentrenados por nombre.
# Los modelos personalizados necesitan la ruta completa al archivo .onnx
MODELS_DIR = os.path.join(
    os.path.dirname(openwakeword.__file__),
    "resources",
    "models",
)
MODEL_PATH = os.path.join(MODELS_DIR, f"{WAKE_WORD_MODEL}.onnx")

# Clave del modelo en el diccionario de predicciones de OpenWakeWord
# Es el nombre del archivo sin extension
MODEL_KEY = os.path.splitext(os.path.basename(MODEL_PATH))[0]

# Mensaje que se envia a Unity cuando se detecta el wake word
WAKE_WORD_DETECTED_MESSAGE = "WAKE_WORD_DETECTED"

# Tiempo minimo entre detecciones (en segundos) para evitar activaciones 
# multiples por el mismo evento de audio
MIN_SECONDS_BETWEEN_DETECTIONS = 2.0

class WakeWordListener:
    """
    Escucha el microfono y notifica a Unity al detectar ARIA
    
    Implementa un servidor WebSocket al que Unity se conecta.
    Cuando OpenWakeWord detecta la palabra de activacion,
    envia WAKE_WORD_DETECTED a todos los clientes conectados.
    
    Attributes:
        _model: modelo de OpenWakeWord cargado en memoria.
        _audio: instancia de PyAudio para acceso al microfono.
        _connected_clients: conjunto de clientes WebSocket activos.
        _last_detection_time: timestamp de la ultima deteccion.
    """

    def __init__(self) -> None:
        """
        Inicializa el listener cargando el modelo wake word.
        
        La carga del modelo ocurre una sola vez al instanciar.
        """
        logger.info(f"Cargando modelo de wake word: '{WAKE_WORD_MODEL}'")

        self._model = Model(
            wakeword_models=[MODEL_PATH],
            inference_framework="onnx",
        )

        self._audio = pyaudio.PyAudio()
        self._connected_clients: set = set()
        self._last_detection_time: float = 0.0

        logger.info("Modelo cargado correctamente.")

    async def start(self) -> None:
        """
        Inicia el servidor WebSocket y el listener del microfono.

        Arranca dos tareas concurrentes:
        - El servidor WebSocket esperando conexiones de Unity
        - El listener del microfono procesando audio

        Returns:
            None.
        """
        logger.info(
            f"Iniciando servidor WebSocket en "
            f"ws://{WEBSOCKET_HOST}:{WEBSOCKET_PORT}"
        )

        # Inicia servidor WebSocket y listener del microfono
        # de forma concurrente
        async with websockets.serve(
            self._handle_unity_connection,
            WEBSOCKET_HOST,
            WEBSOCKET_PORT,
        ):
            logger.info("Servidor WebSocket activo. Esperando Unity...")
            await self._listen_microphone()

    async def _handle_unity_connection(
        self,
        websocket: websockets.WebSocketServerProtocol,
    ) -> None:
        """
        Maneja la conexion de un cliente Unity.
        
        Registra el cliente al conectarse y lo elimina
        al desconectarse. Mantiene la conexion abierta
        mientras Unity este activo.

        Args:
            websocket: conexion WebSocket del cliente Unity.

        Returns:
            None.
        """
        client_address = websocket.remote_address
        self._connected_clients.add(websocket)

        logger.info(f"Unity conectado desde: {client_address}.")
        logger.info(f"Clientes activos: {len(self._connected_clients)}")

        try:
            # Mantener la conexion abierta hasta que Unity se desconecte
            await websocket.wait_closed()
        finally:
            self._connected_clients.discard(websocket)
            logger.info(f"Unity desconectado: {client_address}")
            logger.info(f"Clientes activos: {len(self._connected_clients)}")

    async def _listen_microphone(self) -> None:
        """
        Escucha el microfono continuamente y procesa el audio con OpenWakeWord.
        
        Lee chunks de audio del microfono continuamente, y los procesa con
        OpenWakeWord. Si la confianza supera el umbral y ha pasado
        suficiente tiempo desde la ultima deteccion, notifica a Unity.

        Retrurns:
            None.
        """
        stream = self._audio.open(
            rate=SAMPLE_RATE,
            channels=AUDIO_CHANNELS,
            format=AUDIO_FORMAT,
            input=True,
            frames_per_buffer=CHUNK_SIZE,
            input_device_index=MICROPHONE_INDEX,
        )

        logger.info(f"Microfono activo. Umbral de deteccion: {WAKE_WORD_THRESHOLD}")
        logger.info(f"Escuchando... Di la palabra de activacion.")

        try:
            while True:
                # Leer chunk de audio del microfono
                audio_chunk = stream.read(
                    CHUNK_SIZE,
                    exception_on_overflow=False,
                )

                # Convertir bytes a array numpy de int16
                # OpenWakeWord requiere este formato
                audio_array = np.frombuffer(audio_chunk, dtype=np.int16)

                # Procesar el chunk con el modelo de OpenWakeWord
                # prediction es un dict con la confianza de cada modelo
                prediction = self._model.predict(audio_array)

                # Verificar si la confianza supera el umbral
                confidence = prediction.get(MODEL_KEY, 0.0)

                if self._should_trigger(confidence):
                    await self._notify_all_clients(confidence)

                # Ceder el control al event loop para que el
                # servidor WebSocket pueda procesar conexiones
                # mientras escuhamos el microfono
                await asyncio.sleep(0)
        
        finally:
            stream.stop_stream()
            stream.close()

    def _should_trigger(self, confidence: float) -> bool:
        """
        Determina si la deteccion debe activar una notificacion.
        
        Verifica dos condiciones:
        1. La confianza supera el umbral configurado.
        2. Han pasado al menos MIN_SECONDS_BETWEEN_DETECTIONS
            desde la ultima deteccion. Esto evita multiples activaciones.

        Args:
            confidence: nivel de confianza de la deteccion actual.

        Returns:
            True si se debe notificar a Unity, False si no.
        """
        import time

        if confidence < WAKE_WORD_THRESHOLD:
            return False
        
        current_time = time.time()
        seconds_since_last = current_time - self._last_detection_time

        if seconds_since_last < MIN_SECONDS_BETWEEN_DETECTIONS:
            return False
        
        self._last_detection_time = current_time
        return True

    async def _notify_all_clients(self, confidence: float) -> None:
        """
        Notifica a todos los clientes conectados.
        
        Envia WAKE_WORD_DETECTED a cada cliente activo.
        Si un cliente fallo, lo elimina del conjunto sin
        interrumpir la notificacion al resto.

        Args:
            confidence: nivel de confianza de la deteccion (0.0 a 1.0)
        
        Returns:
            None.
        """
        if not self._connected_clients:
            logger.warning(
                "Wake word detectado pero Unity no esta conectado."
            )
            return

        logger.info(
            f"Wake word detectado con confianza: {confidence:.3f}. "
            f"Notificando a {len(self._connected_clients)} cliente(s)..."
        )

        # Nofificar a todos los clientes conectados
        disconnected_clients = set()

        for client in self._connected_clients:
            try:
                await client.send(WAKE_WORD_DETECTED_MESSAGE)
            except websockets.exceptions.ConnectionClosed:
                disconnected_clients.add(client)
        
        # Limpiear clientes desconectados
        self._connected_clients -= disconnected_clients

    def cleanup(self) -> None:
        """
        Libera los recursos de audio al cerrar el proceso.
        
        Returns:
            None.
        """
        self._audio.terminate()
        logger.info("Recursos de audio liberados.")
