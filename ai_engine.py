# ============================================================
# ai_engine.py — Motor de IA (Zerachiel v3.4)
#
# Motores disponíveis (por prioridade):
#   1. Gemini 2.0 Flash  — rápido, gratuito, motor principal
#   2. Groq              — fallback, function calling completo
#   3. Ollama            — fallback local, sem function calling
#
# CORREÇÕES v3.4:
#   - _call_gemini() duplicado removido (havia 3 definições)
#   - URL do Gemini corrigida (estava sem f-string na 2ª cópia)
#   - _call_ollama() f-string corrigida ("{OLLAMA_BASE_URL}" → f"...")
#   - process() f-strings corrigidas nos logger.error e msg de retorno
#   - system_instruction adicionada ao payload do Gemini
#   - Gemini com suporte a function calling via declaração de tools
# ============================================================

import re
import os
import json
import requests
import logging

from config import (
    ASSISTANT_NAME,
    AI_ENGINE,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    GEMINI_API_KEY,
    GEMINI_MODEL,
    SYSTEM_PROMPT,
    TOOLS_DEFINITION,
    BASE_SANDBOX,
    ALLOWED_DIRS,
)

logger = logging.getLogger("VoiceAssistant")


# ══════════════════════════════════════════════════════════════
# HELPERS DE DIRETÓRIO
# ══════════════════════════════════════════════════════════════

def _normalize_dir_key(text: str) -> str:
    """
    Normaliza uma string de diretório para comparação com ALLOWED_DIRS.
    Remove acentos, converte underscores em espaços, lowercase.
    Ex: "Área_De_Trabalho" → "area de trabalho"
    """
    import unicodedata
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("_", " ").replace("-", " ")
    text = " ".join(text.split())
    return text


def _resolve_directory(directory: str) -> str | None:
    """
    Resolve um alias de diretório para o caminho absoluto.
    Tenta: chave exata → normalizada → todas as chaves normalizadas → caminho absoluto.
    Retorna None se não for uma pasta permitida.
    """
    if not directory:
        return None

    key_lower = directory.lower().strip()
    if key_lower in ALLOWED_DIRS:
        return ALLOWED_DIRS[key_lower]

    key_norm = _normalize_dir_key(directory)
    if key_norm in ALLOWED_DIRS:
        return ALLOWED_DIRS[key_norm]

    for alias, path in ALLOWED_DIRS.items():
        if _normalize_dir_key(alias) == key_norm:
            return path

    try:
        abs_try = os.path.realpath(directory)
        allowed_roots = [os.path.realpath(d) for d in ALLOWED_DIRS.values()]
        if any(abs_try.startswith(root) for root in allowed_roots):
            return abs_try
    except Exception:
        pass

    return None


# ══════════════════════════════════════════════════════════════
# MOTOR PRINCIPAL
# ══════════════════════════════════════════════════════════════

class AIEngine:
    """
    Motor de IA do Zerachiel.
    Prioridade: Gemini → Groq → Ollama.
    Gerencia histórico de conversa e ferramentas (web_search, file_manager).
    """

    def __init__(self):
        self.conversation_history: list = []
        self.engine = AI_ENGINE.lower()
        self._last_response: str = ""

        if self.engine == "gemini":
            self._check_gemini()
        elif self.engine == "groq":
            self._check_groq()
        elif self.engine == "ollama":
            self._check_ollama()
        else:
            logger.warning(f"Engine desconhecida: '{self.engine}'. Usando Gemini como fallback.")
            self.engine = "gemini"
            self._check_gemini()

    # ══════════════════════════════════════════════════════════
    # FERRAMENTAS INTERNAS
    # ══════════════════════════════════════════════════════════

    def _web_search(self, query: str) -> str:
        """Busca no DuckDuckGo Instant Answer API."""
        logger.info(f"[web_search] Pesquisando: '{query}'")
        try:
            url = "https://api.duckduckgo.com/"
            params = {"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"}
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            abstract = data.get("AbstractText", "").strip()
            if abstract:
                return abstract[:800]

            topics = data.get("RelatedTopics", [])
            snippets = [
                item.get("Text", "") for item in topics[:4]
                if isinstance(item, dict) and item.get("Text")
            ]
            if snippets:
                return " | ".join(snippets)[:800]

            return (
                "Não encontrei um resumo direto para essa pesquisa. "
                "Tente reformular a pergunta com termos mais específicos."
            )

        except requests.Timeout:
            return "A pesquisa demorou mais do que o esperado. Tente novamente."
        except Exception as e:
            logger.error(f"[web_search] Erro: {e}")
            return f"Erro ao acessar a internet: {e}"

    def _file_manager(
        self,
        action: str,
        filename: str = "",
        content: str = "",
        directory: str = "",
    ) -> str:
        """
        Gerencia arquivos no PC com sandbox e sanitização de path.

        Actions: create | read | list | edit | append | save_last_response
        Pastas permitidas: desktop, documentos, downloads, sandbox (padrão)
        """
        logger.info(f"[file_manager] action={action} | filename={filename!r} | dir={directory!r}")

        # Resolve diretório
        resolved_dir = _resolve_directory(directory) if directory else BASE_SANDBOX
        if directory and not resolved_dir:
            return (
                f"Pasta '{directory}' não é permitida. "
                "Use: 'desktop', 'documentos', 'downloads' ou 'sandbox'."
            )

        # Sanitiza nome do arquivo
        safe_filename = re.sub(r'[\\/:*?"<>|]', "_", filename).strip() if filename else ""

        if not safe_filename and action not in ("list",):
            return f"Nome de arquivo é obrigatório para a ação '{action}'."

        # Verifica path traversal
        filepath = os.path.realpath(os.path.join(resolved_dir, safe_filename)) if safe_filename else None
        real_base = os.path.realpath(resolved_dir)
        if filepath and not filepath.startswith(real_base):
            logger.warning(f"[file_manager] Path traversal bloqueado: {filepath}")
            return "Acesso negado: caminho inválido ou fora da área permitida."

        os.makedirs(resolved_dir, exist_ok=True)

        # Executa ação
        if action == "create":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[file_manager] Arquivo criado: {filepath}")
            return f"Arquivo '{safe_filename}' criado em '{resolved_dir}'."

        elif action == "edit":
            if not os.path.exists(filepath):
                return f"Arquivo '{safe_filename}' não encontrado. Use 'create' para criar."
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[file_manager] Arquivo editado: {filepath}")
            return f"Arquivo '{safe_filename}' atualizado."

        elif action == "append":
            with open(filepath, "a", encoding="utf-8") as f:
                f.write("\n" + content)
            logger.info(f"[file_manager] Conteúdo adicionado: {filepath}")
            return f"Conteúdo adicionado ao arquivo '{safe_filename}'."

        elif action == "read":
            if not os.path.exists(filepath):
                return f"Arquivo '{safe_filename}' não encontrado em '{resolved_dir}'."
            with open(filepath, "r", encoding="utf-8") as f:
                text = f.read()
            if len(text) > 3000:
                text = text[:3000] + "\n\n[... conteúdo truncado ...]"
            logger.info(f"[file_manager] Arquivo lido: {filepath}")
            return text

        elif action == "list":
            if not os.path.exists(resolved_dir):
                return f"Pasta '{resolved_dir}' não existe."
            files = os.listdir(resolved_dir)
            if not files:
                return f"A pasta '{resolved_dir}' está vazia."
            return f"Arquivos em '{resolved_dir}':\n" + "\n".join(f"  - {f}" for f in sorted(files))

        elif action == "save_last_response":
            if not self._last_response:
                return "Não há resposta anterior para salvar."
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._last_response)
            logger.info(f"[file_manager] Última resposta salva: {filepath}")
            return f"Última resposta salva em '{safe_filename}' ({resolved_dir})."

        return f"Ação '{action}' não reconhecida. Use: create, read, list, edit, append, save_last_response."

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        """Dispatcher central de ferramentas."""
        if tool_name == "web_search":
            return self._web_search(arguments.get("query", ""))
        elif tool_name == "file_manager":
            return self._file_manager(
                action    = arguments.get("action", ""),
                filename  = arguments.get("filename", ""),
                content   = arguments.get("content", ""),
                directory = arguments.get("directory", ""),
            )
        return f"Ferramenta '{tool_name}' não implementada."

    # ══════════════════════════════════════════════════════════
    # MOTOR GEMINI (principal)
    # ══════════════════════════════════════════════════════════

    def _check_gemini(self):
        """Verifica se a API Key do Gemini está configurada."""
        if not GEMINI_API_KEY or "SUA_API" in str(GEMINI_API_KEY):
            logger.warning("GEMINI_API_KEY não configurada. Adicione no arquivo .env!")
            return
        print(f"[OK] Gemini {GEMINI_MODEL} — motor principal ativo.")

    def _call_gemini(self, user_input: str) -> str:
        """
        Chama Gemini 2.0 Flash via REST API oficial.

        Suporte a function calling: se o Gemini retornar functionCall,
        executa a tool localmente e faz segunda chamada com o resultado.

        Formato Gemini (diferente do OpenAI):
          - Histórico usa roles "user" / "model" (não "assistant")
          - System prompt vai em system_instruction separado
          - Tool calls retornam como parts[].functionCall
          - Tool results vão em parts[].functionResponse
        """
        if not GEMINI_API_KEY:
            return "GEMINI_API_KEY não configurada no .env"

        # ── Converte TOOLS_DEFINITION para formato Gemini ────
        # Gemini usa "functionDeclarations" dentro de "tools"
        gemini_tools = []
        if TOOLS_DEFINITION:
            declarations = []
            for t in TOOLS_DEFINITION:
                fn = t.get("function", {})
                declarations.append({
                    "name":        fn.get("name", ""),
                    "description": fn.get("description", ""),
                    "parameters":  fn.get("parameters", {}),
                })
            gemini_tools = [{"functionDeclarations": declarations}]

        # ── Monta histórico no formato Gemini ────────────────
        contents = []
        for exchange in self.conversation_history[-6:]:
            contents.append({"role": "user",  "parts": [{"text": exchange["user"]}]})
            contents.append({"role": "model", "parts": [{"text": exchange["assistant"]}]})
        contents.append({"role": "user", "parts": [{"text": user_input}]})

        url     = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
        headers = {"Content-Type": "application/json"}
        params  = {"key": GEMINI_API_KEY}
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": contents,
            "tools":    gemini_tools,
            "generationConfig": {
                "temperature":     0.7,
                "maxOutputTokens": 1024,
            },
        }

        try:
            resp = requests.post(url, headers=headers, params=params, json=payload, timeout=30)
            if not resp.ok:
                # 429 = quota esgotada → fallback automático para Groq
                if resp.status_code == 429:
                    logger.warning("[Gemini] Quota esgotada (429) — usando Groq como fallback.")
                    return self._call_groq(user_input)
                logger.error(f"[Gemini] Erro {resp.status_code}: {resp.text[:400]}")
                resp.raise_for_status()

            data      = resp.json()
            candidate = data["candidates"][0]
            parts     = candidate["content"]["parts"]

            # ── Verifica se há function call ─────────────────
            fn_call = next((p for p in parts if "functionCall" in p), None)

            if not fn_call:
                # Resposta de texto direta
                return parts[0].get("text", "")

            # ── Executa a ferramenta ──────────────────────────
            tool_name  = fn_call["functionCall"]["name"]
            arguments  = fn_call["functionCall"].get("args", {})
            logger.info(f"[Gemini] Function call: {tool_name}({arguments})")
            tool_result = self._execute_tool(tool_name, arguments)

            # ── Segunda chamada com o resultado ───────────────
            contents_with_tool = contents + [
                # Resposta do modelo com a function call
                {"role": "model", "parts": [{"functionCall": fn_call["functionCall"]}]},
                # Resultado da execução
                {
                    "role": "user",
                    "parts": [{
                        "functionResponse": {
                            "name":     tool_name,
                            "response": {"result": str(tool_result)},
                        }
                    }],
                },
            ]

            payload_final = {
                "system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
                "contents": contents_with_tool,
                "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024},
                # Sem tools na segunda chamada — queremos só o texto final
            }

            resp2 = requests.post(url, headers=headers, params=params, json=payload_final, timeout=30)
            if not resp2.ok:
                logger.error(f"[Gemini] Erro 2ª chamada {resp2.status_code}: {resp2.text[:400]}")
                resp2.raise_for_status()

            parts2 = resp2.json()["candidates"][0]["content"]["parts"]
            return parts2[0].get("text", "")

        except requests.Timeout:
            return "Gemini demorou para responder. Tente novamente."
        except Exception as e:
            logger.error(f"[Gemini] Erro inesperado: {e}", exc_info=True)
            return f"Erro ao chamar Gemini: {str(e)[:200]}"

    # ══════════════════════════════════════════════════════════
    # MOTOR GROQ (fallback)
    # ══════════════════════════════════════════════════════════

    def _check_groq(self):
        """Verifica se a API Groq está acessível."""
        if not GROQ_API_KEY or "SUA_API" in str(GROQ_API_KEY):
            logger.warning("GROQ_API_KEY não configurada. Verifique o arquivo .env!")
            return
        try:
            resp = requests.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
                timeout=10,
            )
            if resp.status_code == 200:
                print(f"[OK] Groq conectado. Modelo: {GROQ_MODEL}")
            else:
                logger.warning(f"Groq retornou status {resp.status_code}")
        except Exception as e:
            logger.error(f"Erro ao conectar com Groq: {e}")

    def _build_messages(self, user_input: str) -> list:
        """Monta mensagens no formato OpenAI-compatible (Groq/Ollama)."""
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for exchange in self.conversation_history[-6:]:
            messages.append({"role": "user",      "content": exchange["user"]})
            messages.append({"role": "assistant",  "content": exchange["assistant"]})
        messages.append({"role": "user", "content": user_input})
        return messages

    def _call_groq(self, user_input: str) -> str:
        """
        Chama Groq com suporte a function calling.

        IMPORTANTE: o ciclo de tool_calls usa lista temporária (msgs_with_tool)
        que NUNCA entra no conversation_history — evita erro 400 do Groq
        (tool_result sem tool_call correspondente no histórico).
        """
        messages = self._build_messages(user_input)
        url      = "https://api.groq.com/openai/v1/chat/completions"
        headers  = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type":  "application/json",
        }
        payload = {
            "model":       GROQ_MODEL,
            "messages":    messages,
            "tools":       TOOLS_DEFINITION,
            "tool_choice": "auto",
            "temperature": 0.7,
            "max_tokens":  1024,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if not resp.ok:
                logger.error(f"[Groq] Erro {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
        except requests.HTTPError:
            raise

        data    = resp.json()
        message = data["choices"][0]["message"]

        if not message.get("tool_calls"):
            return message.get("content", "")

        # Executa a ferramenta
        tool_call    = message["tool_calls"][0]
        tool_name    = tool_call["function"]["name"]
        tool_call_id = tool_call["id"]

        try:
            arguments = json.loads(tool_call["function"]["arguments"])
        except (json.JSONDecodeError, KeyError):
            arguments = {}

        logger.info(f"[Groq] Tool call: {tool_name}({arguments})")
        tool_result = self._execute_tool(tool_name, arguments)

        # Segunda chamada com resultado — lista temporária, não vai pro histórico
        msgs_with_tool = messages + [
            {
                "role":       "assistant",
                "content":    None,   # Groq exige None quando há tool_calls
                "tool_calls": message["tool_calls"],
            },
            {
                "role":         "tool",
                "tool_call_id": tool_call_id,
                "name":         tool_name,
                "content":      str(tool_result),
            },
        ]

        payload_final = {
            "model":      GROQ_MODEL,
            "messages":   msgs_with_tool,
            "max_tokens": 1024,
        }

        try:
            resp_final = requests.post(url, headers=headers, json=payload_final, timeout=30)
            if not resp_final.ok:
                logger.error(f"[Groq] Erro 2ª chamada {resp_final.status_code}: {resp_final.text[:500]}")
                resp_final.raise_for_status()
        except requests.HTTPError:
            raise

        return resp_final.json()["choices"][0]["message"]["content"]

    # ══════════════════════════════════════════════════════════
    # MOTOR OLLAMA (fallback local)
    # ══════════════════════════════════════════════════════════

    def _check_ollama(self):
        """Verifica se o Ollama está rodando localmente."""
        try:
            resp = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5)
            if resp.status_code == 200:
                print(f"[OK] Ollama local ativo. Modelo: {OLLAMA_MODEL}")
        except Exception:
            logger.warning("Ollama não detectado. Inicie com: ollama serve")

    def _call_ollama(self, user_input: str) -> str:
        """Chama Ollama local (sem function calling)."""
        messages = self._build_messages(user_input)
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",   # CORRIGIDO: era "{OLLAMA_BASE_URL}" sem f-string
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    # ══════════════════════════════════════════════════════════
    # PROCESSAMENTO PRINCIPAL
    # ══════════════════════════════════════════════════════════

    def process(self, user_input: str) -> tuple[str, str | None]:
        """
        Processa o input e retorna (spoken_text, display_text).

        spoken_text:  versão limpa para TTS (sem markdown/código)
        display_text: versão completa para a GUI (com markdown)
                      None se o texto for simples (sem código, < 600 chars)

        Ordem de prioridade: Gemini → Groq → Ollama
        """
        try:
            if self.engine == "gemini":
                full_text = self._call_gemini(user_input)
            elif self.engine == "groq":
                full_text = self._call_groq(user_input)
            elif self.engine == "ollama":
                full_text = self._call_ollama(user_input)
            else:
                full_text = self._call_gemini(user_input)

            self._last_response = full_text

            if "```" in full_text or len(full_text) > 600:
                spoken = self._extract_spoken_version(full_text)
                return (spoken, full_text)

            return (full_text, None)

        except requests.Timeout:
            msg = "A resposta demorou demais. Tente novamente."
            return (msg, None)
        except requests.HTTPError as e:
            logger.error(f"Erro HTTP na API: {e}")   # CORRIGIDO: f-string
            msg = "Tive um problema de comunicação. Verifique a API key."
            return (msg, None)
        except Exception as e:
            logger.error(f"Erro no processamento: {e}", exc_info=True)   # CORRIGIDO: f-string
            msg = f"Tive um erro interno: {str(e)}"   # CORRIGIDO: f-string
            return (msg, None)

    def _extract_spoken_version(self, full_text: str) -> str:
        """
        Gera versão falável: remove markdown/código, trunca em ~600 chars
        na última frase completa.
        """
        clean = re.sub(r"```[\s\S]*?```", " [código exibido na tela] ", full_text)
        clean = re.sub(r"`([^`]+)`",      r"\1", clean)
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
        clean = re.sub(r"\*([^*]+)\*",      r"\1", clean)
        clean = re.sub(r"^#{1,6}\s+", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"^\s*[-*•]\s+", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        clean = re.sub(r"\n{2,}", ". ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        if len(clean) > 600:
            truncated   = clean[:600]
            last_period = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
            if last_period > 300:
                clean = truncated[:last_period + 1] + " O texto completo está na tela."
            else:
                clean = truncated + "... O texto completo está na tela."

        return clean

    def _fallback_response(self, user_input: str) -> tuple[str, None]:
        """Resposta de emergência quando nenhum motor está disponível."""
        text = user_input.lower()
        if "olá" in text or "oi" in text:
            return (
                f"Olá! Sou o {ASSISTANT_NAME}. "
                "Configure minha API key no arquivo .env para conversarmos!",
                None,
            )
        return (
            f"Entendi '{user_input}', mas meus motores de IA estão offline. "
            "Verifique o arquivo .env e a conexão com a internet.",
            None,
        )

    # ══════════════════════════════════════════════════════════
    # HISTÓRICO
    # ══════════════════════════════════════════════════════════

    def add_to_history(self, user_msg: str, assistant_msg: str):
        """Adiciona uma troca ao histórico (máximo 20 trocas)."""
        self.conversation_history.append({"user": user_msg, "assistant": assistant_msg})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def clear_history(self):
        """Limpa o histórico de conversa."""
        self.conversation_history.clear()
        logger.info("Histórico de conversa limpo.")

    def detect_code_content(self, text: str) -> bool:
        """Retorna True se o texto contiver bloco de código."""
        return bool(re.search(r"```", text))