#!/usr/bin/env python3
"""
build_dist.py — 产出自包含、可双击 / 可部署的前端。

流程：先编译 KB → data.json，再把数据内联进 index.html，写到 dist/index.html。
产物是单文件（无需服务、无需 fetch）：双击可看，也可丢任意静态托管（Vercel / Netlify /
GitHub Pages）或 visual-explainer:share-page 分享。

用法：  python3 frontend/build_dist.py
"""
import json
import subprocess
import sys
from pathlib import Path

FE = Path(__file__).resolve().parent
ROOT = FE.parent
BUILDER = ROOT / "Knowledge_Wiki" / "scripts" / "build_frontend_data.py"


def main():
    # 1. 编译知识库 → data.json（确保是最新的）
    subprocess.run([sys.executable, str(BUILDER)], check=True)

    html = (FE / "index.html").read_text(encoding="utf-8")
    data = (FE / "data.json").read_text(encoding="utf-8")
    # 校验 JSON 合法，并防止 </script> 提前闭合
    json.loads(data)
    safe = data.replace("</", "<\\/")

    inject = f"<script>window.__KB__={safe};</script>\n"
    if "<script>" not in html:
        sys.exit("index.html 中未找到 <script>，无法内联")
    html_out = html.replace("<script>", inject + "<script>", 1)

    dist = FE / "dist"
    dist.mkdir(exist_ok=True)
    out = dist / "index.html"
    out.write_text(html_out, encoding="utf-8")
    kb = json.loads(data)
    print(f"✓ wrote {out.relative_to(ROOT)}  "
          f"(self-contained, {len(html_out)//1024} KB, "
          f"{kb['stats']['documents']} docs inlined)")
    print("  双击打开即可；或部署 dist/ 到任意静态托管。")


if __name__ == "__main__":
    main()
