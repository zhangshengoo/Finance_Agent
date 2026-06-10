# Finance Agent · 前端（知识台）

知识库的「编译视图」——纯渲染器，**零内容硬编码**，全部数据来自 Knowledge_Wiki。

## 运行

**开发模式（一条命令：编译 + 起服务 + 开浏览器）**
```bash
./frontend/serve.sh            # 默认 8000，可传端口： ./frontend/serve.sh 8080
```
读取 `data.json`（live）。知识库改动后重跑即可刷新。

**自包含构建（可双击，仍是本地文件）**
```bash
python3 frontend/build_dist.py   # 编译 KB 并把数据内联进 frontend/dist/index.html
open frontend/dist/index.html    # 单文件，无需服务、无需 fetch
```
`dist/index.html` 把 `data.json` 内联，双击即看。

> 🔒 **仅限本地个人查看。** 这是私人投研知识库，**不要**部署到任何公网托管 / 分享链接。
> `serve.sh` 起的是 localhost 回环服务，外部访问不到；dist 是本机文件。两者都不外发数据。

**手动两步（等价于 serve.sh）**
```bash
python3 Knowledge_Wiki/scripts/build_frontend_data.py
cd frontend && python3 -m http.server 8000   # → http://localhost:8000
```

## 数据链路

```
wiki/*.md (人 + Agent 共读的单一事实源)
   │   frontmatter = 机器可查字段(YAML properties) ；正文 = 人读叙述/表格
   ▼
scripts/build_frontend_data.py   只读解析：frontmatter + 严格模版正文表格 + ontology/graph.jsonl
   ▼
frontend/data.json               编译产物（等同 index.md 之于目录）
   ▼
frontend/index.html              按 type 注册渲染器，纯展示
```

详见模版契约：[../docs/frontend-kb-binding.md](../docs/frontend-kb-binding.md)

## 文件

| 文件 | 角色 |
|---|---|
| `index.html` | 渲染器（有内联 `window.__KB__` 用之，否则 fetch `data.json`） |
| `data.json` | 由 build 脚本生成，**勿手改**（git 可忽略） |
| `serve.sh` | 开发启动器：编译 + 起服务 + 开浏览器 |
| `build_dist.py` | 产出自包含 `dist/index.html`（数据内联） |
| `dist/` | 部署产物（生成物，可 git 忽略） |
