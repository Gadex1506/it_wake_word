# it_wake_word

Módulo de detección de palabra clave **"Mia"** basado en [OpenWakeWord](https://github.com/dscripka/openWakeWord), diseñado como microservicio para integrarse con un asistente virtual de domótica. Cuando el sistema detecta la palabra clave, envía `WAKE_WORD_DETECTED` por WebSocket a Unity para que inicie la grabación del comando de voz.

---

## 📋 Requisitos previos

- Python **3.13.3**
- Micrófono funcional conectado al sistema
- Git instalado

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/Gadex1506/it_wake_word.git
cd it_wake_word
```

### 2. Crear el entorno virtual

```bash
# Windows
python -m venv venv

# Mac/Linux
python3 -m venv venv
```

### 3. Activar el entorno virtual

```bash
# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate
```

### 4. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 5. Configurar variables de entorno

Copia el archivo de ejemplo y ajusta los valores. Un valor vacío usa el valor por defecto.

```bash
cp .env.example .env
```

| Variable | Por defecto | Descripción |
|---|---|---|
| `WAKE_WORD_MODEL` | `meeah` | Nombre de un `.onnx` en `models/` (sin extensión) o ruta completa. |
| `WAKE_WORD_THRESHOLD` | `0.5` | Umbral de detección (0–1). Más alto = menos falsos positivos. |
| `WAKE_WORD_PATIENCE` | `1` | Frames consecutivos (80 ms) sobre el umbral para confirmar. |
| `ENERGY_GATE_RMS` | `0` (off) | Nivel RMS bajo el cual no se ejecuta el modelo. Ver *Optimización*. |
| `UNITY_SOCKET_HOST` / `UNITY_SOCKET_PORT` | `127.0.0.1` / `9000` | Dónde escucha el servidor WebSocket. |
| `MICROPHONE_INDEX` | `None` | Índice del micrófono. Ver `python -m scripts.list_microphones`. |

---

## 🧪 Cómo probar el proyecto

Para probar el funcionamiento completo necesitas **dos terminales abiertas** al mismo tiempo.

### Terminal 1 — Iniciar el servicio de detección

```bash
python main.py
```

Espera hasta que aparezca el siguiente mensaje antes de continuar:

```
[INFO] it_wake_word: Escuchando... Di la palabra de activacion.
```

### Terminal 2 — Ejecutar el simulador de prueba

```bash
python tests/manual/test_wake_word_flow.py
```

### 🗣️ Di "Mia" frente al micrófono

Cuando el sistema detecte la palabra clave, en la **Terminal 2** aparecerá:

```
INFO:Unity_Simulator:Mensaje recibido de it_wake_word: 'WAKE_WORD_DETECTED'
```

> ⏳ Tras cada detección el servicio ignora nuevas activaciones durante **2 segundos**.

Para detener cada proceso presiona `Ctrl + C`.

### Tests automáticos

No requieren micrófono:

```bash
python -m unittest discover -s tests -t . -v
```

---

## ⚙️ Optimización

El servicio está pensado para equipos de gama media y para convivir con Unity y otros servicios.

- **Ring buffer** (`openwakeword_tuning.py`): evita que OpenWakeWord copie 10 s de audio por cada chunk de 80 ms (~47 % menos CPU en estado estable, resultados idénticos).
- **Arranque ligero**: se evita importar `sklearn`/`scipy`, que OpenWakeWord carga sin usarlos (~1.5 s y decenas de MB menos).
- **Captura en hilo aparte**: la lectura del micrófono ya no bloquea el servidor WebSocket.
- **Prioridad baja del proceso**, para no competir con Unity.
- **Compuerta de energía** (opcional): en silencio no se ejecuta el modelo.

### Calibrar la compuerta de energía

1. Con el servicio apagado y el cuarto en silencio, mide el ruido ambiente; con tu voz hablando normal, mide los picos.
2. Elige `ENERGY_GATE_RMS` claramente por encima del ruido máximo y por debajo de tu voz (en un equipo medido: ruido ≤ 1400, voz 5000–10000 → `2000`).
3. Si el asistente deja de responder a voz suave o lejana, baja el valor o ponlo en `0`.

### Elegir el micrófono

```bash
python -m scripts.list_microphones
```

La columna `16k` indica si el dispositivo acepta el formato del servicio. Los dispositivos virtuales (p. ej. SteelSeries Sonar) funcionan pero añaden una capa de procesamiento; si hay un micrófono físico con `si`, ponlo en `MICROPHONE_INDEX`. Los dispositivos WASAPI no aceptan 16 kHz.

---

## 📁 Estructura del proyecto

```
it_wake_word/
├── main.py                       # Punto de entrada: logging, prioridad, apagado ordenado
├── wake_word/                    # Paquete del servicio
│   ├── config.py                 #   Lectura y validación del .env
│   ├── wake_word_listener.py     #   Servidor WebSocket + hilo de captura
│   ├── detector.py               #   Umbral, patience, debounce y compuerta de energía
│   ├── microphone.py             #   Acceso al micrófono (PyAudio)
│   └── openwakeword_tuning.py    #   Ajustes de rendimiento sobre OpenWakeWord
├── scripts/                      # Utilidades (se ejecutan con python -m scripts.<nombre>)
│   └── list_microphones.py       #   Elegir MICROPHONE_INDEX
├── tests/
│   ├── test_*.py                 #   Tests unitarios (sin micrófono)
│   └── manual/                   #   Pruebas manuales y diagnósticos
│       └── test_wake_word_flow.py#     Simulador del cliente Unity
├── models/                       # Modelos .onnx de wake word (versionados)
├── requirements.txt              # Dependencias directas del servicio
├── .env.example                  # Plantilla de variables de entorno
└── README.md
```

---

## 🌐 Contexto del proyecto

Este módulo forma parte de un sistema mayor de asistente virtual para una **casa domótica**. Su responsabilidad es escuchar continuamente el audio del micrófono y notificar al asistente cuando se pronuncie la palabra clave *Mia*, momento en el cual el asistente iniciará la grabación y procesamiento del comando del usuario.

---

## 👥 Equipo

Proyecto desarrollado en la **Fundación Universitaria Konrad Lorenz** como parte del proyecto de grado - INCLUSIVE_TECH.
