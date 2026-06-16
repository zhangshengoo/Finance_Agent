# TradingAgents-CN 引擎运行 · Bugfix / 踩坑记录

> 本文档汇总在本项目（Finance_Agent）驱动 TradingAgents-CN 多智能体引擎做 A 股个股 / 行业分析时，遇到的非显然 bug、根因与修复。涵盖引擎代码层（数据 provider、分析师、记忆）与运行环境层（claude-max-proxy、v2rayN 路由）。新 bug 修复后请按同格式追加。
>
> 约定：代码改动多在子模块 `TradingAgents-CN/`（独立 git），环境/运维改动在项目根或本机。每条标注**状态**（✅已修 / ⚠️需用户操作 / 🔁绕过）与日期。

## 速览表

| # | Bug | 层 | 症状 | 根因一句话 | 状态 | 日期 |
|---|---|---|---|---|---|---|
| 1 | 基本面 PE/PB/总市值 失真 | 引擎·数据 | PE 6.8x / PB 0.56x「破净极度低估」(真值 68.7x/9.01x) | 无头跑估值/价格双锁 MongoDB → 落占位价 10.0 现算 | ✅ | 2026-06-14 |
| 2 | 嵌入超长文本零向量 | 引擎·记忆 | 长文本嵌入返回零向量，记忆静默写废、永召不回 | 超长文本超嵌入模型上限 → 截断/失败成零向量 | ✅ | 2026-06-12 |
| 3 | eastmoney push2 取数失败 | 环境·路由 | akshare 走 push2 报 RemoteDisconnected/502 | 本机 v2rayN 把国内域名错误代理到死节点 | 🔁/⚠️ | 2026-06-12 |
| 4 | news 分析师对 Anthropic 不取数 | 引擎·分析师 | 新闻报告仅 2 字符空白 | 预处理强制取新闻只对 DashScope 等触发，Anthropic 漏 | ✅ | 2026-06-09 |
| 5 | 风险辩论质疑数据是「未来/虚构」 | 引擎·分析师 | 三方拒绝分析，风险经理防御性给「持有」 | 数据日期晚于模型知识截止 → 判为钓鱼拒答 | ✅ | 2026-06-09 |
| 6 | claude-max-proxy token 过期 | 环境·网关 | 引擎首个 LLM 调用即 401 AuthenticationError | proxy 读文件 token，`claude` 刷的是 Keychain，两边对不上 | ⚠️ | 2026-06-09 |
| 7 | 风险辩论三方「破角色」 | 引擎·分析师 | risky/safe/neutral 拒绝扮演指定对抗立场，对抗辩论结构坍塌 | 数据一边倒看空时，照角色论证买入/折中违反模型诚实→破角色（#5 衍生新模式，非"数据是未来"） | 🔁 | 2026-06-15 |
| 8 | 决策原子 JSONDecodeError 兜底 | 引擎·决策 | confidence/risk_score/reasoning/target_price 全兜底（仅 action 真），target_price 误取止损位 | `signal_processing.py` `json.loads` 抛 `JSONDecodeError` → 整段回退 `_extract_simple_decision`（硬编码默认 + 正则取首个价） | ✅ | 2026-06-15 |

---

## 1. 基本面 PE/PB/总市值 失真（占位价 10.0）

- **症状**：A 股个股基本面报告把估值算成离谱低值，例如 300476 胜宏科技报 `PE 6.8x / PB 0.56x`、判「破净 / 极度低估 / 买入」，真值为 `PE 74.6x / PE_TTM 68.7x / PB 9.01x / 总市值 3216亿`。确定性复现（多次跑结果一致），与网络路由无关。利润指标（毛利率/净利率/ROE）反而正确。
- **根因**：`TradingAgents-CN/tradingagents/dataflows/optimized_china_data.py` 的 A 股基本面路径中：
  - 权威 PE/PB/总市值（第1层 `realtime_metrics.get_pe_pb_with_fallback`）读的是 **MongoDB 集合**（`market_quotes`/`stock_basic_info`），被 `if db_manager.is_mongodb_available()` 闸门包裹；
  - 实时价格兜底（`_get_real_financial_metrics` 内）同样依赖 MongoDB；
  - 本项目**无头跑 MongoDB 永远关** → 上述两层全部跳过 → 落到第2层用 `_estimate_financial_metrics` 里解析失败的静默默认 **`price_value = 10.0`**，现算 `PE=价/EPS`、`PB=价/BPS`。日志铁证：`PE(单期): 股价10.0 / EPS1.4800 = 6.8倍`。
- **修复**（`optimized_china_data.py`，3 处内聚改动，已端到端验证）：
  1. 新增 `OptimizedChinaDataProvider._get_tushare_valuation(symbol)`：直连 Tushare `daily_basic` 取 `pe/pe_ttm/pb/total_mv/close`，**不依赖 MongoDB**。
  2. 在第1层(Mongo) 与第2层(假价) 之间插「**第1.5层**」：`pe_value/pb_value` 为空时用上面 Tushare 权威值填充；现有 `if ... is None` 守卫随即自动跳过脆弱的「股价/EPS」现算。
  3. 价格兜底不再静默用 10.0：先取 Tushare 真实 `close`，全失败才占位并打 `ERROR` 告警（守「绝不杜撰财务数据」红线）。
- **验证**：`_generate_fundamentals_report("300476")` 输出 `总市值 3215.77亿 / PE 74.6 / PE_TTM 68.7 / PB 9.01`，精确命中 Tushare 真值；日志确认第1.5层触发、第2层现算被跳过。
- **遗留（未改）**：`providers/china/fundamentals_snapshot.py:26` import 路径错（`.providers.china.tushare` 应为 `.tushare`）→ `get_cn_fund_snapshot` 一直返回 `{}`；Tushare **DB token 失效**（"您的token不对"），靠 `.env` token 降级才连上；akshare 股票列表/总市值仍 `Excel file format` 失败（已被第1.5层覆盖，不影响估值）。
- **关联**：记忆 `project_tradingagents_cn_fundamentals_pe_pb_bug`。

## 2. 嵌入超长文本零向量

- **症状**：把超长文本送 DashScope `text-embedding-v4` 嵌入时，超过模型 token 上限 → 返回 1024 维**零向量**；`add_situations` 仍「成功」，但该条记忆永远召不回 —— 静默拖垮记忆功能 A（写）/ B（读召回）。
- **根因**：嵌入入口未对超长文本分段，直接整段送模型 → 截断/失败退化为零向量。
- **修复**：`TradingAgents-CN/tradingagents/agents/utils/memory.py` 改为**分段归一化均值池化**：按段落贪心打包成 `≤ EMBEDDING_SAFE_CHARS`（默认 7500）的若干块（`_chunk_text`），各块嵌入后 L2 归一化等权累加再归一化（`_embed_long_text`），不丢信息、不出零向量。见回测功能设计文档 §11。
- **另注（运维侧零向量）**：DashScope 欠费/缺 key 时 `get_embedding` 也会回零向量。功能 A/回测跑前必须**探活 DashScope**。DashScope 仅做嵌入，对话调用走 anthropic:5678。
- **关联**：`docs/backtest-feature-design.md` §11、记忆 `project_stock_memory_loop_B`。

## 3. eastmoney push2 取数失败（v2rayN 错误代理）

- **症状**：行业/个股采集时 akshare 走 `push2.eastmoney.com` 的接口（行业 K 线、成份股、资金流、`stock_zh_a_spot_em`、个股 `stock_individual_info_em` 等）报 `RemoteDisconnected` / `502 Bad Gateway` / 空响应。
- **根因**：**本机 v2rayN 代理（xray + sing-box，多 utun 做规则路由 + TUN 模式）把国内域名错误代理到死节点**（如 `47.112.165.11` 阿里云 nginx 502）。`dig` 出真实 IP 但 curl 实际连到死节点 → 流量在网络层被改道。**不是 claude-max-proxy，不是 /etc/hosts，不是反爬。**
- **关键鉴别**：`curl -sS -o /dev/null -w '%{remote_ip} %{http_code}\n' https://push2.eastmoney.com/api/qt/stock/get?secid=0.300750` —— remote_ip 不是 `101.226.x` 或 http_code=502 即被错误代理。注意 **TUN 模式下应用层 `proxies=` / `NO_PROXY` / `--resolve` 都绕不过**（网络层拦截）。
- **绕过 / 根治**：
  - 根治：v2rayN 路由切「**V3-绕过大陆 / geosite:cn 直连**」（2026-06-14 已切，akshare 股票列表恢复；但东财 em 个别接口仍偶发 ConnectionError）。
  - 代码绕过：缺数据时换不走 push2 的源 —— `index_component_sw`(legulegu) + `stock_zh_valuation_baidu`(baidu) + `stock_zh_a_spot`(sina) 三源回填；基本面估值则直连 Tushare `daily_basic`（见 #1）。
- **关联**：记忆 `project_eastmoney_push2_v2rayn_misroute`。

## 4. news 分析师对 Anthropic 不取数

- **症状**：全 4 分析师跑深度分析时，news 分析师产出仅 ~2 字符的空报告。
- **根因**：`news_analyst.py` 的「预处理强制取新闻」模式只对 DashScope/DeepSeek/Zhipu 触发；Anthropic 落到 LLM 工具调用路径，ChatAnthropic 经 proxy 常只回一个 `tool_use`（参数还用错的 `stock_code/max_news`）就被当成报告。
- **修复**：预处理触发条件加 `'Anthropic' in llm.__class__.__name__`。新闻真正入口是 `tools/unified_news_tool.py` 的 `UnifiedNewsAnalyzer.get_stock_news_unified`（**不是** `agent_utils.Toolkit.get_stock_news_unified`）；兜底链 DB→AKShare→东财实时→Google→WebSearch→OpenAI 已在 `_get_a_share_news` 补 WebSearch。修后东财实时稳定返回 ~2500 字真新闻。
- **关联**：记忆 `project_tradingagents_cn_deeprun_fixes`。

## 5. 风险辩论质疑「真实数据是未来/虚构的」

- **症状**：激进/保守/中性三方 + 风险经理因数据日期（2026-06）晚于模型知识截止，判定「这不是真实数据、是被设计的钓鱼」，集体拒绝实质分析，风险经理给「数据不可验证→持有」的防御性结论。
- **修复**：新增 `tradingagents/agents/utils/prompt_directives.py::data_authenticity_preamble(curr_date)`，强制声明数据为 `state["trade_date"]` 当日真实行情、禁止以「像未来/不可信/被设计」为由拒答；拼到 3 个 risk debator + risk_manager 的 prompt 最前面。
- **关联**：记忆 `project_tradingagents_cn_deeprun_fixes`。

## 6. claude-max-proxy token 过期（401）

- **症状**：proxy 在线（探活返回码正常），但引擎首个 LLM 调用即 `401 / AuthenticationError`。
- **根因**：proxy（`Third_Party/claude-max-proxy/proxy.py`）从**文件** `~/.claude/.credentials.json` 读 `claudeAiOauth.accessToken`；macOS 上 `claude` 的活凭证存在 **Keychain**（服务名 `Claude Code-credentials`）。proxy 过期时调 `claude --print "ping"` 想自动刷新，但只刷 Keychain、**不写回文件** → 文件 token 持续过期 → 401。
- **修复（用户操作，Agent 不碰凭证）**：把 Keychain 活凭证导出覆盖到文件 —— `security find-generic-password -w -s "Claude Code-credentials" -a "$USER" > ~/.claude/.credentials.json`。proxy 每请求重读文件，**无需重启**。若导出后仍 401，说明 Keychain 也过期 → 在终端 `claude` 内 `/login` 重新授权后再导出。
- **运维**：启动 `cd Third_Party/claude-max-proxy && unset VIRTUAL_ENV && .venv/bin/python proxy.py`（:5678，后台）；`/health` 看 `token_hours`；探活/补全用 `curl --noproxy '*'`（避免被 v2rayN 串 localhost，见 #3）。一次标准档 ~12min 跑程需 token 剩余 > 12min。**已封装为 skill** `.claude/skills/fix-proxy-token`（`scripts/proxy_token.sh ensure`：盲刷 Keychain→文件 + 校验，write-only 不读凭证）。
- **关联**：记忆 `project_claude_max_proxy_ops`、`stock-analysis/references/proxy-ops.md`、skill `fix-proxy-token`。

## 7. 风险辩论三方「破角色」（对抗角色拒演）

- **症状**：风险辩论中 risky（激进）/safe（保守）/neutral（中立）三位分析师**显式拒绝扮演被指派的对抗立场**（如激进方拒绝"论证高风险高回报最优"、中立方拒绝"在两极间取折中"），改为各自基于数据直接给观点。对抗式辩论结构（互相攻击、各执一端）实际未发生。标准档3（risk 2轮）与深度档5（risk 3轮）均稳定复现（300476，2026-06-15 **三跑**：含 #8 修复后整链重跑仍复现）。
- **更新（2026-06-15 修复后重跑）**：破角色范围**不止风险辩论**——**交易员节点（trader_investment_plan，§6）同样破角色**：拒绝出具交易方案，称上游四份报告"凭空编造"而拒给目标价。故 honesty-override 是 trader+risk 两处 LLM 节点的共性（数据一边倒时），非风险辩论独有。但**投研多空辩论（§5）正常进行**（bull/bear 各 13k 字实质交锋）、两位裁决官（投研经理 §5 judge、风控主席 §8）照常产出清晰卖出裁决，决策原子经 #8 的 Layer0 解析为 `genuine_structured`。stock-analysis 报告据此把 §6/§7 标 `degraded`、§8 标 `ok`。
- **根因**：当个股数据**一边倒看空**（如 300476：PE 74.6× 配 ROE 7.6% 近数学矛盾 + 全空头技术面 + 治理负面），prompt 强制的角色立场（激进=必须看多、中立=必须折中）与诚实分析冲突 → 模型的诚实/无害训练压过角色扮演，宁可破角色也不编造站不住的多头/折中理由（原话如"照角色论证买入是说服甚至误导，不是分析"）。
- **与 #5 的区别（这是新模式）**：#5 是三方以"数据是未来/虚构"为由**拒绝分析**、风控防御性给"持有"；本模式中 ① bugfix #5 的 `data_authenticity_preamble` **已生效**（激进方明确说"数据晚于知识截止不是我拒绝的借口"仍继续分析），② 三方**照常给出高质量实质看空分析**，只是拒绝对抗**角色**，③ 风控裁决拿到**真实决断**（卖出，非兜底持有）。即 **role-break-but-converged**：辩论结构坍塌但结论有效。
- **影响 / 处理**：决策可用（三方独立诚实分析收敛同一结论，可信度反而高），但**多空对抗的增量价值丢失**（深度档5 多花~3min 跑 3 轮风险辩论，产出与标准档3 同质）。stock-analysis 报告据此把 §7 风险辩论模块标 `degraded`（如实反映结构未按设计运行），正文附注 `role-break-but-converged`；§8 最终裁决若决断真实则标 `ok`/或因 #8 的兜底标 `degraded`。
- **可选根治方向（未做）**：风险辩论 prompt 改为"基于数据给出激进/保守/中立**视角**下的风险评估"而非"扮演必须对立的角色"，把对抗性从"立场强制"改为"维度分工"，可在数据中性时保留辩论张力、数据一边倒时不逼模型造假。
- **关联**：#5、记忆 `project_tradingagents_cn_deeprun_fixes`。

## 8. 决策原子 JSONDecodeError → parse_fallback（target_price 误取止损位）

- **症状**：深度档5 跑 300476（2026-06-15）时，引擎 `decision` 块整段命中兜底——`confidence=0.7`、`risk_score=0.5`、`reasoning="基于综合分析的投资建议"` **三者全是 `_extract_simple_decision` 的硬编码默认值（非真实）**；`target_price=355`（**高于现价 327 却判"卖出"，自相矛盾**）为正则误抓的**止损位**（真值 6 月核心目标 **265**）。**仅 `action=卖出` 为正则真实提取**——因 regex 在全文命中"卖出"，故表面没退成"持有/0.5/0.5"全兜底，极具迷惑性（confidence 0.7 看着像真值，其实是默认）。标准档3 同票同日跑则 JSON 解析成功、干净（target 250 / conf 0.85 / risk 0.75 / reasoning 完整）——**深度档反而更脏**。
- **根因**：`graph/signal_processing.py::process_signal` 用 quick LLM 把裁决全文转结构化 JSON，再 `re.search(r'\{.*\}', resp, DOTALL)` 贪婪截取 + `json.loads`；裁决文本长/含表格/多组价格时 `json.loads` 抛 `JSONDecodeError` → except 整段回退 `_extract_simple_decision`：action 走 regex（真）、target_price 走 `price_patterns` 取**首个**命中数字（误抓止损 355）、confidence/risk_score/reasoning 直接返回**硬编码 0.7/0.5/默认串**。深度档5 裁决更长/含多组价格（1月315/3月290/6月265 + 止损355 + 清仓300），更易触发。
- **处理（本次）**：报告 frontmatter `ta_target_price` 取裁决全文真值 **265**、`ta_risk_score: null`（标 parse_fallback）；§8 模块标 `degraded` 并在正文显式提示"355 实为止损、risk_score/reasoning 为兜底、以全文 265 为准"。**真实理由永远以 `reports.final_trade_decision` 全文为准，勿信 `decision.reasoning` 兜底串。**
- **修复（已实现 + 测试通过，2026-06-15）**：抽出纯函数模块 `tradingagents/graph/decision_parser.py`（不调 LLM、可离线测），`signal_processing.py::process_signal` 改为调用它替代旧的『贪婪正则 + 静默兜底』。三件事：① **稳健 JSON 抽取**（去 ```fence```、trailing-comma 修复、非贪婪+贪婪多策略）；② **标签感知取目标价**——只认 `核心目标价/目标价/N个月` 语境、**排除 `止损/清仓/跌破/现价`** 语境、多 horizon 取 6 个月 canonical，叠加 **方向-价格一致性**（卖出却 target>现价 → 判止损误取并改取文本）；③ **provenance 逐字段标记** `genuine_json|text|rejected_json_then_text|fallback|null`，缺真值的 confidence/risk_score/reasoning 返回 **None（不再静默假填 0.7/0.5）**。
- **Layer 0（治本 · 已实现 + 真实验证，2026-06-15）**：`process_signal` 改为**优先 LLM 原生结构化输出** `self.quick_thinking_llm.with_structured_output(TradingDecisionSchema, include_raw=True)`——schema 强制 JSON 形状，从源头消灭 `JSONDecodeError`/贪婪正则。schema 字段**可空**（`target_price/confidence/risk_score: Optional`），prompt 同步改成『缺失填 null、禁止编造、目标价≠止损≠现价』，避免为满足 schema 而杜撰（守红线）。结构化失败/不支持时优雅回退上面的 Layer 1 文本解析。`decision_from_structured()` 与 `parse_decision()` 共用 `_finalize()`（同一套一致性校验 + provenance，结构化字段标 `genuine_structured`）。
- **验证**：`tests/test_decision_parser_bugfix8.py` **33/33**（含结构化路径 3 场景）；`process_signal` 接线冒烟 2 例（Layer0 成功 / Layer0 不支持→回退 Layer1）均 PASS；**隔离真实验证**——用真实 Haiku 经 proxy(:5678) 在**当初触发 JSONDecodeError 的 1871 字 depth5 裁决**上跑一次 `process_signal`：`HTTP 200 → ✅结构化解析成功 → action=卖出 / target_price=265.0（非355止损）/ confidence=0.95 / risk_score=0.85 / provenance 全 genuine_structured`，7.68s 一次调用。**proxy 确认支持结构化输出（tool-calling）**。
- **端到端真实验证（修复后整链重跑，2026-06-15，11.83min）**：300476 深度档5 全 4 分析师**整条引擎**重跑，日志 `✅ [SignalProcessor] LLM 原生结构化输出解析成功`，`decision` 块逐字段 `genuine_structured`（**无 `decision.parse_fallback`**）：`action=卖出 / target_price=215.0（6月核心目标，非 330 止损 — 误取问题已消除）/ confidence=0.95 / risk_score=0.85`，`current_price=null`（裁决无可信现价锚点，不假填）。对比修复前同票 degraded 跑（355/0.7/0.5 全兜底），**#8 在真实生产路径上闭环**。顺带 patch runner `_serialize` 把 `provenance/current_price` 落进快照 `decision` 块，审计可查。干净报告已替换归档 `raw/analysis/stocks/300476-2026-06-15.md`（§8 由 degraded→**ok**）。
- **改动文件**：`tradingagents/graph/decision_parser.py`（新增，纯函数 + schema）、`tradingagents/graph/signal_processing.py`（接入 Layer0/Layer1 + prompt 可空化）、`tests/test_decision_parser_bugfix8.py`（新增）。下游 `trading_graph.py:841` 仅加 `model_info` 返回，新增 `_provenance/_current_price` 键不影响序列化。
- **未覆盖（后续可选）**：现价目前从裁决文本提取（取不到时 cp=None，靠标签感知仍正确）——理想是从 `final_state.market_report` 把真实现价 thread 进 `process_signal` 以恒定开启方向-价格一致性校验；以及把『写裁决的 Opus 直接吐结构化原子』（少一道 Haiku 二次抽取）。
- **关联**：stock-analysis skill guardrail #5（parse_fallback 必标低置信）、`references/output-schema.md`、`tradingagents/graph/decision_parser.py`、`tests/test_decision_parser_bugfix8.py`。
