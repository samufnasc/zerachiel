# ============================================================
# voice_output.py — Síntese de Voz (Zerachiel)
# Usa edge-tts (Microsoft Neural TTS) + pygame para reprodução.
#
# NOVIDADE v3:
#   speak_raw(text, stop_event) — permite que main_gui.py
#   interrompa a fala a qualquer momento via threading.Event,
#   possibilitando a funcionalidade de pausa durante respostas longas.
# ============================================================

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
    """
    TTS usando edge-tts com suporte a:
    - Interrupção total (stop)
    - Pausa controlada por stop_event externo (speak_raw)
    - Limpeza de markdown para fala natural
    """

    _is_speaking        = False
    _interrupt_requested = False
    _listener_stop      = threading.Event()

    def __init__(self):
        # pt-BR-AntonioNeural: voz masculina natural, séria e clara.
        # Alternativas masculinas disponíveis no Edge TTS:
        #   pt-BR-AntonioNeural  (recomendada — voz principal do projeto)
        #   pt-BR-FabioNeural    (mais grave, mais formal)
        # Para voltar para feminina: pt-BR-FranciscaNeural
        self.voice = "pt-BR-AntonioNeural"
        self.temp_file = os.path.join(tempfile.gettempdir(), "zerachiel_voice.mp3")

        if not pygame.mixer.get_init():
            pygame.mixer.init()

        logger.info(f"VoiceOutput inicializado. Voz: {self.voice}")
        print(f"[Voz] Usando edge-tts: {self.voice} (masculina)")

    # ──────────────────────────────────────────────────────────
    # Limpeza de Texto para Fala
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def clean_speech_text(text: str) -> str:
        """
        Remove elementos de markdown/código que soariam estranhos em voz:
        blocos de código, negrito, itálico, links, tabelas, etc.
        """
        # Remove blocos de código (``` ... ```)
        text = re.sub(r"```[\s\S]*?```", " [código exibido na tela] ", text)
        # Remove código inline (`...`)
        text = re.sub(r"`([^`]+)`", r"\1", text)
        # Remove negrito e itálico (**texto**, *texto*)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
        text = re.sub(r"\*([^*]+)\*", r"\1", text)
        # Remove linhas de tabela markdown (|---|)
        text = re.sub(r"\|[\s\-:|]+\|", "", text)
        text = re.sub(r"\|", " ", text)
        # Remove cabeçalhos markdown (#, ##, ###)
        text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
        # Remove marcadores de lista (-, *, •)
        text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)
        # Remove links [texto](url) → mantém só o texto
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        # Normaliza múltiplas quebras de linha em pausa natural
        text = re.sub(r"\n{2,}", ". ", text)
        # Normaliza espaços extras
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # ──────────────────────────────────────────────────────────
    # Geração de Áudio (async edge-tts)
    # ──────────────────────────────────────────────────────────

    def _generate_audio(self, text: str) -> str | None:
        """
        Gera o áudio MP3 via edge-tts e retorna o caminho do arquivo.

        CORREÇÃO Permission denied (Windows):
        - Sempre faz unload+stop do pygame antes de tentar escrever.
        - Usa um arquivo temporário com nome único por chamada (uuid4)
          para evitar conflito quando a reprodução anterior ainda está
          segurando o handle do arquivo no sistema operacional.
        - Remove o arquivo anterior após garantir que não está em uso.

        Retorna o caminho do arquivo gerado, ou None em caso de erro.
        """
        import uuid

        # ── Garante que o pygame liberou qualquer arquivo anterior ──
        try:
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
                pygame.mixer.music.unload()
        except Exception:
            pass

        # Remove arquivo anterior se ainda existir (liberado pelo unload)
        if os.path.exists(self.temp_file):
            try:
                os.remove(self.temp_file)
            except Exception:
                pass  # se ainda estiver bloqueado, usaremos um novo nome abaixo

        # Gera nome de arquivo único para esta chamada
        temp_path = os.path.join(
            tempfile.gettempdir(),
            f"zerachiel_{uuid.uuid4().hex[:8]}.mp3"
        )

        async def _run():
            communicate = edge_tts.Communicate(text, self.voice)
            await communicate.save(temp_path)

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(_run())
            loop.close()
            self.temp_file = temp_path   # atualiza referência para limpeza futura
            return temp_path
        except Exception as e:
            logger.error(f"Erro ao gerar áudio TTS: {e}")
            return None

    # ──────────────────────────────────────────────────────────
    # speak() — Método original com listeners próprios
    # Mantido para compatibilidade com chamadas diretas (greet, etc.)
    # ──────────────────────────────────────────────────────────

    def speak(self, text: str):
        """
        Gera e reproduz o áudio.
        Inicia listeners internos de interrupção (teclado + voz).
        Usado para falas simples onde não há escuta paralela externa.
        """
        if not text:
            return

        clean_text = self.clean_speech_text(text)
        if not clean_text:
            return

        VoiceOutput._is_speaking         = True
        VoiceOutput._interrupt_requested = False

        # Inicia listeners internos (teclado P e voz "pare")
        self._start_listeners()

        try:
            audio_path = self._generate_audio(clean_text)
            if not audio_path:
                return

            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

            # Aguarda fim da reprodução ou interrupção
            while pygame.mixer.music.get_busy():
                if VoiceOutput._interrupt_requested:
                    pygame.mixer.music.stop()
                    break
                time.sleep(0.05)

            try:
                pygame.mixer.music.unload()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Erro ao reproduzir voz: {e}")
        finally:
            VoiceOutput._is_speaking = False
            self._stop_listeners()

    # ──────────────────────────────────────────────────────────
    # speak_raw() — NOVO: controlado por stop_event externo
    # Chamado por main_gui.py para permitir pausa durante fala longa
    # ──────────────────────────────────────────────────────────

    def speak_raw(self, text: str, stop_event: threading.Event = None):
        """
        Versão de speak() controlada externamente via stop_event.
        Usada por speak_with_listener() em main_gui.py para pausa e
        interrupção durante respostas longas.

        Não inicia listeners internos — a thread externa em main_gui.py
        cuida de escutar por comandos enquanto o áudio toca.

        Args:
            text:       Texto a ser falado (pode conter markdown — será limpo).
            stop_event: threading.Event controlado externamente.
                        Quando setado, a reprodução para imediatamente.
        """
        if not text:
            return

        clean_text = self.clean_speech_text(text)
        if not clean_text:
            return

        if stop_event and stop_event.is_set():
            return  # já foi cancelado antes de começar

        VoiceOutput._is_speaking         = True
        VoiceOutput._interrupt_requested = False

        try:
            audio_path = self._generate_audio(clean_text)
            if not audio_path:
                return

            if stop_event and stop_event.is_set():
                return  # cancelado durante a geração do áudio

            pygame.mixer.music.load(audio_path)
            pygame.mixer.music.play()

            # Loop de reprodução — verifica stop_event a cada 50ms
            while pygame.mixer.music.get_busy():
                # Verifica interrupção externa (via stop_event)
                if stop_event and stop_event.is_set():
                    pygame.mixer.music.stop()
                    logger.debug("speak_raw: interrompido via stop_event.")
                    break
                # Verifica interrupção interna (tecla P ou voz nos listeners)
                if VoiceOutput._interrupt_requested:
                    pygame.mixer.music.stop()
                    logger.debug("speak_raw: interrompido via _interrupt_requested.")
                    break
                time.sleep(0.05)

            try:
                pygame.mixer.music.unload()
            except Exception:
                pass

        except Exception as e:
            logger.error(f"Erro em speak_raw: {e}")
        finally:
            VoiceOutput._is_speaking = False

    # ──────────────────────────────────────────────────────────
    # Controle de Reprodução
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def stop():
        """Para a reprodução imediatamente (interrupção total)."""
        VoiceOutput._interrupt_requested = True
        if pygame.mixer.get_init():
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
        logger.debug("VoiceOutput: reprodução interrompida.")

    @property
    def is_speaking(self) -> bool:
        return VoiceOutput._is_speaking

    # ──────────────────────────────────────────────────────────
    # Listeners Internos (teclado + voz) — para speak() simples
    # ──────────────────────────────────────────────────────────

    @staticmethod
    def _background_listener_voice():
        """Thread: escuta por comandos de voz de interrupção durante speak()."""
        import speech_recognition as sr
        recognizer = sr.Recognizer()
        recognizer.pause_threshold = 0.5

        with sr.Microphone() as source:
            while not VoiceOutput._listener_stop.is_set():
                try:
                    audio = recognizer.listen(source, timeout=0.5, phrase_time_limit=3)
                    text  = recognizer.recognize_google(audio, language="pt-BR").lower()
                    from config import INTERRUPT_PHRASES
                    if any(p in text for p in INTERRUPT_PHRASES):
                        VoiceOutput.stop()
                        break
                except Exception:
                    continue

    @staticmethod
    def _background_listener_keyboard():
        """Thread: escuta pela tecla P (ou 3) para interrupção durante speak()."""
        if sys.platform != "win32":
            return
        import msvcrt
        while not VoiceOutput._listener_stop.is_set():
            try:
                if msvcrt.kbhit():
                    key = msvcrt.getch().lower()
                    if key in [b"p", b"3"]:
                        VoiceOutput.stop()
                        break
            except Exception:
                pass
            time.sleep(0.05)

    def _start_listeners(self):
        """Inicia threads de listener internos para speak()."""
        VoiceOutput._listener_stop.clear()
        threading.Thread(target=self._background_listener_voice,    daemon=True).start()
        threading.Thread(target=self._background_listener_keyboard, daemon=True).start()

    def _stop_listeners(self):
        """Para as threads de listener internos."""
        VoiceOutput._listener_stop.set()

    # ──────────────────────────────────────────────────────────
    # Utilitários
    # ──────────────────────────────────────────────────────────

    def speak_code_notification(self):
        """Avisa por voz que há código sendo exibido na tela."""
        self.speak("Encontrei um código para você na tela.")
