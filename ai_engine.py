# ============================================================
# ai_engine.py — Motor de Inteligência Artificial (Zerachiel)
# Gerencia: Groq API (primário) | Ollama (fallback)
# Tools: web_search | file_manager (Etapa 3)
#
# NOVIDADE v3:
#   - file_manager com ações: create, read, list, edit, append,
#     save_last_response
#   - Aliases de pasta (documentos, desktop, downloads)
#   - Sanitização de path (bloqueia traversal "../")
#   - self._last_response armazena a última resposta para
#     save_last_response
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
    SYSTEM_PROMPT,
    TOOLS_DEFINITION,
    BASE_SANDBOX,
    ALLOWED_DIRS,
)

logger = logging.getLogger("VoiceAssistant")


def _normalize_dir_key(text: str) -> str:
    """
    Normaliza uma string de diretório para comparação com ALLOWED_DIRS.

    Problema: o Google STT transcreve "área de trabalho" de formas variadas,
    e a IA normaliza antes de chamar a tool (remove acentos, usa underscores).
    Esta função trata TODAS as variações conhecidas:
      "área de trabalho" → "area de trabalho"
      "area_de_trabalho" → "area de trabalho"
      "Área De Trabalho"  → "area de trabalho"
    """
    import unicodedata
    # Lowercase
    text = text.lower().strip()
    # Remove acentos (NFD → elimina diacríticos)
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    # Substitui underscores e hífens por espaço
    text = text.replace("_", " ").replace("-", " ")
    # Normaliza espaços extras
    text = " ".join(text.split())
    return text


def _resolve_directory(directory: str) -> str | None:
    """
    Resolve um nome/alias de diretório para o caminho absoluto correspondente.

    Tenta primeiro a chave original, depois a versão normalizada (sem acentos,
    sem underscores). Se nenhuma bater nos aliases, tenta como caminho absoluto
    dentro das pastas permitidas.

    Retorna o caminho resolvido ou None se não for permitido.
    """
    if not directory:
        return None

    # Tenta chave exata (case insensitive)
    key_lower = directory.lower().strip()
    if key_lower in ALLOWED_DIRS:
        return ALLOWED_DIRS[key_lower]

    # Tenta chave normalizada (sem acentos, underscores → espaços)
    key_norm = _normalize_dir_key(directory)
    if key_norm in ALLOWED_DIRS:
        return ALLOWED_DIRS[key_norm]

    # Tenta todas as chaves do dicionário também normalizadas
    for alias, path in ALLOWED_DIRS.items():
        if _normalize_dir_key(alias) == key_norm:
            return path

    # Última tentativa: caminho absoluto dentro das pastas permitidas
    try:
        abs_try = os.path.realpath(directory)
        allowed_roots = [os.path.realpath(d) for d in ALLOWED_DIRS.values()]
        if any(abs_try.startswith(root) for root in allowed_roots):
            return abs_try
    except Exception:
        pass

    return None


class AIEngine:
    """
    Motor de IA do Zerachiel.
    Gerencia chamadas para Groq/Ollama, histórico de conversa e ferramentas.
    """

    def __init__(self):
        self.conversation_history: list = []
        self.engine = AI_ENGINE.lower()
        self._last_response: str = ""   # armazena última resposta para save_last_response

        if self.engine == "groq":
            self._check_groq()
        elif self.engine == "ollama":
            self._check_ollama()
        else:
            logger.warning(f"Engine desconhecida: '{self.engine}'. Usando fallback.")

    # ══════════════════════════════════════════════════════════
    # FERRAMENTAS INTERNAS
    # ══════════════════════════════════════════════════════════

    def _web_search(self, query: str) -> str:
        """
        Realiza busca no DuckDuckGo Instant Answer API.
        Fallback: tenta resumir os RelatedTopics se AbstractText estiver vazio.
        """
        logger.info(f"[web_search] Pesquisando: '{query}'")
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q":              query,
                "format":         "json",
                "no_html":        "1",
                "skip_disambig":  "1",
            }
            resp = requests.get(url, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            # Tenta campo principal
            abstract = data.get("AbstractText", "").strip()
            if abstract:
                return abstract[:800]   # limita para não estourar contexto

            # Fallback: RelatedTopics
            topics = data.get("RelatedTopics", [])
            snippets = []
            for item in topics[:4]:
                text = item.get("Text", "") if isinstance(item, dict) else ""
                if text:
                    snippets.append(text)
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
            return f"Erro ao acessar a internet para esta pesquisa: {e}"

    def _file_manager(
        self,
        action:    str,
        filename:  str,
        content:   str = "",
        directory: str = "",
    ) -> str:
        """
        Gerencia arquivos no PC do usuário com sandbox e sanitização de path.

        Actions disponíveis:
          create              → cria novo arquivo (sobrescreve se existir)
          read                → lê e retorna o conteúdo
          list                → lista arquivos da pasta
          edit                → sobrescreve conteúdo de arquivo existente
          append              → adiciona conteúdo ao final do arquivo
          save_last_response  → salva a última resposta do assistente

        Segurança:
          - Somente pastas em ALLOWED_DIRS são permitidas
          - Nomes de arquivo são sanitizados (sem caracteres especiais)
          - Path traversal (../) é bloqueado via os.path.realpath
        """
        logger.info(f"[file_manager] action={action} | filename={filename} | dir={directory!r}")

        # ── Resolve o diretório de destino ───────────────────
        if directory:
            resolved_dir = _resolve_directory(directory)
            if not resolved_dir:
                return (
                    f"Pasta '{directory}' não é permitida. "
                    "Use: 'desktop', 'documentos', 'downloads' ou 'sandbox'."
                )
        else:
            resolved_dir = BASE_SANDBOX   # pasta padrão segura

        # ── Sanitização do nome do arquivo ───────────────────
        # Remove caracteres inválidos em nomes de arquivo Windows/Linux.
        # Para a ação "list", filename pode ser vazio — é aceitável.
        safe_filename = re.sub(r'[\\/:*?"<>|]', "_", filename).strip() if filename else ""

        if not safe_filename and action not in ("list",):
            return f"Nome de arquivo é obrigatório para a ação '{action}'."

        # ── Verifica path traversal (só quando há filename) ──
        filepath  = os.path.realpath(os.path.join(resolved_dir, safe_filename)) if safe_filename else None
        real_base = os.path.realpath(resolved_dir)

        if filepath and not filepath.startswith(real_base):
            logger.warning(f"[file_manager] Tentativa de path traversal bloqueada: {filepath}")
            return "Acesso negado: caminho de arquivo inválido ou fora da área permitida."

        # Garante que a pasta existe
        os.makedirs(resolved_dir, exist_ok=True)

        # ── Executa a ação ────────────────────────────────────

        if action == "create":
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[file_manager] Arquivo criado: {filepath}")
            return f"Arquivo '{safe_filename}' criado em '{resolved_dir}'."

        elif action == "edit":
            if not os.path.exists(filepath):
                return (
                    f"Arquivo '{safe_filename}' não encontrado em '{resolved_dir}'. "
                    "Use 'create' para criar um novo arquivo."
                )
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            logger.info(f"[file_manager] Arquivo editado: {filepath}")
            return f"Arquivo '{safe_filename}' atualizado com sucesso."

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
            # Limita retorno para não estourar contexto da IA
            if len(text) > 3000:
                text = text[:3000] + "\n\n[... conteúdo truncado — arquivo muito longo ...]"
            logger.info(f"[file_manager] Arquivo lido: {filepath}")
            return text

        elif action == "list":
            if not os.path.exists(resolved_dir):
                return f"Pasta '{resolved_dir}' não existe ou está vazia."
            files = os.listdir(resolved_dir)
            if not files:
                return f"A pasta '{resolved_dir}' está vazia."
            files_list = "\n".join(f"  - {f}" for f in sorted(files))
            return f"Arquivos em '{resolved_dir}':\n{files_list}"

        elif action == "save_last_response":
            if not self._last_response:
                return "Não há resposta anterior para salvar."
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._last_response)
            logger.info(f"[file_manager] Última resposta salva: {filepath}")
            return f"Última resposta salva em '{safe_filename}' ({resolved_dir})."

        else:
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

        else:
            return f"Ferramenta '{tool_name}' não implementada."

    # ══════════════════════════════════════════════════════════
    # MOTOR GROQ
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
                print(f"[OK] Cérebro Groq conectado. Modelo: {GROQ_MODEL}")
            else:
                logger.warning(f"Groq retornou status {resp.status_code}")
        except Exception as e:
            logger.error(f"Erro ao conectar com Groq: {e}")

    def _call_groq(self, user_input: str) -> str:
        """
        Envia a mensagem para a API Groq com suporte a function calling.

        IMPORTANTE sobre histórico e tool_calls:
        O Groq exige que se o histórico contiver uma mensagem do assistente
        com tool_calls, a próxima mensagem DEVE ser um tool_result com o
        mesmo tool_call_id. Por isso o histórico de conversa armazena APENAS
        o texto final da resposta (sem o ciclo de tool_calls) — o ciclo
        de ferramentas acontece só dentro desta função, em mensagens
        temporárias que nunca entram em self.conversation_history.
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
                # Loga o body completo do erro para diagnóstico
                logger.error(f"[Groq] Erro {resp.status_code}: {resp.text[:500]}")
                resp.raise_for_status()
        except requests.HTTPError:
            raise

        data    = resp.json()
        message = data["choices"][0]["message"]

        # ── Sem tool_calls: retorna a resposta direta ────────
        if not message.get("tool_calls"):
            return message.get("content", "")

        # ── Com tool_calls: executa a ferramenta ─────────────
        # Este ciclo usa uma lista de mensagens TEMPORÁRIA (msgs_with_tool)
        # que nunca é gravada em self.conversation_history.
        # Isso evita o erro 400 (tool_result sem tool_call correspondente).

        tool_call  = message["tool_calls"][0]
        tool_name  = tool_call["function"]["name"]
        tool_call_id = tool_call["id"]

        try:
            arguments = json.loads(tool_call["function"]["arguments"])
        except (json.JSONDecodeError, KeyError):
            arguments = {}

        logger.info(f"[Groq] Tool call: {tool_name}({arguments})")
        tool_result = self._execute_tool(tool_name, arguments)

        # Monta ciclo completo só para esta chamada — NÃO vai pro histórico
        msgs_with_tool = messages + [
            # Mensagem do assistente COM tool_calls (obrigatória antes do tool_result)
            {
                "role":       "assistant",
                "content":    None,          # Groq exige None quando há tool_calls
                "tool_calls": message["tool_calls"],
            },
            # Resultado da ferramenta
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
            # Sem tools na segunda chamada — só queremos o texto final
        }

        try:
            resp_final = requests.post(
                url, headers=headers, json=payload_final, timeout=30
            )
            if not resp_final.ok:
                logger.error(f"[Groq] Erro na 2ª chamada {resp_final.status_code}: {resp_final.text[:500]}")
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
                print(f"[OK] Cérebro Ollama (Local) ativo: {OLLAMA_MODEL}")
        except Exception:
            logger.warning("Ollama não detectado. Inicie com: ollama serve")

    def _call_ollama(self, user_input: str) -> str:
        """Envia a mensagem para o Ollama local (sem function calling)."""
        messages = self._build_messages(user_input)
        resp = requests.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": OLLAMA_MODEL, "messages": messages, "stream": False},
            timeout=120,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]

    # ══════════════════════════════════════════════════════════
    # PROCESSAMENTO PRINCIPAL
    # ══════════════════════════════════════════════════════════

    def _build_messages(self, user_input: str) -> list:
        """
        Monta o array de mensagens para a API com:
        - system prompt
        - histórico recente (últimas 6 trocas = 12 mensagens)
        - nova mensagem do usuário
        """
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        for exchange in self.conversation_history[-6:]:
            messages.append({"role": "user",      "content": exchange["user"]})
            messages.append({"role": "assistant",  "content": exchange["assistant"]})

        messages.append({"role": "user", "content": user_input})
        return messages

    def process(self, user_input: str) -> tuple[str, str | None]:
        """
        Processa o input do usuário e retorna (spoken_text, display_text).

        - spoken_text:  versão limpa para o TTS falar (sem markdown, sem código)
        - display_text: versão completa para exibir na GUI (pode ter markdown/código)
                        None se o texto for simples o suficiente para ambos usarem o mesmo
        """
        try:
            if self.engine == "groq":
                full_text = self._call_groq(user_input)
            elif self.engine == "ollama":
                full_text = self._call_ollama(user_input)
            else:
                return self._fallback_response(user_input)

            # Armazena para save_last_response
            self._last_response = full_text

            # Verifica se há código/markdown extenso → separa versões
            if "```" in full_text or len(full_text) > 600:
                spoken = self._extract_spoken_version(full_text)
                return (spoken, full_text)

            return (full_text, None)

        except requests.Timeout:
            msg = "A resposta demorou demais. Tente novamente."
            return (msg, None)
        except requests.HTTPError as e:
            logger.error(f"Erro HTTP na API: {e}")
            msg = "Tive um problema de comunicação com meu cérebro. Verifique a API key."
            return (msg, None)
        except Exception as e:
            logger.error(f"Erro no processamento: {e}", exc_info=True)
            msg = f"Tive um erro interno no processamento: {str(e)}"
            return (msg, None)

    def _extract_spoken_version(self, full_text: str) -> str:
        """
        Gera a versão falável do texto:
        - Remove blocos de código
        - Remove markdown
        - Trunca em ~600 chars na última frase completa
        """
        # Remove código
        clean = re.sub(r"```[\s\S]*?```", " [código exibido na tela] ", full_text)
        # Remove code inline
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        # Remove markdown
        clean = re.sub(r"\*\*([^*]+)\*\*", r"\1", clean)
        clean = re.sub(r"\*([^*]+)\*",     r"\1", clean)
        clean = re.sub(r"^#{1,6}\s+", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"^\s*[-*•]\s+", "", clean, flags=re.MULTILINE)
        clean = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", clean)
        clean = re.sub(r"\n{2,}", ". ", clean)
        clean = re.sub(r"\s+", " ", clean).strip()

        # Trunca em 600 chars na última frase completa para o TTS não demorar
        if len(clean) > 600:
            truncated = clean[:600]
            last_period = max(
                truncated.rfind("."),
                truncated.rfind("!"),
                truncated.rfind("?"),
            )
            if last_period > 300:
                clean = truncated[:last_period + 1] + " O texto completo está na tela."
            else:
                clean = truncated + "... O texto completo está na tela."

        return clean

    def _fallback_response(self, user_input: str) -> tuple[str, None]:
        """Resposta de emergência quando nenhum engine está disponível."""
        text = user_input.lower()
        if "olá" in text or "oi" in text:
            return (
                f"Olá! Sou o {ASSISTANT_NAME}. "
                "Configure minha API key no arquivo .env para conversarmos melhor!",
                None,
            )
        return (
            f"Entendi '{user_input}', mas meus motores de IA estão offline. "
            "Verifique o arquivo .env e a conexão.",
            None,
        )

    # ══════════════════════════════════════════════════════════
    # HISTÓRICO
    # ══════════════════════════════════════════════════════════

    def add_to_history(self, user_msg: str, assistant_msg: str):
        """Adiciona uma troca ao histórico de conversa."""
        self.conversation_history.append({
            "user":      user_msg,
            "assistant": assistant_msg,
        })
        # Mantém apenas as últimas 20 trocas para não estourar contexto
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    def clear_history(self):
        """Limpa o histórico de conversa."""
        self.conversation_history.clear()
        logger.info("Histórico de conversa limpo.")

    def detect_code_content(self, text: str) -> bool:
        """Retorna True se o texto contiver bloco de código."""
        return bool(re.search(r"```", text))