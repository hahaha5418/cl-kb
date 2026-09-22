#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地容灾演练（零外网、零密钥）
------------------------------------------------------------
用两个本地 mock 服务器扮演大模型供应商，真刀真枪跑网关的完整链路：
  · 主供应商（智谱替身）：可配置「一直 500」或「429 两次后恢复」
  · 备供应商（DeepSeek 替身）：正常返回
覆盖三个场景：
  1. 主供应商彻底挂掉 → 重试耗尽 → 自动切换备用 → 拿到结果
  2. 主供应商间歇限流(429) → 指数退避重试 → 不切换就成功
  3. 全部供应商阵亡 → 返回 None 不抛异常（业务优雅降级）
这样一旦用户填了真实 DEEPSEEK_API_KEY，切换行为与演练完全同构。

用法：python scripts/drill_failover_local.py
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from llm_gateway import Gateway  # noqa: E402


class MockLLMHandler(BaseHTTPRequestHandler):
    """OpenAI 兼容 mock。行为由服务器实例的 state 字典驱动：
    mode: 'down'（永远 500）| 'flaky'（前 N 次 429 后 200）| 'ok'（永远 200）"""
    server_version = "MockLLM/1.0"

    def log_message(self, *args):  # 静默访问日志
        pass

    def do_POST(self):
        state = self.server.state
        state["hits"] = state.get("hits", 0) + 1
        mode = state.get("mode", "ok")

        if mode == "down":
            self._reply(500, {"error": {"message": "internal server error (mock)"}})
            return
        if mode == "flaky" and state["hits"] <= state.get("flaky_times", 2):
            self._reply(429, {"error": {"message": "rate limit exceeded (mock)"}})
            return

        # 正常返回一个最小 OpenAI 兼容补全
        try:
            length = int(self.headers.get("Content-Length") or 0)
            req = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            req = {}
        content = state.get("reply", f"mock-ok(#{state['hits']})")
        self._reply(200, {
            "id": "chatcmpl-mock", "object": "chat.completion", "created": 0,
            "model": req.get("model") or "mock-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content},
                         "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
        })

    def _reply(self, code, obj):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _lan_ip():
    """拿一个非回环本机 IP：网关会把 127.0.0.1/localhost 嗅探成 local 供应商，
    会和备用通道(Ollama 端点)撞车。用局域网 IP 让主替身走「自定义供应商」通道。
    UDP connect 不发任何数据包，纯本机路由表查询。"""
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.0.2.1", 9))  # TEST-NET 地址，UDP 不会真正发包
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip if ip != "127.0.0.1" else socket.gethostbyname(socket.gethostname())


def start_mock(mode, reply=None):
    srv = ThreadingHTTPServer(("0.0.0.0", 0), MockLLMHandler)
    srv.state = {"mode": mode, "reply": reply}
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv


def build_gateway(primary_port, backup_port):
    """主供应商 = legacy cfg 端点（primary，走 custom 通道）；
    备供应商 = OLLAMA_BASE_URL（local 通道，用回环地址）。"""
    cfg = {
        "enabled": True,
        "base_url": f"http://{_lan_ip()}:{primary_port}/v1",
        "api_key": "mock-key",
        "model": "glm-4-flash",
    }
    import os
    os.environ["OLLAMA_BASE_URL"] = f"http://127.0.0.1:{backup_port}/v1"
    os.environ["LLM_ORDER"] = "custom,local"
    g = Gateway(cfg)
    g.retries = 2        # 每家最多重试 2 次（演练提速）
    g.backoff = 1.01     # 退避压到最小
    return g


def main():
    print("本地容灾演练（零外网 / 零密钥，mock 服务器扮演供应商）")
    print("=" * 64)
    results = []

    # 场景 1：主供应商彻底宕机 → 切换备用成功
    primary = start_mock("down")
    backup = start_mock("ok", reply="备用链接管上了！")
    g = build_gateway(primary.server_address[1], backup.server_address[1])
    print(f"\n[场景1] 主供应商永远 500（模拟智谱挂了），备用正常")
    print(f"  链路：{g.chain()}")
    r = g.call("你好")
    ok1 = (r == "备用链接管上了！")
    results.append(("主挂→自动切换备用→拿到结果", ok1))
    print(f"  返回：{r!r} → {'✅ 通过' if ok1 else '❌ 失败'}")
    primary.shutdown(); backup.shutdown()

    # 场景 2：主供应商 429 两次后恢复 → 不切换，重试即成功
    primary = start_mock("flaky", reply="重试后成功！")
    backup = start_mock("ok", reply="不应该走到备用")
    g = build_gateway(primary.server_address[1], backup.server_address[1])
    g.retries = 3  # 前 2 次 429 + 第 3 次恢复 → 必须在主供应商内重试成功
    print(f"\n[场景2] 主供应商前 2 次 429 限流后恢复（模拟间歇性限流）")
    r = g.call("你好")
    ok2 = (r == "重试后成功！")
    results.append(("间歇限流→退避重试→原地成功", ok2))
    print(f"  返回：{r!r} → {'✅ 通过' if ok2 else '❌ 失败'}")
    primary.shutdown(); backup.shutdown()

    # 场景 3：全部供应商阵亡 → None 不抛异常
    primary = start_mock("down")
    backup = start_mock("down")
    g = build_gateway(primary.server_address[1], backup.server_address[1])
    print(f"\n[场景3] 主备全部宕机（模拟全网故障）")
    try:
        r = g.call("你好")
        ok3 = (r is None)
        err = None
    except Exception as e:  # pragma: no cover
        r, ok3, err = None, False, e
    results.append(("全阵亡→返回None不抛异常", ok3))
    print(f"  返回：{r!r} 异常：{err} → {'✅ 通过' if ok3 else '❌ 失败'}")
    primary.shutdown(); backup.shutdown()

    print("\n" + "=" * 64)
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'✅' if ok else '❌'} {name}")
    print(f"演练结果：{passed}/{len(results)} 通过")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
