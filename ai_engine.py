# ============================================================
# ai_engine.py — Motor de IA Ultra-Resiliente (v4.0)
# ============================================================

import re
import os
import json
import requests
import logging
import unicodedata
from tkinter import messagebox
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
    ALLOWED_DIRS,
)

logger = logging.getLogger("VoiceAssistant")

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

    def _file_manager(self, action: str, filename: str = "", content: str = "", directory: str = "") -> str:
        resolved_dir = _resolve_directory(directory)
        safe_filename = re.sub(r'[\\/:*?"<>|]', "_", filename).strip()
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
            elif action == "list":
                return f"Arquivos: " + ", ".join(os.listdir(resolved_dir))
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

    def _call_gemini(self, user_input: str) -> str:
        self.current_engine = "GEMINI"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
        contents = []
        for h in self.conversation_history[-5:]:
            contents.append({"role": "user", "parts": [{"text": h["user"]}]})
            contents.append({"role": "model", "parts": [{"text": h["assistant"]}]})
        contents.append({"role": "user", "parts": [{"text": user_input}]})
        
        payload = {
            "system_instruction": {"parts": [{"text": SYSTEM_PROMPT + " SEJA CRITERIOSO: Só crie arquivos se o usuário pedir explicitamente. Para analisar anexos, use o conteúdo fornecido."}]},
            "contents": contents,
            "tools": [{"functionDeclarations": [t["function"] for t in TOOLS_DEFINITION]}]
        }
        resp = requests.post(url, json=payload, timeout=30)
        if resp.status_code == 429: raise Exception("Quota Exceeded")
        if not resp.ok: raise Exception(f"Gemini Error: {resp.status_code}")
        
        data = resp.json()
        parts = data["candidates"][0]["content"]["parts"]
        
        for part in parts:
            if "functionCall" in part:
                fn = part["functionCall"]
                res = self._execute_tool(fn["name"], fn.get("args", {}))
                payload["contents"].append({"role": "model", "parts": [part]})
                payload["contents"].append({
                    "role": "user", 
                    "parts": [{"functionResponse": {"name": fn["name"], "response": {"content": res}}}]
                })
                resp2 = requests.post(url, json=payload, timeout=30)
                return resp2.json()["candidates"][0]["content"]["parts"][0]["text"]
            if "text" in part:
                return part["text"]
        return "Gemini não gerou texto."

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
        resp = requests.post(url, json={"model": OLLAMA_MODEL, "messages": messages, "stream": False}, timeout=60)
        return resp.json()["message"]["content"]

    def process(self, user_input: str) -> tuple[str, str | None]:
        for method in [self._call_gemini, self._call_groq, self._call_ollama]:
            try:
                full_text = method(user_input)
                self._last_response = full_text
                if "```" in full_text or len(full_text) > 500:
                    return (self._clean_for_speech(full_text), full_text)
                return (full_text, None)
            except Exception as e:
                logger.warning(f"Falha na Engine {self.current_engine}: {e}")
                continue
        return ("Todos os motores neurais falharam.", None)

    def _clean_for_speech(self, text: str) -> str:
        text = re.sub(r"```[\s\S]*?```", " [código na tela] ", text)
        text = re.sub(r"[`*#|_]", "", text)
        return text[:500]

    def add_to_history(self, u, a):
        self.conversation_history.append({"user": u, "assistant": a})
        if len(self.conversation_history) > 10: self.conversation_history.pop(0)
