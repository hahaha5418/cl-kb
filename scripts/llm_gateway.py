#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一模型调用网关 (LLM Gateway)  v1.0
=====================================================================
供应商无关的大模型调用层。上层业务（热点中文化、详情库生成、教程生成…）
只调用 gateway.call() / gateway.json()；**换模型只改环境变量，不动业务代码**。

支持的供应商（默认优先级从高到低）
  1. qwen      通义千问（阿里云百炼）  https://dashscope.aliyuncs.com/compatible-mode/v1
  2. doubao    豆包（火山方舟 Ark）    https://ark.cn-beijing.volces.com/api/v3
  3. deepseek  DeepSeek 深度求索        https://api.deepseek.com/v1
  4. zhipu     智谱 GLM                https://open.bigmodel.cn/api/paas/v4
  5. moonshot  月之暗面 Kimi           https://api.moonshot.cn/v1
  6. openai    OpenAI 官方             https://api.openai.com/v1
  7. local     本地模型（Ollama 等）    http://localhost:11434/v1   ← 不需要 Key

密钥安全管理（按优先级解析，Key 绝不写进代码）
  1) 供应商专属环境变量：DASHSCOPE_API_KEY / ARK_API_KEY / DEEPSEEK_API_KEY …
  2) 项目根目录的 .env / .env.local（已在 .gitignore，永不入库）
  3) 兼容旧配置文件 scripts/ai_config.json（仅本地，已 gitignore，会提示迁移）

核心能力
  · call(prompt, system=...)    文本补全，返回 str 或 None
  · json(prompt, system=...)    强制 JSON 输出并解析，失败返回 None
  · chat(messages, ...)         多轮 / 自定义 messages
  · chat_stream(...)            流式输出（SSE），逐段 yield
  · 供应商自动切换：某个 Key 失效 / 欠费 / 模型未开通时，自动换下一个可用供应商
  · 限流与网络抖动自动退避重试（指数退避 + 随机抖动）
  · 用量日志 logs/llm-calls.jsonl（供应商 / 模型 / token / 耗时，**不记录 Key**）

CLI 诊断
  python scripts/llm_gateway.py providers    查看各供应商与密钥配置状态
  python scripts/llm_gateway.py check        逐个测试已配置供应商的连通性
  python scripts/llm_gateway.py chat "1+1=?" 命令行对话
  python scripts/llm_gateway.py json "..."   命令行 JSON 测试
  python scripts/llm_gateway.py env          查看环境变量 / 配置文件加载情况
  python scripts/llm_gateway.py selftest     离线自测（本地 mock，不消耗任何额度）

零依赖：只用 Python 标准库。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "scripts" / "ai_config.json"
LOG_DIR = ROOT / "logs"
LOG_FILE = LOG_DIR / "llm-calls.jsonl"
ENV_FILES = (".env", ".env.local", ".env.llm")

DEFAULT_SYSTEM = "你是一个简洁、准确的中文助手。"
JSON_SYSTEM = "你是一个简洁、准确的中文助手。只输出 JSON。"

# 可重试 / 不可重试 的错误类型
RETRYABLE = {"rate", "server", "network", "http", "unknown"}
FATAL = {"auth", "quota", "notfound", "badreq"}

VERSION = "1.0"

# ---------------------------------------------------------------------------
# 供应商注册表
#   envs   : 该供应商优先读取的环境变量（按序）
#   match  : 用于把旧配置里的 base_url 认领回某个供应商
#   needs_key=False 表示本地服务，不需要密钥
# ---------------------------------------------------------------------------
PROVIDERS = {
    "qwen": {
        "label": "通义千问 / 阿里云百炼",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "envs": ["DASHSCOPE_API_KEY", "QWEN_API_KEY", "TONGYI_API_KEY"],
        "model": "qwen-plus",
        "models": ["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long", "qwen3-8b"],
        "match": ["dashscope", "qwen"],
        "doc": "https://help.aliyun.com/zh/model-studio/get-api-key",
    },
    "doubao": {
        "label": "豆包 / 火山方舟 Ark",
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "envs": ["ARK_API_KEY", "DOUBAO_API_KEY", "VOLC_API_KEY"],
        "model": "doubao-seed-2-1-pro-260628",
        "models": [
            "doubao-seed-2-1-pro-260628",
            "doubao-seed-1-6-250615",
            "doubao-pro-32k",
            "doubao-lite-32k",
        ],
        "match": ["volces", "ark.cn", "doubao"],
        "doc": "https://www.volcengine.com/docs/82379/1399008",
        "note": "也可把 model 填成推理接入点 ID（ep- 开头）；模型需在控制台逐个开通",
    },
    "deepseek": {
        "label": "DeepSeek 深度求索",
        "base_url": "https://api.deepseek.com/v1",
        "envs": ["DEEPSEEK_API_KEY"],
        "model": "deepseek-chat",
        "models": ["deepseek-chat", "deepseek-reasoner"],
        "match": ["api.deepseek.com"],
        "doc": "https://platform.deepseek.com/api_keys",
    },
    "zhipu": {
        "label": "智谱 GLM",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "envs": ["ZHIPUAI_API_KEY", "ZHIPU_API_KEY", "GLM_API_KEY"],
        "model": "glm-4-flash",
        "models": ["glm-4-flash", "glm-4-air", "glm-4-plus", "glm-4.5-flash"],
        "match": ["bigmodel"],
        "doc": "https://open.bigmodel.cn/usercenter/apikeys",
    },
    "moonshot": {
        "label": "月之暗面 Kimi",
        "base_url": "https://api.moonshot.cn/v1",
        "envs": ["MOONSHOT_API_KEY", "KIMI_API_KEY"],
        "model": "moonshot-v1-8k",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "kimi-k2-0905-preview"],
        "match": ["moonshot"],
        "doc": "https://platform.moonshot.cn/console/api-keys",
    },
    "openai": {
        "label": "OpenAI 官方",
        "base_url": "https://api.openai.com/v1",
        "envs": ["OPENAI_API_KEY"],
        "model": "gpt-4o-mini",
        "models": ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini"],
        "match": ["api.openai.com"],
        "doc": "https://platform.openai.com/api-keys",
    },
    "local": {
        "label": "本地模型（Ollama / vLLM）",
        "base_url": "http://localhost:11434/v1",
        "envs": [],
        "model": "qwen2.5:7b",
        "models": ["qwen2.5:7b", "qwen2.5:14b", "llama3.1:8b"],
        "match": ["localhost", "127.0.0.1"],
        "needs_key": False,
        # 显式启用制：不设 OLLAMA_BASE_URL 就不进容灾链，避免没装 Ollama 时白失败一次
        "opt_in": True,
        "doc": "https://ollama.com/download",
    },
}

# 统一接入顺序（写死）：通义千问 → 豆包 → DeepSeek → 智谱
# 这是「团队决策」的优先顺序，谁的 Key 有效先用谁；某家失效/欠费/模型未开通自动切下一家。
# moonshot / openai / local 仍已注册在 PROVIDERS 里，可通过环境变量 LLM_ORDER 临时插入，
# 但默认链只包含上述四家（用户明确要求四家顺序写死）。
DEFAULT_ORDER = ["qwen", "doubao", "deepseek", "zhipu"]


# ---------------------------------------------------------------------------
# 环境变量装载
# ---------------------------------------------------------------------------

_ENV_LOADED: dict = {}


def load_env_files(force: bool = False) -> dict:
    """读取项目根的 .env / .env.local，写入 os.environ（不覆盖已存在的真实环境变量）。"""
    global _ENV_LOADED
    if _ENV_LOADED and not force:
        return _ENV_LOADED
    loaded: dict = {}
    for name in ENV_FILES:
        path = ROOT / name
        if not path.exists():
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for raw in text.splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            if key.startswith("export "):
                key = key[7:].strip()
            if not re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key):
                continue
            val = val.strip().strip('"').strip("'")
            loaded.setdefault(key, name)
            if key not in os.environ:
                os.environ[key] = val
    _ENV_LOADED = loaded
    return loaded


def mask(secret: str) -> str:
    """脱敏展示：sk-abcd…wxyz"""
    if not secret:
        return "(空)"
    s = str(secret)
    if len(s) <= 10:
        return s[:2] + "****"
    return f"{s[:6]}****{s[-4:]}"


# ---------------------------------------------------------------------------
# 异常与错误分类
# ---------------------------------------------------------------------------

class LLMError(Exception):
    """一次模型调用失败的统一异常。kind 决定后续策略（重试 / 换供应商 / 放弃）。"""

    def __init__(self, provider: str, kind: str, message: str, status=None):
        super().__init__(f"[{provider}] {kind}: {message}")
        self.provider = provider
        self.kind = kind
        self.message = message
        self.status = status


def _extract_error(body: str) -> str:
    """从错误响应体里挖出一句人话。"""
    if not body:
        return "(无响应体)"
    try:
        data = json.loads(body)
        if isinstance(data, dict):
            err = data.get("error")
            if isinstance(err, dict):
                for k in ("message", "msg", "detail"):
                    if err.get(k):
                        return str(err[k])[:300]
            if isinstance(err, str) and err:
                return err[:300]
            for k in ("message", "msg", "detail", "error_msg", "code"):
                if data.get(k):
                    return str(data[k])[:300]
    except Exception:
        pass
    return re.sub(r"\s+", " ", body).strip()[:300]


def classify(status: int, body: str) -> str:
    """把 HTTP 状态码 + 响应体映射成错误类型。"""
    low = (body or "").lower()
    if status in (401, 403):
        return "auth"
    if status == 404:
        return "notfound"
    if status == 429:
        return "rate"
    if status == 402:
        return "quota"
    if status == 400:
        # 额度/模型未开通有时也走 400
        if any(w in low for w in ("insufficient", "balance", "quota", "欠费", "余额")):
            return "quota"
        if any(w in low for w in ("model not", "not open", "未开通", "不存在")):
            return "notfound"
        return "badreq"
    if status >= 500:
        return "server"
    if any(w in low for w in ("insufficient", "balance", "quota", "欠费", "余额")):
        return "quota"
    return "http"


KIND_HINT = {
    "auth": "Key 无效或已过期",
    "quota": "余额不足 / 免费额度用尽",
    "notfound": "模型不存在或未开通（豆包需在控制台逐个开通）",
    "badreq": "请求参数被拒",
    "rate": "触发限流",
    "server": "服务端错误",
    "network": "网络不可达 / 超时",
    "http": "HTTP 异常",
}


# ---------------------------------------------------------------------------
# 用量日志
# ---------------------------------------------------------------------------

def record(log_enabled: bool, provider: str, model: str, ok: bool,
           kind: str, seconds: float, usage: dict | None = None, note: str = ""):
    if not log_enabled:
        return
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        usage = usage or {}
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "provider": provider,
            "model": model,
            "ok": bool(ok),
            "kind": kind,
            "seconds": round(seconds, 2),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
            "total_tokens": usage.get("total_tokens"),
        }
        if note:
            row["note"] = note
        with LOG_FILE.open("a", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:
        pass  # 日志失败绝不能影响主流程


# ---------------------------------------------------------------------------
# 网关主体
# ---------------------------------------------------------------------------

class Gateway:
    """统一模型调用网关。

    兼容旧接口：Gateway(cfg) 与老 ai_config.json 完全兼容，
    旧业务代码里的 ai.call() / ai.json() / ai.enabled 无需改动。
    """

    def __init__(self, cfg: dict | None = None, **overrides):
        cfg = dict(cfg or {})
        cfg.update(overrides)

        load_env_files()

        self.legacy_cfg = cfg
        self.enabled_cfg = bool(cfg.get("enabled", True))
        self.legacy_key = str(cfg.get("api_key") or "").strip()
        self.legacy_base = str(cfg.get("base_url") or "").strip().rstrip("/")
        self.legacy_model = str(cfg.get("model") or "").strip()
        self.legacy_temperature = cfg.get("temperature")
        self.legacy_max_tokens = cfg.get("max_tokens")

        # 运行期配置（环境变量优先于旧配置文件）
        def _num(name, default, cast=float):
            v = os.environ.get(name)
            if v in (None, ""):
                return default
            try:
                return cast(v)
            except Exception:
                return default

        self.temperature = _num("LLM_TEMPERATURE", self.legacy_temperature
                                if self.legacy_temperature is not None else 0.3, float)
        self.max_tokens = int(_num("LLM_MAX_TOKENS", self.legacy_max_tokens
                                   if self.legacy_max_tokens is not None else 1500, float))
        self.timeout = int(_num("LLM_TIMEOUT", 90, float))
        self.retries = max(1, int(_num("LLM_RETRIES", 2, float)))
        self.backoff = float(_num("LLM_BACKOFF", 1.5, float))
        self.fallback = os.environ.get("LLM_FALLBACK", "1") not in ("0", "false", "False")
        self.log_enabled = os.environ.get("LLM_LOG", "1") not in ("0", "false", "False")

        # 旧 base_url 认领到某个供应商（保持历史行为不变）
        # cfg 里可显式写 "provider": "qwen" 指定供应商；写了未知名字则按自定义端点处理
        forced = str(cfg.get("provider") or "").strip()
        if forced and forced in PROVIDERS:
            self.legacy_provider = forced
        elif forced:
            self.legacy_provider = None
        else:
            self.legacy_provider = self._sniff_provider(self.legacy_base)
        self.custom = None
        if (forced and forced not in PROVIDERS) or (self.legacy_base and not self.legacy_provider):
            # 未知 base_url：注册为一个自定义供应商，排在最末位兜底
            self.custom = {
                "label": forced or "自定义端点（旧 ai_config.json）",
                "base_url": self.legacy_base,
                "envs": [],
                "model": self.legacy_model or "",
                "match": [],
            }

        # 优先级顺序
        env_order = os.environ.get("LLM_ORDER", "").strip()
        env_force = os.environ.get("LLM_PROVIDER", "").strip()
        self.explicit = {x.strip() for x in env_order.split(",") if x.strip()}
        if env_force:
            self.explicit.add(env_force)
        order = [x.strip() for x in env_order.split(",") if x.strip()] if env_order else list(DEFAULT_ORDER)
        order = [x for x in order if x in PROVIDERS or x == "custom"]
        if self.custom and "custom" not in order:
            order.append("custom")
        self.order = order

        self._dead: set = set()          # 本次运行中已确认不可用的供应商（不再重试）
        self._failed_providers: list = []
        self.calls = 0

    # ---------------- 供应商解析 ----------------

    @staticmethod
    def _sniff_provider(base_url: str) -> str | None:
        low = (base_url or "").lower()
        if not low:
            return None
        for name, meta in PROVIDERS.items():
            for token in meta.get("match", []):
                if token in low:
                    return name
        return None

    def _spec(self, name: str) -> dict | None:
        if name == "custom":
            return self.custom
        return PROVIDERS.get(name)

    def key_of(self, name: str) -> str:
        """按「专属环境变量 → 通用环境变量 → 旧配置文件」解析密钥。"""
        spec = self._spec(name)
        if not spec:
            return ""
        for env_name in spec.get("envs", []):
            v = os.environ.get(env_name, "").strip()
            if v:
                return v
        if name == self.legacy_provider and self.legacy_key:
            return self.legacy_key
        if name == "custom" and self.legacy_key:
            return self.legacy_key
        # 通用变量：仅当 base_url 是自定义/旧配置端点时才使用，避免误用别家 Key
        return ""

    def model_of(self, name: str) -> str:
        """模型名解析，优先级：单家专属变量 → 全局 LLM_MODEL → 旧配置 → 内置默认。

        单家专属变量形如 QWEN_MODEL / DOUBAO_MODEL / DEEPSEEK_MODEL / ZHIPU_MODEL，
        用于某个账号的模型名与默认值不一致时单独调整（不会影响其它供应商）。
        """
        spec = self._spec(name) or {}
        per = os.environ.get(f"{name.upper()}_MODEL", "").strip()
        if per:
            return per
        forced = os.environ.get("LLM_MODEL", "").strip()
        if forced:
            return forced
        if name == self.legacy_provider and self.legacy_model:
            return self.legacy_model
        return spec.get("model", "")

    def base_of(self, name: str) -> str:
        if name == self.legacy_provider:
            env_key = self.key_of(name)
            # 只有走「专属环境变量」时才用官方端点；走旧配置时用旧 base_url
            legacy_used = bool(self.legacy_key) and env_key == self.legacy_key
            if self.legacy_base and legacy_used:
                return self.legacy_base
        spec = self._spec(name) or {}
        if name == "local":
            return os.environ.get("OLLAMA_BASE_URL", spec.get("base_url", "")).rstrip("/")
        return str(spec.get("base_url", "")).rstrip("/")

    def usable(self, name: str) -> bool:
        spec = self._spec(name)
        if not spec or name in self._dead:
            return False
        if not self.enabled_cfg:
            return False
        if spec.get("opt_in") and not os.environ.get("OLLAMA_BASE_URL", "").strip() \
                and name not in getattr(self, "explicit", set()):
            return False
        if spec.get("needs_key", True) and not self.key_of(name):
            return False
        return True

    def chain(self, provider: str | None = None) -> list:
        """本次调用可用的供应商列表（按优先级）。"""
        if provider:
            names = [provider]
        else:
            env_force = os.environ.get("LLM_PROVIDER", "").strip()
            if env_force:
                names = [env_force]
            else:
                names = list(self.order)
                if not self.fallback:
                    names = names[:1]
        return [n for n in names if self.usable(n)]

    @property
    def enabled(self) -> bool:
        return bool(self.chain())

    @property
    def provider_name(self) -> str:
        ch = self.chain()
        return ch[0] if ch else ""

    @property
    def model(self) -> str:
        ch = self.chain()
        return self.model_of(ch[0]) if ch else ""

    def status(self) -> list:
        """诊断信息：每个供应商的配置状态。"""
        rows = []
        for name in self.order:
            spec = self._spec(name) or {}
            key = self.key_of(name)
            rows.append({
                "name": name,
                "label": spec.get("label", name),
                "base_url": self.base_of(name),
                "model": self.model_of(name),
                "env": (spec.get("envs") or ["(无需 Key)"])[0],
                "has_key": bool(key),
                "key_masked": mask(key) if key else "",
                "is_local": not spec.get("needs_key", True),
                "opt_in": bool(spec.get("opt_in")),
                "opt_in_on": (not spec.get("opt_in"))
                             or bool(os.environ.get("OLLAMA_BASE_URL", "").strip())
                             or name in getattr(self, "explicit", set()),
                "dead": name in self._dead,
                "usable": self.usable(name),
            })
        return rows

    def first_configured_env(self, name: str) -> str:
        """该供应商当前实际生效的环境变量名（用于提示用户配哪个变量）。"""
        spec = self._spec(name) or {}
        for env_name in spec.get("envs", []):
            if os.environ.get(env_name, "").strip():
                return env_name
        return (spec.get("envs") or [""])[0]

    # ---------------- HTTP 调用 ----------------

    def _http(self, url: str, payload: dict, key: str, timeout: int, stream: bool = False):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/event-stream" if stream else "application/json",
            "User-Agent": f"cl-kb-llm-gateway/{VERSION}",
        }
        if key:
            headers["Authorization"] = "Bearer " + key
        req = urllib.request.Request(url, data=body, headers=headers)
        try:
            return urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as e:
            raw = ""
            try:
                raw = e.read().decode("utf-8", "ignore")
            except Exception:
                pass
            kind = classify(e.code, raw)
            raise LLMError("", kind, f"HTTP {e.code} {_extract_error(raw)}", e.code) from None
        except urllib.error.URLError as e:
            raise LLMError("", "network", f"连接失败: {getattr(e, 'reason', e)}") from None
        except (TimeoutError, OSError) as e:
            raise LLMError("", "network", f"{type(e).__name__}: {e}") from None

    def _request(self, provider: str, messages: list, model: str | None,
                 temperature, max_tokens, timeout, stream: bool = False):
        spec = self._spec(provider) or {}
        base = self.base_of(provider)
        if not base:
            raise LLMError(provider, "badreq", "未配置 base_url")
        url = base.rstrip("/") + "/chat/completions"
        payload = {
            "model": model or self.model_of(provider),
            "messages": messages,
            "temperature": self.temperature if temperature is None else temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }
        if stream:
            payload["stream"] = True
        key = self.key_of(provider)
        started = time.time()
        try:
            resp = self._http(url, payload, key, timeout or self.timeout, stream=stream)
        except LLMError as e:
            e.provider = provider
            record(self.log_enabled, provider, payload["model"], False, e.kind,
                   time.time() - started, note=KIND_HINT.get(e.kind, ""))
            raise
        if stream:
            return self._iter_sse(resp), None
        with resp:
            raw = resp.read().decode("utf-8", "ignore")
        try:
            data = json.loads(raw)
        except Exception:
            record(self.log_enabled, provider, payload["model"], False, "unknown",
                   time.time() - started, note="响应非 JSON")
            raise LLMError(provider, "unknown", f"响应无法解析: {raw[:200]}") from None
        text = self._pick_text(data)
        if text is None:
            record(self.log_enabled, provider, payload["model"], False, "unknown",
                   time.time() - started, note="响应缺少 content")
            raise LLMError(provider, "unknown", f"响应缺少 content: {raw[:200]}")
        usage = data.get("usage") or {}
        record(self.log_enabled, provider, payload["model"], True, "ok",
               time.time() - started, usage=usage)
        return text, data

    @staticmethod
    def _pick_text(data: dict) -> str | None:
        """兼容 OpenAI 风格 / DashScope 原生风格 的返回结构。"""
        try:
            choices = data.get("choices")
            if choices:
                msg = choices[0].get("message") or {}
                content = msg.get("content")
                if isinstance(content, list):  # 多模态分段返回
                    parts = [c.get("text", "") for c in content if isinstance(c, dict)]
                    content = "".join(parts)
                if content:
                    return str(content)
                if choices[0].get("text"):
                    return str(choices[0]["text"])
            out = data.get("output")
            if isinstance(out, dict):
                if out.get("text"):
                    return str(out["text"])
                ch = out.get("choices")
                if ch and isinstance(ch, list):
                    m = ch[0].get("message") or {}
                    if m.get("content"):
                        return str(m["content"])
            if data.get("response"):
                return str(data["response"])
        except Exception:
            return None
        return None

    @staticmethod
    def _iter_sse(resp):
        """逐行解析 SSE 流，yield 文本增量。"""
        try:
            for raw in resp:
                line = raw.decode("utf-8", "ignore").strip()
                if not line or line.startswith(":"):
                    continue
                if not line.startswith("data:"):
                    continue
                chunk = line[5:].strip()
                if chunk == "[DONE]":
                    break
                try:
                    data = json.loads(chunk)
                except Exception:
                    continue
                choices = data.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    piece = delta.get("content")
                    if piece:
                        yield piece
        finally:
            try:
                resp.close()
            except Exception:
                pass

    # ---------------- 对外统一接口 ----------------

    @staticmethod
    def _normalize(messages) -> list:
        if isinstance(messages, str):
            return [{"role": "user", "content": messages}]
        return messages

    def chat(self, messages, *, provider=None, model=None, temperature=None,
             max_tokens=None, timeout=None, retries=None, verbose=False) -> str | None:
        """多轮对话，返回纯文本；全部供应商都失败时返回 None（绝不抛异常）。

        messages 可以是字符串（自动包成单轮 user），也可以是
        [{"role": "system"|"user"|"assistant", "content": "..."}, ...]
        """
        msgs = self._normalize(messages)
        names = self.chain(provider)
        if not names:
            if verbose and not self.enabled_cfg:
                print("    [网关] 已禁用（配置 enabled=false）")
            return None
        attempts = retries or self.retries
        last_err = None

        for idx, name in enumerate(names):
            for attempt in range(1, attempts + 1):
                try:
                    text, _ = self._request(name, msgs, model, temperature,
                                            max_tokens, timeout)
                    self.calls += 1
                    if idx > 0 or verbose:
                        spec = self._spec(name) or {}
                        print(f"    [网关] 使用 {spec.get('label', name)}"
                              f"（{self.model_of(name)}）")
                    return text
                except LLMError as e:
                    last_err = e
                    hint = KIND_HINT.get(e.kind, "")
                    if e.kind in FATAL:
                        # Key 失效 / 模型未开通 / 欠费：不再重试该供应商，直接换下一个
                        self._dead.add(name)
                        self._failed_providers.append(name)
                        print(f"    [网关] {name} 不可用（{e.kind}：{hint}）→ 切换下一个")
                        break
                    if attempt < attempts:
                        wait = self.backoff ** attempt + random.uniform(0, 0.6)
                        time.sleep(wait)
                        continue
                    self._failed_providers.append(name)
                    print(f"    [网关] {name} 重试 {attempts} 次仍失败（{e.kind}：{hint}）→ 切换下一个")
                    break

        if last_err:
            print(f"    [网关] 所有可用供应商均失败，最后一次：{last_err.message[:160]}")
        return None

    def chat_stream(self, messages, *, provider=None, model=None, temperature=None,
                    max_tokens=None, timeout=None):
        """流式输出：逐段 yield 文本增量；失败时返回空迭代（不抛异常）。"""
        msgs = self._normalize(messages)
        for name in self.chain(provider):
            try:
                gen = self._request(name, msgs, model, temperature, max_tokens,
                                    timeout, stream=True)[0]
                for piece in gen:
                    yield piece
                return
            except LLMError as e:
                if e.kind in FATAL:
                    self._dead.add(name)
                continue

    def call(self, prompt: str, system: str = DEFAULT_SYSTEM,
             max_tokens=None, provider=None, model=None) -> str | None:
        """单轮补全（兼容旧接口）。"""
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return self.chat(msgs, provider=provider, model=model, max_tokens=max_tokens)

    def json(self, prompt: str, system: str = JSON_SYSTEM, max_tokens=None,
             provider=None, model=None):
        """强制 JSON：返回 dict/list，解析失败返回 None（兼容旧接口）。"""
        text = self.call(prompt, system=system, max_tokens=max_tokens,
                         provider=provider, model=model)
        return parse_json(text)

    # ---------------- 诊断 ----------------

    def check(self, only: str | None = None) -> list:
        """逐个供应商做一次真实调用，返回结果表。"""
        results = []
        names = [only] if only else [n for n in self.order if self.key_of(n)]
        for name in names:
            spec = self._spec(name) or {}
            if not self.usable(name):
                results.append({"name": name, "ok": False,
                                "detail": "未配置密钥或已禁用", "elapsed": 0})
                continue
            model = self.model_of(name)
            t0 = time.time()
            try:
                text, _ = self._request(name, [{"role": "user", "content": "请只回复两个字：正常"}],
                                        model, 0.1, 16, min(self.timeout, 45))
                results.append({"name": name, "ok": True,
                                "detail": (text or "").strip().replace("\n", " ")[:40],
                                "elapsed": time.time() - t0, "model": model})
            except LLMError as e:
                results.append({"name": name, "ok": False,
                                "detail": f"{e.kind} {KIND_HINT.get(e.kind, '')} {e.message[:100]}",
                                "elapsed": time.time() - t0, "model": model})
        return results


# 向后兼容：旧代码 `from ai_enrich import AI` / `AI(cfg)` 继续可用
AI = Gateway


def parse_json(text: str | None):
    """从模型输出里稳健地抽出 JSON（容忍 ```json 围栏与前后废话）。"""
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", t).strip()
    try:
        return json.loads(t)
    except Exception:
        pass
    m = re.search(r"(\{[\s\S]*\}|\[[\s\S]*\])", t)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _display_width(s) -> int:
    """中文按 2 个字符宽计算，保证 CLI 表格对齐。"""
    import unicodedata
    return sum(2 if unicodedata.east_asian_width(ch) in "WF" else 1 for ch in str(s))


def _pad(s, width: int) -> str:
    s = str(s)
    return s + " " * max(0, width - _display_width(s))


def _cmd_providers():
    gw = Gateway(_load_legacy_cfg())
    print(f"\n统一模型调用网关 v{VERSION}   工作目录：{ROOT}")
    print("=" * 84)
    print(f"{_pad('键', 10)}{_pad('供应商', 26)}{_pad('环境变量', 22)}{_pad('密钥', 18)}状态")
    print("-" * 84)
    for row in gw.status():
        key_show = row["key_masked"] if row["has_key"] else ("无需" if row["is_local"] else "未配置")
        if row["usable"]:
            state = "✅ 可用"
        elif row["opt_in"] and not row["opt_in_on"]:
            state = "— 可选未启用"
        elif row["has_key"] or row["is_local"]:
            state = "⏸ 本轮已禁用"
        else:
            state = "— 未配置"
        print(f"{_pad(row['name'], 10)}{_pad(row['label'], 26)}"
              f"{_pad(row['env'], 22)}{_pad(key_show, 18)}{state}")
    print("-" * 84)
    active = gw.chain()
    if active:
        n = active[0]
        label = (gw._spec(n) or {}).get("label", n)
        print(f"当前生效：{label} / {gw.model_of(n)}")
        print(f"调用顺序：{' → '.join(active)}")
        if len(active) == 1:
            print("提示：再配 1~2 个其它供应商的环境变量，即可获得自动容灾切换能力。")
    else:
        print("⚠️  没有任何供应商可用 —— 业务脚本会自动降级（照常运行，只是没有 AI 增强）。")
        print("    最快启用方式：把 cl-kb/.env.example 复制成 cl-kb/.env，填一个 Key 即可。")
    print()


def _cmd_env():
    loaded = load_env_files(force=True)
    print(f"\n环境变量装载情况（工作目录：{ROOT}）")
    print("=" * 78)
    for name in ENV_FILES:
        path = ROOT / name
        print(f"  {name:12}{'✅ 存在' if path.exists() else '—  不存在'}   {path}")
    print("-" * 78)
    names = set()
    for meta in PROVIDERS.values():
        names.update(meta.get("envs", []))
    names.update(["LLM_PROVIDER", "LLM_MODEL", "LLM_ORDER", "LLM_FALLBACK",
                  "LLM_TEMPERATURE", "LLM_MAX_TOKENS", "LLM_TIMEOUT",
                  "LLM_RETRIES", "LLM_LOG", "OLLAMA_BASE_URL"])
    names.update(f"{k.upper()}_MODEL" for k in PROVIDERS)   # 单家模型名覆盖
    for n in sorted(names):
        v = os.environ.get(n)
        if v is None:
            continue
        src = loaded.get(n) or "系统环境"
        shown = mask(v) if re.search(r"(KEY|TOKEN|SECRET)", n) else v
        print(f"  {n:22}{shown:30}（来源：{src}）")
    print(f"\n  配置文件兼容：{CONFIG_FILE} "
          f"{'✅ 存在（建议迁移到 .env 后删除）' if CONFIG_FILE.exists() else '— 不存在'}")
    print()


def _cmd_check(only=None):
    gw = Gateway(_load_legacy_cfg())
    rows = gw.check(only)
    print(f"\n连通性测试（真实调用，会产生极少量的 token 消耗）")
    print("=" * 78)
    if not rows:
        print("  没有任何已配置的供应商可测试。")
        print("  请复制 cl-kb/.env.example 为 cl-kb/.env 并填入至少一个 Key。")
        print()
        return 1
    ok = 0
    for r in rows:
        if r["ok"]:
            ok += 1
            print(f"  ✅ {r['name']:9}{r.get('model', ''):26}{r['elapsed']:.2f}s   返回：{r['detail']}")
        else:
            print(f"  ❌ {r['name']:9}{r.get('model', ''):26}          {r['detail']}")
    print("-" * 78)
    print(f"  {ok}/{len(rows)} 个供应商可用。")
    print()
    return 0 if ok else 1


def _cmd_failover():
    """多模型故障切换演练（真机，不是 mock）。

    做法：把当前优先级最高的那家供应商的 Key 临时换成无效值，然后正常发起一次调用。
    预期：该家被判为不可用（401/鉴权失败）→ 网关自动降级到下一家 → 仍返回正常答案。
    这是「多模型自动切换」最直接的验证方式，只消耗几十个 token。
    """
    gw = Gateway(_load_legacy_cfg())
    chain = gw.chain()
    print("\n多模型故障切换演练（真机调用）")
    print("=" * 78)
    if len(chain) < 2:
        print(f"  当前只有 {len(chain)} 家供应商可用，无法演练「切换」。")
        print("  至少再配 1 家的 Key（例如 DASHSCOPE_API_KEY），然后重跑本命令。")
        print()
        return 1

    first = chain[0]
    spec = gw._spec(first) or {}
    env_names = [e for e in spec.get("envs", []) if e]
    if not env_names:
        print(f"  {first} 没有声明环境变量别名，无法注入无效 Key，跳过演练。")
        print()
        return 1

    second = chain[1]
    first_label = spec.get("label", first)
    second_label = (gw._spec(second) or {}).get("label", second)
    print(f"  可用链：{' → '.join(chain)}")
    print(f"  演练内容：把「{first_label}」的 Key 临时改成无效值，")
    print(f"           看网关能否自动切到「{second_label}」继续干活。")
    print("-" * 78)

    saved = {k: os.environ.get(k) for k in env_names}
    for k in env_names:          # 先清掉全部别名，确保一定走无效值
        os.environ.pop(k, None)
    os.environ[env_names[0]] = "invalid-key-for-failover-test"

    winner = None
    text = None
    elapsed = 0.0
    try:
        gw2 = Gateway(_load_legacy_cfg())
        gw2.backoff = 1.01      # 演练时把退避压到最小，免得等太久
        t0 = time.time()
        text = gw2.call("请只回复两个字：正常", max_tokens=16)
        elapsed = time.time() - t0
        failed = list(getattr(gw2, "_failed_providers", []))
        if text:
            winner = next((n for n in chain if n not in failed), None)
    finally:
        for k in env_names:     # 无论如何都要复原真实 Key
            if saved.get(k) is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]

    print("-" * 78)
    if text and winner:
        winner_label = (gw2._spec(winner) or {}).get("label", winner)
        print(f"  ✅ 切换成功：{first_label} 被判定不可用 → 「{winner_label}」自动接管")
        print(f"     接管方返回：{text.strip()[:40]}    总耗时 {elapsed:.2f}s")
    elif text:
        print(f"  ⚠️  有返回但无法定位接管方，返回：{text.strip()[:40]}")
    else:
        print("  ❌ 切换失败：所有供应商都没能返回内容。")
        print("     请先逐家排查：python scripts/llm_gateway.py check")

    again = Gateway(_load_legacy_cfg())
    live = again.chain()
    print(f"  复原后可用链：{' → '.join(live) if live else '(无)'}")
    print()
    return 0 if text else 1


def _cmd_chat(prompt, as_json=False):
    gw = Gateway(_load_legacy_cfg())
    if not gw.enabled:
        print("网关未启用：没有可用供应商。请先配置 cl-kb/.env 中的 API Key。")
        return 1
    out = gw.json(prompt) if as_json else gw.call(prompt)
    print(out if out is not None else "(无返回)")
    return 0


def _cmd_selftest():
    """离线自测：本地 mock 服务验证 重试 / 切换 / JSON 解析 / 限流退避。"""
    import http.server
    import socketserver

    state = {"flaky": 0}
    seen = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _reply(self, code, obj):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n).decode("utf-8"))
            model = payload.get("model", "")
            auth = self.headers.get("Authorization", "")
            seen.append((model, auth))
            if "/bad/" in self.path:
                self._reply(401, {"error": {"message": "invalid api key"}})
            elif "/quota/" in self.path:
                self._reply(400, {"error": {"message": "insufficient balance"}})
            elif "/flaky/" in self.path:
                state["flaky"] += 1
                if state["flaky"] == 1:
                    self._reply(429, {"error": {"message": "rate limit exceeded"}})
                else:
                    self._reply(200, {"choices": [{"message": {"content": "重试后成功"}}],
                                      "usage": {"total_tokens": 7}})
            elif "/json/" in self.path:
                self._reply(200, {"choices": [{"message": {
                    "content": "```json\n{\"要点\": [\"A\", \"B\"], \"ok\": true}\n```"}}]})
            elif "/dash/" in self.path:
                self._reply(200, {"output": {"text": "DashScope 原生结构"},
                                  "usage": {"input_tokens": 3, "output_tokens": 2}})
            elif "/sse/" in self.path:
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.end_headers()
                for piece in ("流", "式", "成功"):
                    chunk = {"choices": [{"delta": {"content": piece}}]}
                    self.wfile.write(
                        ("data: " + json.dumps(chunk, ensure_ascii=False) + "\n\n").encode("utf-8"))
                    self.wfile.flush()
                self.wfile.write(b"data: [DONE]\n\n")
                self.wfile.flush()
            else:
                self._reply(200, {"choices": [{"message": {"content": "正常"}}]})

    srv = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{port}"

    print("\n离线自测（本地 mock，不联网、不消耗任何额度）")
    print("=" * 78)
    passed = failed = 0

    def case(title, cond, extra=""):
        nonlocal passed, failed
        if cond:
            passed += 1
            print(f"  ✅ {title}")
        else:
            failed += 1
            print(f"  ❌ {title} {extra}")

    def gw(path, **env):
        """只挂 mock 供应商并锁死 order，确保自测绝不触碰真实 API。"""
        cfg = {"enabled": True, "provider": "mock",
               "base_url": base + path, "model": "mock-model",
               "api_key": "test-key-1234567890", "temperature": 0, "max_tokens": 64}
        old = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            g = Gateway(cfg)
        finally:
            for k, v in old.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
        g.log_enabled = False
        g.backoff = 1.01
        g.order = ["custom"]
        return g

    # 1 基础调用
    g = gw("/ok/")
    case("基础调用返回内容", g.call("hi") == "正常")
    case("enabled 属性正确", g.enabled is True)

    # 2 JSON 围栏解析
    g = gw("/json/")
    obj = g.json("hi")
    case("JSON 围栏解析", isinstance(obj, dict) and obj.get("ok") is True,
         f"得到 {obj!r}")
    case("中文键保留", obj and obj.get("要点") == ["A", "B"])

    # 3 限流退避重试（第 1 次 429，第 2 次 200）
    state["flaky"] = 0
    g = gw("/flaky/")
    g.retries = 3
    case("429 限流自动重试成功", g.call("hi") == "重试后成功",
         f"flaky={state['flaky']}")

    # 4 DashScope 原生返回结构
    g = gw("/dash/")
    case("兼容 DashScope 原生返回", g.call("hi") == "DashScope 原生结构")

    # 5 Key 无效 → 标记不可用
    g = gw("/bad/")
    case("401 返回 None 不抛异常", g.call("hi") is None)
    case("401 后供应商被标记 dead", "custom" in g._dead or not g.enabled)

    # 6 欠费 → 归类 quota
    g = gw("/quota/")
    g.call("hi")
    case("余额不足归类为 quota", ("custom" in g._dead))

    # 7 多供应商容灾切换：第一个 Key 失效 → 自动切到第二个
    os.environ["OLLAMA_BASE_URL"] = base + "/ok/"
    try:
        g = Gateway({"enabled": True, "provider": "mock", "base_url": base + "/bad/",
                     "model": "m1", "api_key": "k1", "temperature": 0})
        g.log_enabled = False
        g.backoff = 1.01
        g.order = ["custom", "local"]
        text = g.call("hi")
        case("供应商自动切换（坏 Key → 好端点）", text == "正常", f"得到 {text!r}")
        case("失效供应商被记入黑名单", "custom" in g._dead)
    finally:
        os.environ.pop("OLLAMA_BASE_URL", None)

    # 8 SSE 流式解析
    g = gw("/sse/")
    case("SSE 流式解析", "".join(g.chat_stream("hi")) == "流式成功")

    # 9 无 Key 优雅降级（不报错、不阻塞流水线）
    g = Gateway({"enabled": True, "provider": "mock",
                 "base_url": "https://api.example.com/v1", "model": "x"})
    g.order = ["custom"]
    case("无任何 Key 时 enabled=False", g.enabled is False)
    case("无 Key 时 call 返回 None", g.call("hi") is None)

    srv.shutdown()
    print("-" * 78)
    print(f"  自测结果：{passed} 通过 / {failed} 失败\n")
    return 0 if failed == 0 else 1


def _cmd_migrate(write=False):
    """把旧 scripts/ai_config.json 里的明文 Key 迁移到 .env（环境变量化管理）。"""
    cfg = _load_legacy_cfg()
    print(f"\n密钥迁移：scripts/ai_config.json → {ROOT / '.env'}")
    print("=" * 78)
    if not cfg:
        print("  未找到旧配置文件，无需迁移。\n")
        return 0

    base = str(cfg.get("base_url") or "")
    name = str(cfg.get("provider") or "").strip() or Gateway._sniff_provider(base) or "custom"
    spec = PROVIDERS.get(name) or {}
    env_name = (spec.get("envs") or [None])[0]
    key = str(cfg.get("api_key") or "").strip()

    print(f"  旧配置 base_url : {base or '(空)'}")
    print(f"  识别为供应商     : {spec.get('label', name)}")
    print(f"  目标环境变量     : {env_name or '(未知端点，请手工配置 LLM_BASE_URL)'}")
    print(f"  密钥             : {mask(key) if key else '(空)'}")

    existing = load_env_files(force=True)
    lines = []
    if env_name and key:
        if env_name in existing or os.environ.get(env_name):
            print(f"  ⏭  {env_name} 已存在，跳过（不覆盖现有值）")
        else:
            lines.append(f"{env_name}={key}")
    for k, src in (("model", "LLM_MODEL"), ("temperature", "LLM_TEMPERATURE"),
                   ("max_tokens", "LLM_MAX_TOKENS")):
        v = cfg.get(k)
        if v not in (None, ""):
            lines.append(f"{src}={v}")

    if not lines:
        print("\n  没有可迁移的内容。\n")
        return 0

    print("\n  将写入以下内容（不含其它 Key）：")
    for ln in lines:
        k, _, v = ln.partition("=")
        print(f"    {k}={mask(v) if 'KEY' in k else v}")

    if not write:
        print("\n  这是预演（未写入）。确认无误后执行：")
        print("    python scripts/llm_gateway.py migrate --write\n")
        return 0

    env_path = ROOT / ".env"
    header = ""
    if not env_path.exists():
        header = ("# 由 llm_gateway.py migrate 从 scripts/ai_config.json 迁移生成\n"
                  "# 本文件已被 .gitignore 忽略，不会提交到 GitHub\n")
    with env_path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(header + "\n".join(lines) + "\n")
    print(f"\n  ✅ 已写入 {env_path}")
    print("  下一步：")
    print("    1) 运行  python scripts/llm_gateway.py providers   确认识别成功")
    print("    2) 确认无误后，可删除明文配置 scripts/ai_config.json（它已不再必需）\n")
    return 0


def _load_legacy_cfg() -> dict:
    if CONFIG_FILE.exists():
        try:
            return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[警告] 读取 {CONFIG_FILE} 失败: {e}")
    return {}


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="llm_gateway.py",
        description="统一模型调用网关 —— 通义千问 / 豆包 / DeepSeek / 智谱 / Kimi / OpenAI / 本地模型")
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("providers", help="查看供应商与密钥配置状态")
    sub.add_parser("env", help="查看环境变量与配置文件加载情况")
    p_check = sub.add_parser("check", help="逐个测试已配置供应商的连通性")
    p_check.add_argument("--provider", default=None, help="只测某一家")
    sub.add_parser("failover", help="真机演练：故意让首选供应商失效，验证自动切换")
    p_chat = sub.add_parser("chat", help="命令行对话")
    p_chat.add_argument("prompt")
    p_json = sub.add_parser("json", help="命令行 JSON 输出测试")
    p_json.add_argument("prompt")
    sub.add_parser("selftest", help="离线自测（本地 mock，不消耗额度）")
    p_mig = sub.add_parser("migrate", help="把旧 ai_config.json 的明文 Key 迁移到 .env")
    p_mig.add_argument("--write", action="store_true", help="真正写入（默认只预演）")

    args = parser.parse_args(argv)
    cmd = args.cmd or "providers"

    if cmd == "providers":
        _cmd_providers()
        return 0
    if cmd == "env":
        _cmd_env()
        return 0
    if cmd == "check":
        return _cmd_check(args.provider)
    if cmd == "failover":
        return _cmd_failover()
    if cmd == "chat":
        return _cmd_chat(args.prompt, as_json=False)
    if cmd == "json":
        return _cmd_chat(args.prompt, as_json=True)
    if cmd == "selftest":
        return _cmd_selftest()
    if cmd == "migrate":
        return _cmd_migrate(args.write)
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
