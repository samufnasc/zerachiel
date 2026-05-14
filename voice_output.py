# ============================================================
# voice_output.py — Síntese de Voz Estável (Zerachiel v3.5)
# ============================================================

import tempfile
import os
import re
import time
import threading
import asyncio
import edge_tts
import pygame
import logging
import uuid

logger = logging.getLogger("VoiceAssistant")

class VoiceOutput:
    _is_speaking = False

    def __init__(self):
        self.voice = "pt-BR-AntonioNeural"
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        logger.info(f"VoiceOutput pronto. Voz: {self.voice}")

    def _generate_audio(self, text):
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except: pass

        temp_path = os.path.join(tempfile.gettempdir(), f"z_{uuid.uuid4().hex[:6]}.mp3")

        async def _gen():
            comm = edge_tts.Communicate(text, self.voice)
            await comm.save(temp_path)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_gen())
            loop.close()
            return temp_path
        except Exception as e:
            logger.error(f"Erro TTS: {e}")
            return None

    def speak_raw(self, text, stop_event=None):
        if not text: return
        VoiceOutput._is_speaking = True
        
        try:
            path = self._generate_audio(text)
            if not path or (stop_event and stop_event.is_set()): return

            pygame.mixer.music.load(path)
            pygame.mixer.music.play()

            while pygame.mixer.music.get_busy():
                if stop_event and stop_event.is_set():
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.05)
            
            pygame.mixer.music.unload()
            try: os.remove(path)
            except: pass
        finally:
            VoiceOutput._is_speaking = False

    def speak(self, text):
        self.speak_raw(text)

    def stop(self):
        """Para a reprodução de áudio imediatamente."""
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
