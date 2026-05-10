import tempfile
import os
import re
import time
import sys
import threading
import asyncio
import edge_tts
import pygame
import logging
from config import ASSISTANT_NAME

logger = logging.getLogger("VoiceAssistant")

class VoiceOutput:
    """TTS usando edge-tts com suporte a interrupção e reprodução real."""

    _is_speaking = False
    _interrupt_requested = False
    _listener_thread = None
    _listener_stop = threading.Event()
    _keyboard_active = False

    def __init__(self):
        self.edge_tts = edge_tts
        self.asyncio = asyncio
        self.voice = "pt-BR-FranciscaNeural"
        self.temp_file = os.path.join(tempfile.gettempdir(), "zerachiel_voice.mp3")
        
        if not pygame.mixer.get_init():
            pygame.mixer.init()
            
        print(f"[Voz] Usando edge-tts: {self.voice}")

    @staticmethod
    def clean_speech_text(text):
        """Limpa texto para fala natural — remove markdown."""
        text = re.sub(r"```[\s\S]*?```", "", text)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        text = re.sub(r"\|[\s\-:|]+\|", "", text)
        text = re.sub(r"\|", "", text)
        text = re.sub(r"#", "", text)
        text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.MULTILINE)
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        text = re.sub(r"\n{2,}", ". ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def speak(self, text):
        """Gera o áudio e reproduz, permitindo interrupção."""
        if not text: return
        
        clean_text = self.clean_speech_text(text)
        VoiceOutput._is_speaking = True
        VoiceOutput._interrupt_requested = False
        
        # Inicia listeners de interrupção
        self.start_listeners()

        async def _generate():
            communicate = self.edge_tts.Communicate(clean_text, self.voice)
            await communicate.save(self.temp_file)

        try:
            # Gera o áudio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_generate())
            loop.close()

            # Reproduz
            pygame.mixer.music.load(self.temp_file)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if VoiceOutput._interrupt_requested:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.1)
                
            pygame.mixer.music.unload()
        except Exception as e:
            logger.error(f"Erro ao reproduzir voz: {e}")
        finally:
            VoiceOutput._is_speaking = False
            self.stop_listeners()

    @staticmethod
    def stop():
        """Para a reprodução imediatamente."""
        VoiceOutput._interrupt_requested = True
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()

    # --- Listeners (Mantendo sua lógica original) ---
    
    @staticmethod
    def _background_listener():
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        with sr.Microphone() as source:
            while not VoiceOutput._listener_stop.is_set():
                try:
                    audio = recognizer.listen(source, timeout=0.5, phrase_time_limit=2)
                    text = recognizer.recognize_google(audio, language="pt-BR").lower()
                    if "certo assistente" in text or "para" in text:
                        VoiceOutput.stop()
                        break
                except: continue

    @staticmethod
    def _background_keyboard():
        if sys.platform != "win32": return
        import msvcrt
        while not VoiceOutput._listener_stop.is_set():
            if msvcrt.kbhit():
                if msvcrt.getch().lower() in [b"3", b"p"]:
                    VoiceOutput.stop()
                    break
            time.sleep(0.05)

    def start_listeners(self):
        VoiceOutput._listener_stop.clear()
        threading.Thread(target=self._background_listener, daemon=True).start()
        threading.Thread(target=self._background_keyboard, daemon=True).start()

    def stop_listeners(self):
        VoiceOutput._listener_stop.set()

    def speak_code_notification(self):
        self.speak("Encontrei um código para você na tela.")