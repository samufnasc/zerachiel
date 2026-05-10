# ============================================================
# config.py — Configurações Centrais do Zerachiel
# ============================================================

import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env (nunca comite o .env no git)
load_dotenv()

# ─────────────────────────────────────────────
# Identidade do Assistente
# ─────────────────────────────────────────────
ASSISTANT_NAME  = "Zerachiel"
VOICE_LANGUAGE  = "pt-BR"

# ─────────────────────────────────────────────
# Wake Words — palavras/frases que ativam o assistente
# IMPORTANTE: todas em minúsculas; a comparação usa .lower()
# Adicione variações para aumentar a taxa de reconhecimento
# ─────────────────────────────────────────────
WAKE_WORDS = [
    "zerachiel",                    # nome direto
    "olá assistente",               # ← CORRIGIDO: estava faltando
    "oi assistente",                # variação informal
    "olá zerachiel",                # nome + saudação
    "oi zerachiel",                 # variação informal
    "ei zerachiel",                 # variação coloquial
    "hey zerachiel",                # variação em inglês comum
    "olá assistente zerachiel",     # frase completa original
    "olá assistente iniciar",       # frase original alternativa
]

# Resposta ao ser ativado por wake word
WAKE_RESPONSE = "Estou aqui. O que deseja?"

# ─────────────────────────────────────────────
# Configurações de Captura de Voz
# ─────────────────────────────────────────────
# Segundos de silêncio que indicam fim do turno de fala.
# 1.8s = equilibrado (não muito sensível, não muito lento)
# Reduza para 1.2s se o ambiente for silencioso.
# Aumente para 2.5s se o assistente cortar sua fala com frequência.
PAUSE_THRESHOLD = 1.8

# Tempo máximo esperando o usuário COMEÇAR a falar (segundos).
# Após esse tempo sem fala, o listen() retorna None e o loop continua.
LISTEN_TIMEOUT = 8

# Teto de segurança: gravação máxima por turno (segundos).
# Não é um corte fixo — só evita gravação infinita em casos de falha.
PHRASE_TIME_LIMIT = 120

# Segundos de inatividade sem fala antes de o assistente voltar a "dormir"
SLEEP_AFTER_IDLE = 120  # 2 minutos

# ─────────────────────────────────────────────
# Comandos de Interrupção (param a fala imediatamente)
# ─────────────────────────────────────────────
INTERRUPT_PHRASES = [
    "certo assistente",
    "pode parar",
    "pare",
    "chega",
    "silêncio",
    "stop",
    "para",
    "interromper",
]

# ─────────────────────────────────────────────
# Comandos de Pausa (param a fala mas mantêm o assistente acordado)
# ─────────────────────────────────────────────
PAUSE_PHRASES = [
    "espera",
    "espere",
    "aguarda",
    "aguarde",
    "um momento",
    "pausa",
    "calma",
]

RESUME_PHRASES = [
    "pode continuar",
    "continue",
    "prossiga",
    "vai",
    "ok continue",
]

# ─────────────────────────────────────────────
# Motor de IA
# ─────────────────────────────────────────────
AI_ENGINE      = "groq"                  # "groq" ou "ollama"
GROQ_API_KEY   = os.getenv("GROQ_API_KEY")
GROQ_MODEL     = "llama-3.1-8b-instant"  # rápido e gratuito
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL   = "llama3.2"

# ─────────────────────────────────────────────
# Sandbox de Arquivos
# ─────────────────────────────────────────────
BASE_SANDBOX = os.path.join(os.path.expanduser("~"), "AssistantFiles")
if not os.path.exists(BASE_SANDBOX):
    os.makedirs(BASE_SANDBOX)

# Pastas permitidas para o file_manager (além do sandbox padrão)
ALLOWED_DIRS = {
    "documentos":        os.path.join(os.path.expanduser("~"), "Documents"),
    "documents":         os.path.join(os.path.expanduser("~"), "Documents"),
    "desktop":           os.path.join(os.path.expanduser("~"), "Desktop"),
    "área de trabalho":  os.path.join(os.path.expanduser("~"), "Desktop"),
    "downloads":         os.path.join(os.path.expanduser("~"), "Downloads"),
    "sandbox":           BASE_SANDBOX,
}

# ─────────────────────────────────────────────
# Definição de Ferramentas (Tools / Function Calling)
# ─────────────────────────────────────────────
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": (
                "Busca informações em tempo real na internet. "
                "Use quando o usuário perguntar sobre eventos recentes, notícias, "
                "preços, dados atuais ou qualquer coisa que exija informação atualizada."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "O termo ou pergunta a ser pesquisado"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "file_manager",
            "description": (
                "Gerencia arquivos no computador do usuário. "
                "Use quando o usuário pedir para salvar, criar, ler, editar, "
                "copiar ou listar arquivos. Também use para salvar a última resposta "
                "do assistente em um arquivo de texto."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["create", "read", "list", "edit", "append", "save_last_response"],
                        "description": (
                            "Ação a executar: "
                            "create=criar novo arquivo, "
                            "read=ler conteúdo, "
                            "list=listar arquivos da pasta, "
                            "edit=sobrescrever conteúdo existente, "
                            "append=adicionar ao final do arquivo, "
                            "save_last_response=salvar última resposta do assistente"
                        )
                    },
                    "filename": {
                        "type": "string",
                        "description": "Nome do arquivo com extensão (ex: 'resumo.txt', 'notas.md')"
                    },
                    "content": {
                        "type": "string",
                        "description": "Conteúdo a escrever no arquivo (para create, edit e append)"
                    },
                    "directory": {
                        "type": "string",
                        "description": (
                            "Pasta de destino. Valores aceitos: "
                            "'documentos', 'desktop', 'downloads', 'sandbox' (padrão). "
                            "Também aceita caminhos absolutos dentro das pastas permitidas."
                        )
                    }
                },
                "required": ["action", "filename"]
            }
        }
    }
]

# ─────────────────────────────────────────────
# Prompt do Sistema (personalidade do Zerachiel)
# ─────────────────────────────────────────────
SYSTEM_PROMPT = (
    f"Você é o {ASSISTANT_NAME}, um assistente de voz pessoal inteligente, "
    "prestativo e conciso. Sempre responda em português do Brasil. "
    "Suas respostas devem ser claras e diretas — evite respostas excessivamente longas. "
    "Quando o conteúdo for código ou texto extenso, avise que está exibindo na tela. "
    "Use a ferramenta web_search sempre que precisar de dados atuais ou em tempo real. "
    "Use a ferramenta file_manager quando o usuário pedir para salvar, criar ou ler arquivos."
)
