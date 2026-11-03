# list_microphones.py
# =====================================================
# Lista los dispositivos de entrada de audio para elegir el
# valor de MICROPHONE_INDEX en el .env.
#
# Uso (desde la raiz del proyecto):  python -m scripts.list_microphones
#
# La columna "16k" indica si el dispositivo acepta el formato
# que necesita el servicio (16 kHz, mono, int16). Un dispositivo
# virtual (p. ej. SteelSeries Sonar) funciona, pero obliga a
# Windows a procesar el audio por una capa extra; si hay un
# microfono fisico con "si", suele ser mejor opcion.
# =====================================================

import pyaudio

from wake_word.config import SAMPLE_RATE


def accepts_format(audio: pyaudio.PyAudio, index: int) -> bool:
    try:
        return audio.is_format_supported(
            SAMPLE_RATE,
            input_device=index,
            input_channels=1,
            input_format=pyaudio.paInt16,
        )
    except ValueError:
        return False


def main() -> None:
    audio = pyaudio.PyAudio()
    try:
        default_index = audio.get_default_input_device_info()["index"]
    except OSError:
        default_index = None

    print(f"{'idx':>3}  {'16k':<3}  {'defecto':<7}  {'API':<22} {'Hz':>6}  nombre")
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        if info["maxInputChannels"] < 1:
            continue
        api = audio.get_host_api_info_by_index(info["hostApi"])["name"]
        print(
            f"{i:>3}  {'si' if accepts_format(audio, i) else 'no':<3}  "
            f"{'*' if i == default_index else '':<7}  {api:<22} "
            f"{int(info['defaultSampleRate']):>6}  {info['name']}"
        )
    audio.terminate()


if __name__ == "__main__":
    main()
