"""
Assistente de I.A. com comandos de voz e resposta interativa.
Ponto de entrada principal.
"""

from voice_input import listen
from voice_output import VoiceOutput
from ai_engine import AIEngine
from config import (
    WAKE_WORD,
    WAKE_RESPONSE,
    ASSISTANT_NAME,
    SHOW_TEXT_RESPONSE,
    SMART_TEXT_DISPLAY,
    TEXT_REQUEST_KEYWORDS,
)
import sys
import msvcrt
import input_helper

def main():
    # --- BLOCO DE INTERFACE INICIAL ---
    # Exibe o cabeçalho no console e as instruções de uso para o usuário
    print("=" * 50)
    print(f"  {ASSISTANT_NAME} — Assistente por Voz e Texto")
    print("=" * 50)
    print(f'\n  Para ativar, diga: "{WAKE_WORD}" ou DIGITE aqui.')
    print('  Diga "sair" ou "encerrar" para sair.')
    print('  Pressione "P" ou diga "certo assistente" para interromper a resposta.')
    if SMART_TEXT_DISPLAY:
        print("  Diga 'mostre o texto' ou 'exiba o código' para ver respostas na tela.")
    print("=" * 50)

    # --- INICIALIZAÇÃO DOS COMPONENTES ---
    # Instancia os motores de voz e inteligência artificial
    voice = VoiceOutput()
    ai = AIEngine()

    # --- BOAS-VINDAS ---
    # O assistente se apresenta vocalmente ao iniciar
    voice.speak(WAKE_RESPONSE)
    voice.wait()

    # --- LOOP PRINCIPAL DE EXECUÇÃO ---
    while True:
        # 1. ENTRADA VIA TECLADO (Não-bloqueante)
        # Tenta capturar o que o usuário digita sem travar o programa
        text = input_helper.get_input()

        # 2. ENTRADA VIA VOZ (Bloqueante por timeout)
        # Se não houver texto, abre o microfone para ouvir o usuário
        if not text:
            text = listen()

        # Se nada foi detectado (silêncio ou sem digitação), volta ao início do loop
        if not text:
            continue

        # Padroniza a entrada para facilitar a comparação de comandos
        text = text.strip().lower()

        # --- CONTROLE DE SAÍDA ---
        # Verifica se o usuário deseja fechar o programa
        if text in ("sair", "encerrar"):
            VoiceOutput.stop()
            voice.speak("Até mais! Tenha um ótimo dia.")
            voice.wait()
            break

        # --- COMANDO DE INTERRUPÇÃO ---
        # Permite parar a fala do assistente imediatamente via voz
        interrupt_keywords = ("pausar", "pare", "não quero ouvir", "chega")
        if text in interrupt_keywords:
            VoiceOutput.stop()
            print("[Interrupção detectada] Silenciando resposta. O que mais?")
            continue

        # --- ANALISE DE PREFERÊNCIA DE EXIBIÇÃO ---
        # Identifica se o usuário pediu para ver o texto na tela através de palavras-chave
        user_wants_text = any(kw in text for kw in TEXT_REQUEST_KEYWORDS)

        # --- PROCESSAMENTO PELA IA ---
        # Envia o comando para o ai_engine decidir se responde ou usa ferramentas (Web Search)
        print(f"\n[Processando: '{text}']")
        spoken_text, display_text = ai.process(text)

        # --- LÓGICA DE EXIBIÇÃO INTELIGENTE ---
        # Define se a resposta deve aparecer no console (casos de código ou solicitação direta)
        has_code = ai.detect_code_content(display_text or spoken_text)
        should_display = SHOW_TEXT_RESPONSE and (
            SMART_TEXT_DISPLAY
            and (user_wants_text or has_code or display_text)
        )

        # --- EXECUÇÃO DA RESPOSTA DE VOZ ---
        # Garante que qualquer áudio anterior pare antes de começar a nova resposta
        VoiceOutput.stop()
        voice.speak(spoken_text)

        # Aguarda a finalização da fala (limite de 120 segundos)
        completed = voice.wait(timeout=120)

        # --- NOTIFICAÇÃO DE CÓDIGO ---
        # Se houver código na tela, o assistente avisa vocalmente após terminar a frase principal
        if completed and should_display and has_code:
            VoiceOutput.stop()
            voice.speak_code_notification()
            voice.wait(timeout=30)

        # --- EXIBIÇÃO NO CONSOLE ---
        # Imprime a resposta formatada se a lógica de exibição for positiva
        if should_display:
            print("-" * 40)
            print(ai.format_display_text(spoken_text, display_text))
            print("-" * 40)

        # --- GESTÃO DE MEMÓRIA ---
        # Salva a interação no histórico para que a IA tenha contexto na próxima pergunta
        ai.add_to_history(text, spoken_text)

    # --- FINALIZAÇÃO ---
    print(f"\n{ASSISTANT_NAME} encerrado.")
    sys.exit(0)

if __name__ == "__main__":
    main()