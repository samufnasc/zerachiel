import os
from dotenv import load_dotenv

# Carrega as variáveis do arquivo .env
load_dotenv()

# --- Identidade do Assistente ---
ASSISTANT_NAME = "Zerachiel"
VOICE_LANGUAGE = "pt-BR"

# --- Configurações de Voz e Ativação ---
# No seu config.py, mude/adicione estas linhas:
WAKE_WORDS = ["olá assistente zerachiel", "olá assistente iniciar", "zerachiel"]
WAKE_RESPONSE = "Olá! Eu sou {ASSISTANT_NAME}. Como posso ajudar você hoje?"
LISTEN_TIMEOUT = 10
SILENCE_THRESHOLD = 0.5

# --- Motor de IA ---
AI_ENGINE = "groq" # ou 'ollama'
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = "llama-3.1-8b-instant"

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = "llama3.2"

# --- Sandbox de Arquivos ---
BASE_SANDBOX = os.path.join(os.path.expanduser("~"), "AssistantFiles")
if not os.path.exists(BASE_SANDBOX):
    os.makedirs(BASE_SANDBOX)

# --- Definição de Ferramentas (Tools) ---
TOOLS_DEFINITION = [
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Busca informações em tempo real na internet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "O termo de busca"}
                },
                "required": ["query"]
            }
        }
    }
]

# --- Prompt do Sistema ---
SYSTEM_PROMPT = (
    f"Você é o {ASSISTANT_NAME}, um assistente de voz prestativo e conciso. "
    "Responda de forma clara e direta em português do Brasil. "
    "Use a ferramenta web_search sempre que precisar de dados atuais."
)