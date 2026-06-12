# 资金面分析师（Capital Flow Analyst）设计方案

> **评审状态**：v2（已修订）。本文档由一次多 agent 工作流（6 个代码事实提取 + 4 个维度审计 + 42 条发现逐条独立复核）对照 `TradingAgents-CN` **真实源码**校正。v1 中所有"凭印象"写法（`self.provider`、`asyncio.run`、`operator.add`、`_LAZY_IMPORTS`、`Msg Clear Capital Flow` 空格命名等）均为运行时 bug，已逐一改正，并补全 v1 遗漏的入口层（CLI / web / propagation）接线。
>
> 下方「评审结论」记录了改了什么、为什么改、以及哪些"看似要改其实不用改"的点。

---

## 评审结论（v1 → v2 修正清单）

| # | 严重度 | v1 的错误 | 真实代码 | v2 修正 |
|---|---|---|---|---|
| 1 | 🔴 Blocker | Toolkit 工具写成 `def get_stock_cyq(self, ...)` 调 `self.provider` | `agent_utils.py` 中**每个**工具都是 `@staticmethod` 叠在 `@tool` 上、**无 self**；`Toolkit` 只有类级 `_config`，**没有 `.provider`** | 工具改为 `@staticmethod @tool`，无 self；在函数体内**本地构造** `AKShareProvider()` 调同步方法（与现有 `get_stock_news_em` 工具完全一致的先例） |
| 2 | 🔴 Blocker | 工具体内 `asyncio.run(self.provider.get_*())` | 全文件无 `asyncio`/`async`/`await`；工具全是同步 `def`；且 `asyncio.run` 在 LangGraph 运行中的事件循环里会直接崩 | 改为**同步调用** provider 的 `*_sync` 方法 |
| 3 | 🔴 Blocker | `capital_flow_report: Annotated[str, operator.add]`、计数器同样 `operator.add` | `agent_states.py` 里 `*_report` 全是 `Annotated[str, "描述"]`、计数器是 `Annotated[int, "描述"]`，**无 reducer**；文件**未 import operator**（会 NameError）；`operator.add` 会让字符串累加而非覆盖 | 改为 `Annotated[str, "Report from the Capital Flow Analyst"]` 与 `Annotated[int, "Capital flow analyst tool call counter"]` |
| 4 | 🔴 Blocker | `should_continue` 返回 `"Msg Clear Capital Flow"`（空格） | `setup.py:180` 用 `f"Msg Clear {analyst_type.capitalize()}"`；`"capital_flow".capitalize()` → **`"Capital_flow"`**（下划线、首字母大写） | 返回 `"Msg Clear Capital_flow"` 与 `"tools_capital_flow"`，与图自动生成的节点名严格一致 |
| 5 | 🔴 Blocker | 在 `setup.py` 里加 ToolNode 字典 | ToolNode 字典在 **`trading_graph.py:602 _create_tool_nodes()`**，硬编码 4 个 key；`setup.py:182` 只是 `tool_nodes[t]=self.tool_nodes[t]` 取用，缺 key 会 KeyError | 在 `trading_graph.py _create_tool_nodes()` 内新增 `"capital_flow"` ToolNode key |
| 6 | 🔴 Blocker | 注册到 `_LAZY_IMPORTS` 字典 | `agents/__init__.py:8` 变量名是 **`_EXPORTS`**（`Dict[str, Tuple[str,str]]`），配 `__getattr__` 懒加载 | 改为追加到 `_EXPORTS` 和 `__all__` |
| 7 | 🔴 Blocker | 只改 `setup.py` 默认 `selected_analysts` | `TradingAgentsGraph.__init__`（`trading_graph.py:203`）有**独立**默认值；主入口 `propagate()` 走它 | 同步更新 `trading_graph.py:203` 的默认列表，否则主入口根本不会跑资金面 |
| 8 | 🔴 Blocker | 完全没提 web 层 | `web/utils/analysis_runner.py:811` 有硬编码白名单 `valid_analysts = ['market','social','news','fundamentals']`，`validate_analysis_params` 会拒绝 `'capital_flow'`；报告导出列表（711-714）也漏 `capital_flow_report` | 把 `'capital_flow'` 加进白名单、`'capital_flow_report'` 加进导出列表 |
| 9 | 🟠 Major | 计数器返回常量 `1` | 真实 analyst 是 `state.get("xxx_tool_call_count",0)` 读出后返回 `+1`；覆盖式 reducer 下常量 1 永远停在 1，`>=3` 上限**永不触发** | 读当前值 `+1` 返回 |
| 10 | 🟠 Major | analyst 模板省略 `GoogleToolCallHandler` 分支 | `market_analyst.py:262` 等每个 analyst 都有 `if GoogleToolCallHandler.is_google_model(llm): ... else: ...` 分支（Gemini 工具调用兼容） | 模板补回该分支 |
| 11 | 🟠 Major | 只改 bull/bear researcher | `research_manager.py`、`trader.py`、3 个风险辩论 + `risk_manager` 也读这些 report | 用 grep 找出所有 report 消费者，一并注入（`.get()` 防御式） |
| 12 | 🟠 Major | CLI 未提 | `cli/models.py:10 AnalystType(Enum)` + `cli/utils.py:17 ANALYST_ORDER` 枚举合法分析师 | 各加一项，CLI 才能勾选 |
| 13 | 🟠 Major | `market` 参数写死 `"sh"` | A 股需按代码前缀判 sh/sz/bj | 加 `_infer_market()` 自动推断 |
| 14 | 🟠 Major | provider 直返原始 `df`，绕过 `interface.py`/`DataSourceManager` | 其它 A 股路径都经 manager（MongoDB 缓存优先 + 多源回退） | 采纳"本地 provider + 同步方法"（有 `get_stock_news_em` 先例）；并说明若要缓存/回退可选走 interface 层（见 §3） |
| 15 | 🟡 Minor | 工具直接喂 `df.to_string()` 给 LLM | 浪费 token、无单位语义 | 工具返回**结构化精简摘要**（带单位的 Markdown / 关键派生值） |
| 16 | 🟡 Minor | 未初始化 `capital_flow_report` | `propagation.py:48 create_initial_state` 只 seed 4 个 report | 加 `"capital_flow_report": ""`，防下游 `state[...]` 取键报错 |

**经核查、确认无需改动的点（避免过度工程）**：

- ✅ `chain.invoke(state["messages"])` 传裸列表**没问题**——LangChain 能处理；report 在工具执行后的"无 tool_calls 最终轮"回填，不会空。v1 的 analyst 主体逻辑可保留。
- ✅ `constants/data_sources.py` 注册表**无需改**——筹码/资金流/龙虎榜是"指标接口"，不是新数据源；它们绑定到已注册的 AKShare 源。
- ✅ `ak.stock_lhb_stock_detail_em(symbol, date)` 的签名**无需强加 `flag` 参数**（该说法是某审计 agent 臆造）。但仍建议在实现时对照已安装的 akshare 版本核签名（见 §2 数据源备注）。

---

## 1. 背景与目标

在 TradingAgents-CN 完整个股分析流程中，缺少 A 股特有的资金面维度：

- **筹码分布 / 成本分布**：主力建仓成本区间、套牢盘 / 获利盘比例
- **主力资金净流入**：超大单 / 大单 / 中单 / 小单分类净流入
- **龙虎榜席位**：机构买卖方向与金额

新增「资金面分析师」节点补全该维度，使下游 Bull/Bear Researcher、Research Manager、Trader 在辩论与决策时拥有资金面依据。

---

## 2. 数据源：AKShare（免费，无需 token）

| 数据类型 | AKShare 函数 | 关键字段 | 频率 | 备注 |
|---|---|---|---|---|
| 筹码分布 | `ak.stock_cyq_em(symbol, adjust="")` | 获利比例、平均成本、90%/70% 集中度区间 | 日频（收盘后） | A 股唯一免费筹码接口 |
| 主力资金流 | `ak.stock_individual_fund_flow(stock, market)` | 主力/超大/大/中/小单净流入额、净占比 | 日内延迟 ~15min | `market` 须按代码前缀推断 sh/sz/bj |
| 龙虎榜席位 | `ak.stock_lhb_stock_detail_em(symbol, date)` | 买卖席位、营业部、机构标识、金额 | 日频（T 日收盘后） | 多数日子为空（未上榜）需容错；**实现时核对 akshare 版本签名**，或改用更稳的 `ak.stock_lhb_detail_em(start_date, end_date)` 再按 symbol 过滤 |

**数据时效说明（须在工具输出中如实披露）**：`stock_cyq_em` / `stock_individual_fund_flow` 返回的是**截至最新交易日**的数据，并非"任意历史 as-of 日"的时点快照。若对过去的 `trade_date` 跑回测，这些字段反映的是最新值而非当时值——工具应把实际数据日期一并返回，让 LLM 知情。

---

## 3. 关键设计决策

### 3.1 数据获取路径：本地 provider + 同步方法（采纳，有先例）

真实代码里 Toolkit 工具有两种取数方式：(a) 调模块级 `interface.*` 函数；(b) **在工具体内本地构造 provider 实例并调其同步方法**——例如现有的 `get_stock_news_em` 工具就是 `provider = AKShareProvider(); provider.get_stock_news_sync(...)`。

资金面三类数据是 **AKShare 独有**（Tushare 的 `moneyflow` 需 2000 积分、筹码无；BaoStock 全无），多源回退价值有限，因此**采纳方式 (b)**：在 `AKShareProvider` 加同步方法，工具内本地构造调用。它同步、无事件循环问题、不依赖虚构的 `self.provider`，且与现有 `get_stock_news_em` 完全一致。

> **可选（完全对齐架构）**：若希望获得 MongoDB 缓存优先 + 数据源回退，可改为在 `interface.py` 加 `get_*_unified()` 函数并经 `DataSourceManager` 路由。代价是更多样板代码，收益对 AKShare 独有数据有限——**非必须**。

### 3.2 分析师 key 命名与 capitalize 陷阱（关键）

`setup.py` 用 `f"{analyst_type.capitalize()} Analyst"` 生成节点名。Python 的 `str.capitalize()` 只把首字母大写、**其余转小写且不处理下划线**：

```python
>>> "capital_flow".capitalize()
'Capital_flow'          # 不是 'Capital Flow'，也不是 'Capital_Flow'
```

因此 `analyst_type = "capital_flow"` 生成的节点名是：

| 派生位置 | 值 |
|---|---|
| Analyst 节点 | `Capital_flow Analyst` |
| Msg Clear 节点 | `Msg Clear Capital_flow` |
| Tools 节点 | `tools_capital_flow` |
| 条件方法名 | `should_continue_capital_flow` |

`should_continue_capital_flow` 的返回值**必须严格等于** `"Msg Clear Capital_flow"` 与 `"tools_capital_flow"`，否则 LangGraph 找不到目标节点、编译/路由失败。本文档统一采用 key = `"capital_flow"`（语义清晰、与 `capital_flow_report` 前缀一致），并在 §4 Step 7 给出精确字符串。

---

## 4. 执行链中的位置

资金面分析师插入在分析师序列**第 1 位**（在 Market Analyst 之前）。各 analyst 之间互不读对方 report，顺序不影响分析质量；放第 1 位只是"资金流向先于价格走势"的概念顺序。

> ⚠️ 第 1 位的副作用：`setup.py:197` 用 `selected_analysts[0]` 接 `START` 边，最后一个 analyst 的 Msg Clear 接 `Bull Researcher`。把 capital_flow 放首位是安全的，但**所有入口的默认 `selected_analysts` 列表都要更新**（见 Step 6、Step 8），否则主入口根本不会执行它。

```
START
  ↓
[新] Capital Flow Analyst  → capital_flow_report
  ↓  (Capital_flow Analyst → tools_capital_flow ⇄ → Msg Clear Capital_flow)
Market Analyst             → market_report
  ↓
Social / News / Fundamentals Analyst
  ↓
Bull / Bear Researcher     ← 消费全部 5 个 report
  ↓
Research Manager → Trader → Risk 辩论 → Risk Judge → END
```

---

## 5. 实现步骤

### Step 1 — `AKShareProvider` 新增 3 个同步方法

**文件**：`tradingagents/dataflows/providers/china/akshare.py`（在类内追加，紧邻现有 `get_stock_news_sync`）

```python
@staticmethod
def _infer_market(code: str) -> str:
    """按代码前缀推断交易所，用于 stock_individual_fund_flow 的 market 参数。"""
    code = str(code).zfill(6)
    if code.startswith("6"):                 return "sh"
    if code.startswith(("0", "3")):          return "sz"
    if code.startswith(("4", "8", "9")):     return "bj"
    return "sh"

def get_cyq_sync(self, symbol: str) -> Optional[pd.DataFrame]:
    """筹码分布（成本分布）。返回最近若干日的获利比例/平均成本/集中度区间。"""
    if not self.connected:
        return None
    try:
        return self.ak.stock_cyq_em(symbol=symbol, adjust="")
    except Exception as e:
        logger.error(f"get_cyq_sync failed for {symbol}: {e}")
        return None

def get_fund_flow_sync(self, symbol: str, market: str = None) -> Optional[pd.DataFrame]:
    """主力资金净流入（超大/大/中/小单）。market 缺省时按 symbol 自动推断。"""
    if not self.connected:
        return None
    market = market or self._infer_market(symbol)
    try:
        return self.ak.stock_individual_fund_flow(stock=symbol, market=market)
    except Exception as e:
        logger.error(f"get_fund_flow_sync failed for {symbol}/{market}: {e}")
        return None

def get_lhb_sync(self, symbol: str, date: str) -> Optional[pd.DataFrame]:
    """龙虎榜席位明细。date 为 YYYYMMDD；未上榜返回空，不抛错。"""
    if not self.connected:
        return None
    try:
        # 注意：实现时核对已安装 akshare 的签名；必要时改用
        # self.ak.stock_lhb_detail_em(start_date=date, end_date=date) 再按 symbol 过滤
        return self.ak.stock_lhb_stock_detail_em(symbol=symbol, date=date)
    except Exception as e:
        logger.error(f"get_lhb_sync failed for {symbol}@{date}: {e}")
        return None
```

> `logger`、`pd`、`Optional` 沿用该文件已有的导入与日志器；同步方法签名与现有 `get_stock_list_sync`/`get_stock_news_sync` 一致。可选：返回前做列名归一化为标准 dict（与其它 provider 方法对齐），但摘要化在 Step 2 工具里做也可。

### Step 2 — Toolkit 新增 3 个工具（`@staticmethod` + `@tool`，无 self）

**文件**：`tradingagents/agents/utils/agent_utils.py`（在 `Toolkit` 类内追加，模仿现有 `get_stock_news_em`）

```python
@staticmethod
@tool
def get_stock_cyq(
    ticker: Annotated[str, "A股股票代码，如 000001 / 600519"],
    curr_date: Annotated[str, "分析日期 yyyy-mm-dd"],
) -> str:
    """获取 A 股个股筹码分布（成本分布）：获利比例、平均成本、90%/70% 筹码集中区间。"""
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider
    provider = AKShareProvider()
    df = provider.get_cyq_sync(ticker)
    if df is None or len(df) == 0:
        return f"⚠️ 无法获取 {ticker} 的筹码分布数据"
    latest = df.iloc[-1]
    asof = latest.get("日期", "未知")
    # 返回结构化精简摘要而非 df.to_string，附数据日期与单位
    return (
        f"【{ticker} 筹码分布】数据截至 {asof}\n"
        f"- 获利比例: {latest.get('获利比例')}\n"
        f"- 平均成本: {latest.get('平均成本')} 元\n"
        f"- 90% 集中区间: {latest.get('90%成本-低')} ~ {latest.get('90%成本-高')} 元\n"
        f"- 70% 集中区间: {latest.get('70%成本-低')} ~ {latest.get('70%成本-高')} 元\n"
        f"（近 {min(len(df),10)} 日趋势）\n{df.tail(10).to_string(index=False)}"
    )

@staticmethod
@tool
def get_fund_flow(
    ticker: Annotated[str, "A股股票代码"],
    curr_date: Annotated[str, "分析日期 yyyy-mm-dd"],
) -> str:
    """获取 A 股个股主力资金净流入：主力/超大单/大单/中单/小单净额与净占比（近 5 日）。"""
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider
    provider = AKShareProvider()
    df = provider.get_fund_flow_sync(ticker)   # market 自动推断
    if df is None or len(df) == 0:
        return f"⚠️ 无法获取 {ticker} 的资金流数据"
    return (
        f"【{ticker} 主力资金流】近 5 日（金额单位见原列名，多为元/万元）\n"
        f"{df.tail(5).to_string(index=False)}"
    )

@staticmethod
@tool
def get_dragon_tiger(
    ticker: Annotated[str, "A股股票代码"],
    curr_date: Annotated[str, "分析日期 yyyy-mm-dd"],
) -> str:
    """获取 A 股个股龙虎榜席位明细（买卖营业部、金额、机构标识）。未上榜则说明。"""
    from tradingagents.dataflows.providers.china.akshare import AKShareProvider
    provider = AKShareProvider()
    date = curr_date.replace("-", "")
    df = provider.get_lhb_sync(ticker, date)
    if df is None or len(df) == 0:
        return f"{ticker} 在 {curr_date} 未登上龙虎榜（或数据暂无）。"
    return f"【{ticker} 龙虎榜 {curr_date}】\n{df.to_string(index=False)}"
```

> 关键点：`@staticmethod` 在 `@tool` **之上**、首参是工具输入（非 self）、同步、本地构造 provider——这套写法与 `agent_utils.py` 现有工具逐字一致。列名（如 `90%成本-低`）请在实现时按 akshare 实际返回校正。

### Step 3 — `AgentState` 新增字段（无 reducer）

**文件**：`tradingagents/agents/utils/agent_states.py`（与现有 `*_report` / `*_tool_call_count` 并列）

```python
capital_flow_report: Annotated[str, "Report from the Capital Flow Analyst"]
...
capital_flow_tool_call_count: Annotated[int, "Capital flow analyst tool call counter"]
```

> ❌ 不要用 `Annotated[str, operator.add]`：现有字段全是 `Annotated[T, "描述"]`，无 reducer（默认覆盖式 last-value-wins）；该文件也未 import operator。

### Step 4 — 新建资金面分析师（模仿 `market_analyst.py`，含 Google 分支与计数器）

**文件**：`tradingagents/agents/analysts/capital_flow_analyst.py`（新建）

```python
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from tradingagents.agents.utils.google_tool_handler import GoogleToolCallHandler

SYSTEM_PROMPT = """你是 A 股资金面分析师。基于以下三类数据分析个股资金结构与主力动向：
1. 筹码分布：主力成本区间、套牢/获利盘、压力位与支撑位
2. 主力资金净流入：区分超大单（机构/游资）与大单，判断主力进出方向
3. 龙虎榜：是否有机构席位、买卖方向
输出：资金面综合评价（偏多/中性/偏空）、主力成本区间、近 5 日主力净流入趋势、龙虎榜要点、一句话风险提示。
务必标注数据实际日期；缺数据时如实说明，不得编造。"""


def create_capital_flow_analyst(llm, toolkit):
    def capital_flow_analyst_node(state):
        ticker = state["company_of_interest"]
        trade_date = state["trade_date"]
        tool_call_count = state.get("capital_flow_tool_call_count", 0)
        max_tool_calls = 3

        tools = [toolkit.get_stock_cyq, toolkit.get_fund_flow, toolkit.get_dragon_tiger]

        human = (f"分析股票 {ticker}（{trade_date}）的资金面：先取筹码分布，再取主力资金流，"
                 f"再查龙虎榜，综合输出资金面报告。")

        # Google/Gemini 走专用工具调用处理（与其它 analyst 一致）
        if GoogleToolCallHandler.is_google_model(llm):
            prompt = GoogleToolCallHandler.create_analysis_prompt(SYSTEM_PROMPT, human, tools)
            report, messages = GoogleToolCallHandler.handle_google_tool_calls(
                llm, prompt, tools, state)
            return {
                "messages": messages,
                "capital_flow_report": report,
                "capital_flow_tool_call_count": tool_call_count + 1,
            }

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="messages"),
            ("human", human),
        ])
        chain = prompt | llm.bind_tools(tools)
        result = chain.invoke(state["messages"])
        report = result.content if not result.tool_calls else ""
        return {
            "messages": [result],
            "capital_flow_report": report,
            "capital_flow_tool_call_count": tool_call_count + 1,
        }

    return capital_flow_analyst_node
```

> 计数器读 `state.get(..., 0)` 后 `+1` 返回（覆盖式 reducer 下才能真正递增、让 `>=3` 上限生效）。`GoogleToolCallHandler` 的具体函数名以 `market_analyst.py` 实际调用为准。report 在"工具执行后无 tool_calls 的最终轮"回填，传裸 `state["messages"]` 列表无碍（已核实）。

### Step 5 — 注册到 `_EXPORTS`

**文件**：`tradingagents/agents/__init__.py`

`_EXPORTS` 字典中追加（值为 `(模块路径, 属性名)` 元组）：

```python
"create_capital_flow_analyst": (
    "tradingagents.agents.analysts.capital_flow_analyst", "create_capital_flow_analyst"),
```

`__all__` 列表中追加 `"create_capital_flow_analyst"`。

### Step 6 — `setup.py` 接线

**文件**：`tradingagents/graph/setup.py`

- **导入**：`from tradingagents.agents import (..., create_capital_flow_analyst)`
- **条件注册块**（在 "market" 块之前，使其成为首个分析师）：

```python
if "capital_flow" in selected_analysts:
    analyst_nodes["capital_flow"] = create_capital_flow_analyst(
        self.quick_thinking_llm, self.toolkit)
    delete_nodes["capital_flow"] = create_msg_delete()
    tool_nodes["capital_flow"] = self.tool_nodes["capital_flow"]   # 依赖 Step 7a
```

- **默认值**：`def setup_graph(self, selected_analysts=["capital_flow", "market", "social", "news", "fundamentals"])`

### Step 7 — `trading_graph.py`（两处）

**文件**：`tradingagents/graph/trading_graph.py`

**7a. `_create_tool_nodes()`（约 602 行）** 新增 key —— 这是 v1 漏掉、会 KeyError 的关键点：

```python
"capital_flow": ToolNode([
    self.toolkit.get_stock_cyq,
    self.toolkit.get_fund_flow,
    self.toolkit.get_dragon_tiger,
]),
```

**7b. `TradingAgentsGraph.__init__`（约 203 行）默认值** 同步更新（主入口走这里）：

```python
selected_analysts=["capital_flow", "market", "social", "news", "fundamentals"],
```

### Step 8 — `conditional_logic.py` 条件函数（精确节点名）

**文件**：`tradingagents/graph/conditional_logic.py`

```python
def should_continue_capital_flow(self, state):
    messages = state["messages"]
    last_message = messages[-1]
    if state.get("capital_flow_tool_call_count", 0) >= 3:
        return "Msg Clear Capital_flow"          # 注意：Capital_flow（capitalize 产物）
    if last_message.tool_calls:
        return "tools_capital_flow"
    return "Msg Clear Capital_flow"
```

> 返回串必须严格等于 `setup.py` 由 `.capitalize()` 生成的节点名（见 §3.2）。

### Step 9 — `propagation.py` 初始化字段

**文件**：`tradingagents/graph/propagation.py`（`create_initial_state` 约 48 行，与 4 个现有 report 并列）

```python
"capital_flow_report": "",
```

### Step 10 — 下游消费者注入 `capital_flow_report`

用 grep 找出所有读 report 的节点，逐一加入（**用 `.get()` 防御**，避免未选 capital_flow 时 KeyError）：

```bash
grep -rn 'state\["market_report"\]\|state\.get("market_report"' tradingagents/agents/
```

至少覆盖：`researchers/bull_researcher.py`、`researchers/bear_researcher.py`、`managers/research_manager.py`、`trader/trader.py`（风险辩论 `risk_debators/*` 与 `managers/risk_manager.py` 视需要）。每处两步：

```python
capital_flow_report = state.get("capital_flow_report", "")
# 并入拼接给 LLM 的情境串（放最前面）
curr_situation = (f"{capital_flow_report}\n\n{market_research_report}\n\n"
                  f"{sentiment_report}\n\n{news_report}\n\n{fundamentals_report}")
```

> ⚠️ Bull/Bear 等若在 prompt 模板里**逐条列出各 report**，除了 `curr_situation` 外还要在模板里补 capital_flow 一项，否则 LLM 看不到。

### Step 11 — 入口层放开 `capital_flow`

- **CLI**：`cli/models.py:10 AnalystType` 加 `CAPITAL_FLOW = "capital_flow"`；`cli/utils.py:17 ANALYST_ORDER` 加一项（显示名 + value），否则交互式 CLI 无法勾选。
- **Web**：`web/utils/analysis_runner.py:811 valid_analysts` 加 `'capital_flow'`；报告导出列表（711-714 附近）加 `'capital_flow_report'`，否则 web 端校验拒绝且报告不落盘/不展示。

---

## 6. 完整改动文件清单

| # | 文件 | 改动 |
|---|------|------|
| 1 | `dataflows/providers/china/akshare.py` | +`_infer_market` +`get_cyq_sync`/`get_fund_flow_sync`/`get_lhb_sync`（同步） |
| 2 | `agents/utils/agent_utils.py` | +3 个 `@staticmethod @tool`（本地构造 AKShareProvider，返回结构化摘要） |
| 3 | `agents/utils/agent_states.py` | +`capital_flow_report` / `capital_flow_tool_call_count`（`Annotated[T,"描述"]`，无 reducer） |
| 4 | `agents/analysts/capital_flow_analyst.py` | **新建**（含 Google 分支 + 计数器 +1） |
| 5 | `agents/__init__.py` | `_EXPORTS` + `__all__` 各 +1 |
| 6 | `graph/setup.py` | import + 条件块 + 默认列表 |
| 7 | `graph/trading_graph.py` | `_create_tool_nodes` +key（关键）+ `__init__` 默认列表 |
| 8 | `graph/conditional_logic.py` | +`should_continue_capital_flow`（精确节点名） |
| 9 | `graph/propagation.py` | `create_initial_state` +`capital_flow_report:""` |
| 10 | `agents/researchers/bull_researcher.py`、`bear_researcher.py`、`managers/research_manager.py`、`trader/trader.py`（+风险节点可选） | 读取并注入 `capital_flow_report` |
| 11 | `cli/models.py`、`cli/utils.py` | AnalystType 枚举 + ANALYST_ORDER |
| 12 | `web/utils/analysis_runner.py` | `valid_analysts` 白名单 + report 导出列表 |

> 最小可运行集（先打通单分析师）：1 + 2 + 3 + 4 + 5 + 6 + 7 + 8 + 9。入口层（11、12）与下游注入（10）让它在 CLI/web/辩论中真正生效。

---

## 7. 验证方式

```bash
cd TradingAgents-CN

# A. 单独跑资金面分析师（先验证取数 + 节点接线）
python -c "
from tradingagents.graph.trading_graph import TradingAgentsGraph
ta = TradingAgentsGraph(selected_analysts=['capital_flow'], debug=True)
state, decision = ta.propagate('000001', '2026-06-08')
print(state.get('capital_flow_report'))
"

# B. 完整流程（默认已含 capital_flow）
python analyze_stock.py 000001 2026-06-08
```

**预期**：`capital_flow_report` 含筹码区间 + 近 5 日主力净流入趋势 + 龙虎榜情况（或"未上榜"），并标注数据实际日期。检查图能正常 compile（无节点名 KeyError），且 Bull/Bear 辩论中引用了资金面结论。

---

## 8. 后续扩展

- 接 `ak.stock_individual_fund_flow_rank(indicator="今日")` 做全市场资金排行对比
- 接 `ak.stock_margin_sh()` / `ak.stock_margin_sz()` 补融资融券
- 若确需缓存/多源回退，再把三类数据下沉到 `interface.py` + `DataSourceManager`（见 §3.1 可选项）
- Level2 逐笔需 mootdx + 券商授权（有成本），暂不纳入
