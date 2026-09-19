#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把构建好的静态站（publish/）部署到 Cloudflare Pages。

凭证来源：cl-kb/.cloudflare.json（本地文件，不进 publish、不提交）
{
  "account_id": "你的 Cloudflare Account ID",
  "api_token":  "具有 Account > Cloudflare Pages:Edit 权限的 API Token",
  "project_name": "cl-ai-kb"   # Pages 项目名，需在 Dashboard 先建好（Direct Upload 方式）
}

用法：
  python scripts/deploy_cloudflare.py
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)          # cl-kb/
WORKSPACE = os.path.dirname(ROOT)     # 工作区根（publish/ 在这里）
CFG = os.path.join(ROOT, ".cloudflare.json")
PUBLISH = os.path.join(WORKSPACE, "publish")

# wrangler 装在托管的 node workspace 下，需用其 JS 入口（.bin/wrangler 是 shell 脚本，不能直接用 node 跑）
NODE = "C:/Users/Lenovo/.workbuddy/binaries/node/versions/22.22.2-2/node.exe"
WRANGLER = "C:/Users/Lenovo/.workbuddy/binaries/node/workspace/node_modules/wrangler/bin/wrangler.js"


def load_cfg():
    if not os.path.exists(CFG):
        print(f"缺少凭证文件：{CFG}\n请创建该文件并填入 account_id / api_token / project_name。")
        sys.exit(2)
    with open(CFG, encoding="utf-8") as f:
        cfg = json.load(f)
    for k in ("account_id", "api_token", "project_name"):
        if not cfg.get(k):
            print(f"凭证文件缺少字段：{k}")
            sys.exit(2)
    return cfg


def main():
    if not os.path.isdir(PUBLISH):
        print(f"找不到构建产物目录：{PUBLISH}\n请先运行 npm run docs:build 生成 publish/")
        sys.exit(2)
    cfg = load_cfg()
    env = os.environ.copy()
    env["CLOUDFLARE_ACCOUNT_ID"] = cfg["account_id"]
    env["CLOUDFLARE_API_TOKEN"] = cfg["api_token"]

    cmd = [
        NODE, WRANGLER, "pages", "deploy", PUBLISH,
        "--project-name", cfg["project_name"],
        "--branch", "main",
        "--commit-dirty=true",
    ]
    print(">>> 开始推送到 Cloudflare Pages：", cfg["project_name"])
    r = subprocess.run(cmd, env=env)
    if r.returncode != 0:
        print(">>> Cloudflare 部署失败（见上方错误）。常见原因：")
        print("    1) project_name 在 Dashboard 还没建（Pages → 创建项目 → Direct Upload）")
        print("    2) api_token 权限不足（需要 Account > Cloudflare Pages: Edit）")
        print("    3) account_id 填错")
        sys.exit(r.returncode)
    print(">>> Cloudflare 部署成功。访问：")
    print(f"    https://{cfg['project_name']}.pages.dev")


if __name__ == "__main__":
    main()
