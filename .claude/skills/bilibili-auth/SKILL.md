---
name: bilibili-auth
description: 通过扫码登录获取并校验 B 站登录态 cookie（SESSDATA），落地本地缓存供 media-archive 抓取使用。任何时候遇到「B 站 SESSDATA 过期 / 刷新 B 站 cookie / 扫码登录 B 站 / 重新登录 bilibili」，或抓取 B 站时报「未登录 / code -101 / 账号未登录」、字幕全部抓空（subtitle_source=none）、动态/视频接口疑似登录态失效——都应主动用本 skill 重新取一份有效 SESSDATA。它是 media-archive 等 B 站采集能力的鉴权前置：登录态一旦失效，字幕和需要登录的接口会静默返回空，本 skill 负责把它修好。
---

# bilibili-auth — 扫码获取 / 刷新 B 站 SESSDATA

## 这个 skill 解决什么

B 站很多接口（**视频 AI 字幕**、部分动态/空间数据）只对**登录请求**返回完整内容。
登录态 `SESSDATA` cookie 大约**月级别过期**。过期后接口仍回 `code:0 OK`，但把数据
**静默吞成空**——表现为「字幕全是 `subtitle_source=none`」「明明有字幕的视频也抓不到」，
极易被误判成「视频没字幕」。本 skill 负责拿到一份**经过校验确实在线**的新 SESSDATA。

判断登录态是否失效的权威信号：`GET /x/web-interface/nav` 返回 `code:-101 账号未登录` /
`data.isLogin == false`。

## 何时触发（主动用，别等用户明说）

- 用户说：「B 站 SESSDATA 过期了」「刷新 / 重新登录 B 站」「扫码登录 bilibili」「B 站 cookie 失效」
- media-archive / 任何 B 站抓取报 **未登录 / `-101` / 账号未登录**
- 抓视频后**字幕整批 `none`**、或某个已知有字幕的视频也抓空 → 先怀疑登录态，跑本 skill 的 `--check`
- 准备做一轮 B 站采集前，想先确认登录态还在线

> 不负责绕过风控 IP 限制（那是 `-352/-412`，属网络出口问题，见 media-archive 红线 7）。
> 本 skill 只管「登录态」这一层。两者是独立问题，别混。

## CRITICAL 红线

1. **凭据只落本地、绝不外传。** SESSDATA 是你账号的登录令牌，等同密码级敏感。脚本只把它写到
   `~/.bilibili_sessdata.json`（`chmod 600`，仅本人可读），**不**打印完整值、**不**发任何外部服务、
   **不**写进仓库 / KB / 日志。报告里只显示 `uname` / `mid` / `sessdata_len` 这类非敏感字段。
2. **只走官方扫码登录。** 不采集密码、不破解验证码、不模拟非官方登录。扫码是 B 站 web 官方流程。
3. **拿到后必须校验再宣布成功。** 必须用新 cookie 打 `nav` 确认 `isLogin==true` 才算成功——
   否则又会重蹈「拿到无效串却以为修好了」的覆辙。脚本已内置这步，别跳过。
4. **手机用 B 站 App 扫，不是微信/支付宝扫一扫。** 扫错 App 不会登录。

## 工作流

### 1) 先自检（可选但推荐）

怀疑登录态时，先花一秒确认到底是不是登录问题：

```bash
uv run .claude/skills/bilibili-auth/scripts/get_sessdata.py --check
```

- `{"ok":true,"uname":"…"}` → 登录态在线，问题不在这儿（去查风控 / 是否真无字幕）
- `{"ok":false,…}` 或退出码非 0 → 登录态失效，进下一步扫码

### 2) 扫码登录取新 SESSDATA

```bash
uv run .claude/skills/bilibili-auth/scripts/get_sessdata.py
```

脚本会：
1. 生成二维码：终端打印 ASCII 码 + 存 PNG 到 `/tmp/bilibili_login_qr.png` 并在 macOS 自动 `open`，同时打印 URL（任选其一扫）
2. 轮询登录状态，实时打印「等待扫码 → 已扫码待确认 → 登录成功」
3. **用新 cookie 打 nav 校验 `isLogin`**
4. 写 `~/.bilibili_sessdata.json`（`chmod 600`）

> **必须前台 / 可交互执行**（要等用户用手机扫码，默认超时 180s）。**不要后台跑**——
> 后台跑用户看不到二维码、也没法在超时内确认。需要更长时间用 `--timeout 240`。

成功输出（最后一行 JSON）：
```json
{"ok": true, "uname": "你的B站昵称", "mid": 12345678, "cache": "~/.bilibili_sessdata.json", "sessdata_len": 222}
```

### 3) 下游自动生效（端到端）

`media-archive` 的 `_bilibili_common.get_sessdata()` 按
**`--sessdata` CLI 参数 > `~/.bilibili_sessdata.json` 缓存 > `BILIBILI_SESSDATA` 环境变量(.env)** 的顺序解析。
所以扫码成功后，**抓取脚本直接就能用上新 cookie，无需手动 `export`、无需改 .env、无需重启会话**。

**为什么缓存压过 env：** env / `.env` 通常在**会话启动时一次性注入**进程环境，之后无法在会话内
热更新——一旦过期就会出现「陈旧 env 盖住刚扫码的新 cache」（踩过的坑）。而缓存由本 skill 每次
扫码登录写入、且写前经 `nav` 校验 `isLogin`，是「当前活的」凭据，故优先级高于 env。
显式 `--sessdata` 仍最高（人工覆盖 / 多账号临时切换）。

> `.env` 里若还留着旧的 `BILIBILI_SESSDATA`，**不影响**（缓存会压过它）；它只在「从没扫过码、
> 缓存缺失」时作兜底。想彻底单一来源也可以把 `.env` 那行删掉，纯靠缓存。

## 与其它 skill 的边界

| 任务 | 用哪个 |
|---|---|
| 取 / 刷新 / 校验 B 站登录态 SESSDATA | **bilibili-auth**（本 skill）|
| 抓 B 站视频/动态/公众号落 raw/ | `media-archive` |
| 抓取报 `-352/-412` 风控（IP 出口问题，非登录）| 调路由 / 等冷却，见 media-archive 红线 7，**不是**本 skill |

## 环境依赖

- `uv`（PEP 723 内联依赖，自动装）：`curl_cffi==0.9.0`、`qrcode==7.4.2`、`pillow`
- 一台能打开 B 站 App 扫码的手机
- 产物：`~/.bilibili_sessdata.json`（含 `sessdata` / `bili_jct` / `dedeuserid` / `uname` / `mid` / `saved_at`，`chmod 600`）

## 错误处理

| 情况 | 行为 |
|---|---|
| 二维码生成失败（`code≠0`）| 报错退出，多半是网络/出口被风控，稍后重试 |
| 二维码失效（poll `86038`）| 报错提示重跑生成新码 |
| 扫码超时 | 到 `--timeout` 退出，提示重跑；可加大超时 |
| 取到 SESSDATA 但 nav `isLogin=false` | 视为失败报错（不写缓存），避免落地无效串 |
| `--check` 时 env/缓存都没有 | 退出码 2 + 提示先扫码 |
