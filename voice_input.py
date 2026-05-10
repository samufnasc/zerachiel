import speech_recognition as sr
try:
    from config import VOICE_LANGUAGE, LISTEN_TIMEOUT
except ImportError:
    # Caso falte no config, o sistema não trava
    VOICE_LANGUAGE = "pt-BR"
    LISTEN_TIMEOUT = 10

def listen():
    recognizer = sr.Recognizer()
    with sr.Microphone() as source:
        try:
            # Ajusta para o ruído ambiente
            recognizer.adjust_for_ambient_noise(source, duration=0.5)
            # Ouve com o timeout definido
            audio = recognizer.listen(source, timeout=LISTEN_TIMEOUT, phrase_time_limit=10)
            text = recognizer.recognize_google(audio, language=VOICE_LANGUAGE)
            return text
        except sr.WaitTimeoutError:
            return None
        except Exception:
            return None