import re
import requests
import logging
import json
from config import (
    ASSISTANT_NAME,
    AI_ENGINE,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    SYSTEM_PROMPT,
    TOOLS_DEFINITION
)

logger = logging.getLogger("VoiceAssistant")

class AIEngine:
    """
    Motor de IA do Zerachiel.
    Gerencia chamadas para Groq/Ollama, histórico e ferramentas de busca.
    """

    def __init__(self):
        self.conversation_history = []
        self.engine = AI_ENGINE.lower()

        if self.engine == "groq":
            self._check_groq()
        elif self.engine == "ollama":
            self._check_ollama()

    # ==================== FERRAMENTAS INTERNAS ====================

    def _web_search(self, query):
        """Realiza busca no DuckDuckGo (Simulado via API simples ou Scraper)."""
        logger.info(f"Zerachiel pesquisando na web por: {query}")
        try:
            # Usando uma URL de busca rápida que retorna texto (exemplo simplificado)
            # Para uma implementação real, pode-se usar bibliotecas como duckduckgo_search
            url = f"https://api.duckduckgo.com/?q={query}&format=json"
            resp = requests.get(url, timeout=10)
            data = resp.json()
            abstract = data.get("AbstractText", "")
            if not abstract:
                return "Não encontrei um resumo específico, mas os resultados sugerem que é um tema relevante."
            return abstract
        except Exception as e:
            logger.error(f"Erro na busca web: {e}")
            return "Erro ao acessar a internet para esta pesquisa."

    # ==================== MOTOR GROQ ====================

    def _check_groq(self):
        if not GROQ_API_KEY or "SUA_API" in GROQ_API_KEY:
            logger.warning("GROQ_API_KEY não configurada corretamente no .env!")
            return
        try:
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=10,
            )
            if resp.status_code == 200:
                print(f"[OK] Cérebro Groq conectado. Modelo: {GROQ_MODEL}")
        except Exception as e:
            logger.error(f"Erro ao conectar com Groq: {e}")

    def _call_groq(self, user_input):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        
        # Histórico formatado para OpenAI/Groq
        for exchange in self.conversation_history[-6:]:
            messages.append({"role": "user", "content": exchange["user"]})
            messages.append({"role": "assistant", "content": exchange["assistant"]})
        
        messages.append({"role": "user", "content": user_input})

        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        
        payload = {
            "model": GROQ_MODEL,
            "messages": messages,
            "tools": TOOLS_DEFINITION,
            "tool_choice": "auto",
            "temperature": 0.7
        }

        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        message = data["choices"][0]["message"]

        # Lógica de Function Calling (Web Search)
        if message.get("tool_calls"):
            tool_call = message["tool_calls"][0]
            if tool_call["function"]["name"] == "web_search":
                args = json.loads(tool_call["function"]["arguments"])
                search_result = self._web_search(args["query"])
                
                # Segunda chamada enviando o resultado da busca
                messages.append(message)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "name": "web_search",
                    "content": search_result
                })
                
                resp_final = requests.post(url, headers=headers, json={"model": GROQ_MODEL, "messages": messages}, timeout=30)
                return resp_final.json()["choices"][0]["message"]["content"]

        return message["content"]

    # ==================== MOTOR OLLAMA ====================

    def _check_ollama(self):
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                print(f"[OK] Cérebro Ollama (Local) ativo: {OLLAMA_MODEL}")
        except Exception:
            logger.warning("Ollama não detectado localmente.")

    def _call_ollama(self, user_input):
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for exchange in self.conversation_history[-6:]:
            messages.append({"role": "user", "content": exchange["user"]})
            messages.append({"role": "assistant", "content": exchange["assistant"]})
        messages.append({"role": "user", "content": user_input})

        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    # ==================== PROCESSAMENTO PRINCIPAL ====================

    def process(self, user_input):
        try:
            if self.engine == "groq":
                full_text = self._call_groq(user_input)
            elif self.engine == "ollama":
                full_text = self._call_ollama(user_input)
            else:
                return self._fallback_response(user_input)

            # Separa versão falada (limpa) da versão exibida (com código/markdown)
            if "```" in full_text or "`" in full_text:
                spoken = self._extract_spoken_version(full_text)
                return (spoken, full_text)

            return (full_text, None)

        except Exception as e:
            logger.error(f"Erro no processamento: {e}")
            return (f"Tive um erro no meu processamento interno: {str(e)}", None)

    def _extract_spoken_version(self, full_text):
        """Remove blocos de código para a voz não ler caracteres técnicos."""
        clean = re.sub(r"```[\s\S]*?```", " [Conteúdo de código exibido na tela] ", full_text)
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        clean = re.sub(r"[*_#]", "", clean) # Remove markdown de negrito/itálico
        return clean.strip()

    def _fallback_response(self, user_input):
        text = user_input.lower()
        if "olá" in text or "oi" in text:
            return (f"Olá! Sou o {ASSISTANT_NAME}. Configure minhas chaves para conversarmos melhor!", None)
        return (f"Entendi '{user_input}', mas meus motores de IA estão desligados.", None)

    def add_to_history(self, user_msg, assistant_msg):
        self.conversation_history.append({"user": user_msg, "assistant": assistant_msg})

    def detect_code_content(self, text):
        return bool(re.search(r"```", text))