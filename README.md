# it_wake_word

Módulo de detección de palabra clave **"Nova"** basado en [OpenWakeWord](https://github.com/dscripka/openWakeWord), diseñado como microservicio para integrarse con un asistente virtual de domótica. Cuando el sistema detecta la palabra clave *Nova*, envía una señal al asistente para que inicie la grabación del comando de voz.

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

Copia el archivo de ejemplo y completa los valores:

```bash
cp .env.example .env
```

Edita el archivo `.env` con tus propios valores.

---

## 🧪 Cómo probar el proyecto

Para probar el funcionamiento completo necesitas **dos terminales abiertas** al mismo tiempo.

---

### Terminal 1 — Iniciar el servicio de detección

```bash
python main.py
```

Espera hasta que aparezca el siguiente mensaje antes de continuar:

```
[INFO] it_wake_word: Escuchando... Di la palabra de activacion.
```

---

### Terminal 2 — Ejecutar el simulador de prueba

Una vez que la Terminal 1 esté lista, abre la segunda terminal y ejecuta:

```bash
python test_wake_word_flow.py
```

Espera hasta que aparezca el siguiente mensaje en esta terminal:

```
INFO:Unity_Simulator:Di 'Nova' frente al micrófono
```

---

### 🗣️ Di "Nova" frente al micrófono

Cuando el sistema detecte correctamente la palabra clave, en la **Terminal 2** deberán aparecer los siguientes mensajes:

```
INFO:Unity_Simulator:Mensaje recibido de it_wake_word: 'WAKE_WORD_DETECTED'
INFO:Unity_Simulator:Wake word detectado. Unity iniciaria grabacion del comando aqui.
```

> ⏳ **Importante:** Después de cada detección exitosa, espera **2 segundos** antes de volver a decir "Nova". Esto evita saturar el detector de OpenWakeWord.

---

### ⛔ Finalizar la ejecución

Para detener el proceso en **cada terminal**, presiona:

```
Ctrl + C
```

---

## 📁 Estructura del proyecto

```
it_ai_assistant/
├── main.py                  # Punto de entrada del servicio
├── test_wake_word_flow.py   # Simulador de prueba
├── wake_word_listener.py    # Deteccion de palabra de activacion
├── requirements.txt         # Dependencias del proyecto
├── .env.example             # Plantilla de variables de entorno
├── .gitignore
└── README.md
```

---

## 🌐 Contexto del proyecto

Este módulo forma parte de un sistema mayor de asistente virtual para una **casa domótica**. Su responsabilidad es escuchar continuamente el audio del micrófono y notificar al asistente cuando se pronuncie la palabra clave *Nova*, momento en el cual el asistente iniciará la grabación y procesamiento del comando del usuario.

---

## 👥 Equipo

Proyecto desarrollado en la **Fundación Universitaria Konrad Lorenz** como parte del proyecto de grado — INCLUSIVE_TECH.