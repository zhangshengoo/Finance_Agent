# Finance Agent · 前端（知识台）

知识库的「编译视图」——纯渲染器，**零内容硬编码**，全部数据来自 Knowledge_Wiki。
**live 模式**：浏览器内用 `kb-parse.js` 直接解析 KB 的 `.md` / `.jsonl`，**不再编译 / 维护 `data.json`**。

## 运行（本地服务，零编译）

```bash
./frontend/serve.sh            # 默认 8000，可传端口： ./frontend/serve.sh 8080
```

`serve.sh` 只做两件事：① 生成源清单 `manifest.json`（一份路径列表）；② 从**项目根**起本地服务并开浏览器（`http://localhost:8000/frontend/`）。

- **改任意 `wiki/raw` 下的 `.md` 内容 → 刷新浏览器即见**（内容 live 解析，无需重建）。
- **新增 / 改名 / 删除文件**后重跑 `serve.sh` 刷新 `manifest.json` 即可。

> 🔒 **仅限本地个人查看。** 这是私人投研知识库，**不要**部署到任何公网托管 / 分享链接。
> `serve.sh` 起的是 localhost 回环服务，外部访问不到。
>
> ⚠️ 浏览器禁止 `file://` 页面 `fetch()` 本地文件，所以**必须走本地服务**，不能直接双击 `index.html`。

## 数据链路

```
wiki/*.md · raw/analysis/stocks/*.md · ontology/graph.jsonl · raw/.../timeline.json
   │   frontmatter = 机器可查字段(YAML) ；正文 = 人读叙述 + 注释栅栏模块
   ▼  serve.sh 生成 manifest.json（源路径清单）
frontend/kb-parse.js   浏览器内 live 解析：frontmatter + 模块栅栏 + 严格模版表格 + 图谱
   ▼  → 等同旧 data.json 的 KB 对象（{stats,sectors,macro,media,companies,graph}）
frontend/index.html    按 type 注册渲染器，纯展示（渲染层与解析层解耦）
```

`kb-parse.js` 是**单一解析真源**（取代旧 `build_frontend_data.py`）。详见模版契约：[../docs/frontend-kb-binding.md](../docs/frontend-kb-binding.md)

## 文件

| 文件 | 角色 |
|---|---|
| `index.html` | 渲染器 + boot（fetch `manifest.json` → fetch 各源 → `kbParse` → 渲染） |
| `kb-parse.js` | **单一解析真源**：把 KB 的 md/jsonl 解析成 KB 对象（node 端 + 浏览器端共用） |
| `manifest.json` | 由 `serve.sh` 生成的源路径清单（生成物，可 git 忽略；**勿手改**） |
| `serve.sh` | 启动器：生成 manifest + 从项目根起服务 + 开浏览器 |
