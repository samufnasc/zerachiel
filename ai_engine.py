# ============================================================
# ai_engine.py — Motor de IA Ultra-Resiliente (v4.0)
# ============================================================

import re
import os
import json
import time
import base64
import requests
import logging
import unicodedata
from datetime import datetime
from tkinter import messagebox
from config import (
    ASSISTANT_NAME,
    AI_ENGINE,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT,
    OLLAMA_SLOW_THRESHOLD,
    GEMINI_API_KEY,
    GEMINI_MODELS,
    GEMINI_VISION_MODELS,
    GEMINI_QUOTA_STATE_FILE,
    SYSTEM_PROMPT,
    TOOLS_DEFINITION,
    ALLOWED_DIRS,
    SCREEN_REQUEST_KEYWORDS,
)

logger = logging.getLogger("VoiceAssistant")


class OllamaSlowError(Exception):
    """Levantada quando o Ollama demora mais que o limite aceitável."""


def _is_quota_error(exc: Exception) -> bool:
    """Detecta erros de quota/limite diário (429 / RESOURCE_EXHAUSTED)."""
    try:
        from google.genai import errors
        if isinstance(exc, errors.ClientError) and getattr(exc, "status_code", None) == 429:
            return True
    except Exception:
        pass
    text = str(exc)
    return "RESOURCE_EXHAUSTED" in text or "quota" in text.lower() or "429" in text

def _normalize_dir_key(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = text.replace("_", " ").replace("-", " ")
    return " ".join(text.split())

def _resolve_directory(directory: str) -> str | None:
    if not directory: return ALLOWED_DIRS.get("desktop")
    key_lower = directory.lower().strip()
    if key_lower in ALLOWED_DIRS: return ALLOWED_DIRS[key_lower]
    key_norm = _normalize_dir_key(directory)
    if key_norm in ALLOWED_DIRS: return ALLOWED_DIRS[key_norm]
    for alias, path in ALLOWED_DIRS.items():
        if _normalize_dir_key(alias) == key_norm: return path
    return ALLOWED_DIRS.get("desktop")

class AIEngine:
    def __init__(self):
        self.conversation_history = []
        self.current_engine = "GEMINI"
        self._last_response = ""
        self._gemini_cursor = 0
        self._quota_state_file = GEMINI_QUOTA_STATE_FILE
        self._exhausted_today = self._load_quota_state()

    # ---------- Rotação de modelos Gemini ----------

    def _load_quota_state(self) -> set:
        try:
            with open(self._quota_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("date") == datetime.now().strftime("%Y-%m-%d"):
                return set(data.get("exhausted", []))
        except (FileNotFoundError, ValueError, TypeError):
            pass
        return set()

    def _save_quota_state(self):
        try:
            data = {"date": datetime.now().strftime("%Y-%m-%d"), "exhausted": sorted(self._exhausted_today)}
            with open(self._quota_state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.debug(f"Não foi possível salvar estado de quota: {e}")

    def _next_available_gemini(self, exclude: set | None = None) -> str | None:
        """Retorna o próximo modelo Gemini ainda com quota diária livre."""
        exclude = exclude or set()
        total = len(GEMINI_MODELS)
        for _ in range(total):
            model = GEMINI_MODELS[self._gemini_cursor % total]
            self._gemini_cursor = (self._gemini_cursor + 1) % total
            if model not in self._exhausted_today and model not in exclude:
                return model
        return None

    def _has_available_gemini(self, exclude: set | None = None) -> bool:
        exclude = exclude or set()
        return any(m not in self._exhausted_today and m not in exclude for m in GEMINI_MODELS)

    def _mark_quota_exhausted(self, model: str):
        self._exhausted_today.add(model)
        self._save_quota_state()
        logger.warning(f"Quota diária esgotada: {model}")

    def _file_manager(self, action: str, filename: str = "", content: str = "", directory: str = "") -> str:
        resolved_dir = _resolve_directory(directory)
        safe_filename = re.sub(r'[\\/:*?"<>|]', "_", filename).strip()

        # Ação "list" não requer nome de arquivo
        if action == "list":
            if not os.path.isdir(resolved_dir): return "ERRO: Diretório não encontrado."
            return f"Arquivos: " + ", ".join(os.listdir(resolved_dir))

        if not safe_filename: return "ERRO: Nome de arquivo inválido."
        
        filepath = os.path.join(resolved_dir, safe_filename)
        os.makedirs(resolved_dir, exist_ok=True)

        # SEGURANÇA: Pede permissão se o arquivo já existir para ações de escrita
        if action in ["create", "edit", "append"] and os.path.exists(filepath):
            import tkinter as tk
            from tkinter import messagebox
            root = tk.Tk(); root.withdraw()
            ans = messagebox.askyesno("Permissão de Arquivo", f"O arquivo '{safe_filename}' já existe. Deseja permitir a alteração?")
            root.destroy()
            if not ans: return "ERRO: Permissão negada pelo usuário."

        try:
            if action in ["create", "edit"]:
                with open(filepath, "w", encoding="utf-8") as f: f.write(content)
                logger.info(f"ARQUIVO OPERADO: {filepath}")
                return f"SUCESSO: Arquivo '{safe_filename}' salvo no Desktop."
            elif action == "append":
                with open(filepath, "a", encoding="utf-8") as f: f.write("\n" + content)
                return "SUCESSO: Conteúdo adicionado."
            elif action == "read":
                if not os.path.exists(filepath): return "ERRO: Arquivo não encontrado."
                with open(filepath, "r", encoding="utf-8") as f: return f.read()[:2000]
        except Exception as e:
            return f"ERRO ao manipular arquivo: {e}"
        return "Ação inválida."

    def _execute_tool(self, tool_name: str, arguments: dict) -> str:
        if tool_name == "web_search":
            try:
                url = "https://api.duckduckgo.com/"
                params = {"q": arguments.get("query", ""), "format": "json", "no_html": "1", "skip_disambig": "1"}
                resp = requests.get(url, params=params, timeout=10)
                return resp.json().get("AbstractText", "Sem resultados.")[:800]
            except: return "Erro na busca."
        if tool_name == "file_manager": return self._file_manager(**arguments)
        return "Ferramenta não encontrada."

    def _call_gemini(self, user_input: str, model: str | None = None) -> str:
        model = model or GEMINI_MODELS[0]
        self.current_engine = model
        if not GEMINI_API_KEY:
            raise Exception("GEMINI_API_KEY não configurada")
        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=GEMINI_API_KEY)

        contents = []
        for h in self.conversation_history[-5:]:
            contents.append({"role": "user", "parts": [{"text": h["user"]}]})
            contents.append({"role": "model", "parts": [{"text": h["assistant"]}]})
        contents.append({"role": "user", "parts": [{"text": user_input}]})

        resp = client.models.generate_content(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT + " SEJA CRITERIOSO: Só crie arquivos se o usuário pedir explicitamente. Para analisar anexos, use o conteúdo fornecido."
            ),
        )
        if not resp.text:
            raise Exception(f"Gemini não gerou texto ({model})")
        return resp.text

    def _call_groq(self, user_input: str) -> str:
        self.current_engine = "GROQ"
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}
        messages = [{"role": "system", "content": SYSTEM_PROMPT + " SEJA CRITERIOSO: Só crie arquivos se o usuário pedir explicitamente."}]
        for h in self.conversation_history[-5:]:
            messages.extend([{"role": "user", "content": h["user"]}, {"role": "assistant", "content": h["assistant"]}])
        messages.append({"role": "user", "content": user_input})
        
        payload = {"model": GROQ_MODEL, "messages": messages, "tools": TOOLS_DEFINITION, "tool_choice": "auto"}
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        if not resp.ok: raise Exception(f"Groq Error: {resp.status_code}")
        
        data = resp.json()
        msg = data["choices"][0]["message"]
        
        if msg.get("tool_calls"):
            tool_call = msg["tool_calls"][0]
            fn_name = tool_call["function"]["name"]
            fn_args = json.loads(tool_call["function"]["arguments"])
            res = self._execute_tool(fn_name, fn_args)
            messages.append(msg)
            messages.append({"role": "tool", "tool_call_id": tool_call["id"], "name": fn_name, "content": res})
            resp2 = requests.post(url, headers=headers, json={"model": GROQ_MODEL, "messages": messages}, timeout=20)
            return resp2.json()["choices"][0]["message"]["content"]
        return msg["content"]

    def _call_ollama(self, user_input: str) -> str:
        self.current_engine = "OLLAMA"
        url = f"{OLLAMA_BASE_URL}/api/chat"
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in self.conversation_history[-5:]:
            messages.extend([{"role": "user", "content": h["user"]}, {"role": "assistant", "content": h["assistant"]}])
        messages.append({"role": "user", "content": user_input})

        start = time.monotonic()
        try:
            resp = requests.post(url, json={"model": OLLAMA_MODEL, "messages": messages, "stream": False}, timeout=OLLAMA_TIMEOUT)
        except requests.exceptions.Timeout:
            raise OllamaSlowError(f"Ollama sem resposta em {OLLAMA_TIMEOUT}s")
        if resp.status_code != 200:
            raise Exception(f"Ollama Error: {resp.status_code}")

        content = resp.json()["message"]["content"]
        elapsed = time.monotonic() - start
        if elapsed > OLLAMA_SLOW_THRESHOLD:
            raise OllamaSlowError(f"Ollama lento demais ({elapsed:.1f}s)")
        return content

    def process_screen(self, user_input: str) -> tuple[str, str | None]:
        """Captura a tela e a envia ao Gemini (multimodal) para análise."""
        if not GEMINI_API_KEY:
            return ("Configure a chave GEMINI_API_KEY para usar a visão.", None)
        try:
            from screen_capture import capture_screen_png_base64
            image_b64 = capture_screen_png_base64()
        except Exception as e:
            logger.error(f"Erro ao capturar a tela: {e}")
            return ("Não consegui capturar a tela. Instale a biblioteca mss e tente novamente.", None)

        from google import genai
        from google.genai import types as genai_types
        client = genai.Client(api_key=GEMINI_API_KEY)
        failed_models = set()
        for model in GEMINI_VISION_MODELS:
            if model in self._exhausted_today or model in failed_models:
                continue
            self.current_engine = model
            try:
                resp = client.models.generate_content(
                    model=model,
                    contents=[
                        genai_types.Part.from_bytes(data=base64.b64decode(image_b64), mime_type="image/png"),
                        user_input,
                    ],
                    config=genai_types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT + " Analise a captura de tela com precisão, resuma o que vê e aponte problemas visíveis."
                    ),
                )
                if not resp.text:
                    raise Exception(f"Gemini não gerou texto ({model})")
                text = resp.text
                self._gemini_cursor = 0
                break
            except Exception as e:
                if _is_quota_error(e):
                    self._mark_quota_exhausted(model)
                else:
                    failed_models.add(model)
                logger.warning(f"Falha na visão {model}: {e}")
        else:
            return ("Não consegui processar a imagem com nenhum modelo disponível.", None)

        self._last_response = text
        return (self._clean_for_speech(text), text)

    def process(self, user_input: str) -> tuple[str, str | None]:
        if any(kw in user_input.lower() for kw in SCREEN_REQUEST_KEYWORDS):
            try:
                return self.process_screen(user_input)
            except Exception as e:
                logger.warning(f"Falha na visão: {e}")
                return ("Não consegui analisar a tela. Verifique a captura e tente novamente.", None)

        # Rotação: Gemini (cada modelo free) → Groq → Ollama.
        # Se o Ollama ficar lento, volta para o próximo Gemini disponível.
        max_attempts = len(GEMINI_MODELS) * 2 + 3
        tried_groq = False
        failed_here = set()
        for _ in range(max_attempts):
            model = self._next_available_gemini(exclude=failed_here)
            if model:
                try:
                    full_text = self._call_gemini(user_input, model=model)
                    self._last_response = full_text
                    self._gemini_cursor = 0
                    return self._format_output(full_text)
                except Exception as e:
                    if _is_quota_error(e):
                        self._mark_quota_exhausted(model)
                    else:
                        failed_here.add(model)
                        logger.warning(f"Falha no Gemini {model}: {e}")
                    continue

            if not tried_groq:
                tried_groq = True
                try:
                    full_text = self._call_groq(user_input)
                    self._last_response = full_text
                    return self._format_output(full_text)
                except Exception as e:
                    logger.warning(f"Falha na Engine GROQ: {e}")

            try:
                full_text = self._call_ollama(user_input)
                self._last_response = full_text
                return self._format_output(full_text)
            except OllamaSlowError:
                logger.warning("Ollama lento — voltando para o próximo Gemini")
                if self._has_available_gemini(exclude=failed_here):
                    continue
                break
            except Exception as e:
                logger.warning(f"Falha na Engine OLLAMA: {e}")
                if self._has_available_gemini(exclude=failed_here):
                    continue
                break
        return ("Todos os motores neurais falharam.", None)

    def _format_output(self, full_text: str) -> tuple[str, str | None]:
        if "```" in full_text or len(full_text) > 500:
            return (self._clean_for_speech(full_text), full_text)
        return (full_text, None)

    def _clean_for_speech(self, text: str) -> str:
        text = re.sub(r"```[\s\S]*?```", " [código na tela] ", text)
        text = re.sub(r"[`*#|_]", "", text)
        return text[:500]

    def add_to_history(self, u, a):
        self.conversation_history.append({"user": u, "assistant": a})
        if len(self.conversation_history) > 10: self.conversation_history.pop(0)
