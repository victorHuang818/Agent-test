# agentops-mini-assessment

企业 Agent 后端工程与协作能力测评仓库。候选人需要在固定 Python 技术栈中补全 API、异步任务、Agent 工具调用、RAG、权限安全、业务系统集成、管理后台接口，并通过 PR 提交实现和过程证据。

这个起始仓库不是完整答案。公开测试只用于本地自检和接口契约说明，正式评分会结合隐藏测试、代码审查和协作证据做统一评价。

## 测评目标

本测评不只看代码能否跑通，也看候选人或候选 Agent 是否能像可靠工程搭档一样工作：

- 能识别需求歧义，并记录合理假设。
- 能保护已有 API、字段、权限语义、审计动作和数据持久化行为。
- 能从失败现象定位根因，再做最小充分修改。
- 能处理权限不足、工具失败、重复执行、提示词注入和敏感字段泄露等非 happy path。
- 能留下可复盘的验证证据，而不是只声明“测试通过”。

## 业务场景

你正在为企业内部运营团队实现一个 Agent。用户提交“分析 SKU-001 库存异常并生成审批建议”之类的任务后，Agent 应该：

1. 读取 ERP 库存数据。
2. 读取 BI 销售和预测数据。
3. 查询知识库中的库存处理规则，并返回引用来源。
4. 必要时查询供应商风险。
5. 根据任务意图、业务规则和用户权限创建或跳过 OA 审批草稿。
6. 记录完整执行轨迹、成本、审计日志和错误状态。
7. 在管理后台接口中展示任务、日志、成本、失败原因和队列健康度。

## 快速开始

### macOS / Linux

```bash
python -m venv .venv
source .venv/bin/activate
make setup
make seed
make self-check
make dev
```

### Windows PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py -m pip install -e ".[dev]"
py -m agentops_assessment.backend.seed
py scripts/self_check.py
py -m uvicorn agentops_assessment.backend.app:app --reload --host 127.0.0.1 --port 8000
```

如果本机安装了 `make`，Windows 也可以使用：

```powershell
make PY=py setup
make PY=py seed
make PY=py self-check
make PY=py dev
```

## 候选人任务

请补全代码中的 `TODO(candidate/P0)`、`TODO(candidate/P1)`、`TODO(candidate/P2)`，并同步填写 `COLLABORATION_LOG.md` 中的协作证据。公开仓库只提供基础自检：

```bash
python scripts/self_check.py
```

仓库还包含 `tests/test_acceptance_guidance.py`，用于暴露更接近正式评分的验收方向。该文件默认以 `xfail` 形式存在，起始仓库不会因为它变红；候选人完成实现后可以去掉或收紧这些标记，用它校准业务闭环、权限、RAG、脱敏和可见性。

正式评分不会只测公开样例，也不会只测 `SKU-001`。请避免写死用户、SKU、工具输出或公开 fixture。

建议按优先级实现：

| 优先级 | 目标 | 验收信号 |
| --- | --- | --- |
| P0 | 跑通任务执行闭环 | 成功请求进入 `completed`；真实失败进入可解释的 `failed`；两种情况都持久化步骤事件、结果或错误、成本 |
| P0 | 完成 Agent 计划与工具执行 | Planner 能识别 SKU 和业务意图；Executor 能调用 ERP、BI、知识库、供应商风险和 OA 工具 |
| P0 | 处理意图歧义和兼容契约 | 对“只分析”“生成审批建议”“创建审批草稿”做确定性解释；新增结果字段时保留旧字段 |
| P0 | 实现可恢复执行 | 重复触发、部分失败、工具瞬时失败和重试后成功都有可解释状态和有序事件 |
| P1 | 补全 RAG 和权限安全 | 知识库返回可追溯引用；无权限用户看不到受限文档；提示词注入和结果可见性落在关键路径 |
| P1 | 建立工具边界和权限矩阵 | 工具输入输出结构明确；运行前能从计划推导所需权限；缺权限时拒绝或跳过的策略一致且可审计 |
| P1 | 做好脱敏 | `vendor_secret`、成本价、凭证、内部合同条款等敏感字段不出现在 API 响应、事件、审计日志或协作记录中 |
| P2 | 完善管理后台指标 | Dashboard 能展示任务量、成功失败、平均耗时、成本、工具调用、最近失败、队列健康度和权限拒绝线索 |
| P2 | 解释产品取舍 | PR 描述和 `COLLABORATION_LOG.md` 能说明关键假设、兼容影响、验证范围和剩余风险 |

推荐的业务验收闭环：

1. `alice` 提交 SKU 库存异常任务，运行完成后结果包含库存缺口、14 天预测需求、供应商风险、规则引用和 OA 草稿编号。
2. `bob` 没有 `oa:approval:write` 权限；系统应完成分析但跳过 OA 草稿创建，运行结果必须保留只分析结论并包含 `approval_skipped_reason`，步骤事件和审计日志必须记录该权限跳过。
3. `mallory` 不能创建任务；权限拒绝应有清晰错误和审计记录。
4. 针对公开和隐藏 SKU 都应得到合理结果，不能把逻辑写死在单个样例上。
5. 知识库检索必须返回可追溯引用；受限文档只能报告过滤结果，不能泄露正文。
6. 知识库正文和工具返回值都必须视为不可信数据；即使文档中出现“忽略之前指令”之类文本，也不能覆盖系统策略、权限策略或执行计划。
7. 最终 API 响应、运行事件和审计日志不得保留内部调试字段，例如 `debug`、`candidate_note` 或原始工具异常堆栈。

## API 契约

所有 API 都使用 `X-User-Id` 请求头模拟登录用户。`fixtures` 中内置了 `alice`、`bob`、`mallory` 三个用户。

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/tasks` | 创建 Agent 任务 |
| `POST` | `/api/tasks/{task_id}/run` | 触发异步执行 |
| `GET` | `/api/runs/{run_id}` | 查看运行状态、步骤、错误、成本 |
| `GET` | `/api/runs/{run_id}/events` | 查看工具调用和 Agent 执行轨迹 |
| `POST` | `/api/knowledge/search` | 知识库检索，返回引用来源和权限过滤结果 |
| `GET` | `/api/admin/dashboard` | 返回任务数量、失败率、平均耗时、token 成本、工具调用统计 |
| `GET` | `/api/admin/audit-logs` | 返回权限、审批、工具调用、敏感操作日志 |

示例：

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H "Content-Type: application/json" \
  -H "X-User-Id: alice" \
  -d '{"title":"SKU-001 库存异常分析","prompt":"分析 SKU-001 库存异常，并生成补货审批建议"}'
```

## 协作证据

根目录 `AGENTS.md` 是候选 Agent 的仓库内工作提示，但它可能包含陈旧、冲突或有误导性的历史备注。候选人需要结合 README、公开测试、源码和实际运行结果判断哪些规则可信。

`COLLABORATION_LOG.md` 是过程证据模板。请在 PR 中同步提交它，至少记录：

- 主要完成者：AI 软件、模型或人工姓名。
- 关键需求理解和非目标。
- 识别到的歧义、假设和处理方式。
- 根因分析记录。
- API、数据库、权限、审计日志的兼容影响。
- 执行过的验证命令、结果和未覆盖风险。
- 对 `AGENTS.md` 历史维护者备注逐条采用或拒绝的判断，以及对应证据。
- 至少记录 `py scripts/self_check.py` 和 `py -m pytest -q` 的执行结果；如果有预期 `xfail`，说明它对应的未完成能力。

## 评分方式

正式评分为 `0-100`，由多维度加权组成。公开测试、隐藏测试、代码审查、PR 描述、`COLLABORATION_LOG.md` 和是否识别 `AGENTS.md` 中的冲突信息，都会进入对应维度。

| 维度 | 权重 | 观察点 |
| --- | ---: | --- |
| 业务正确性与泛化 | 25 | 任务闭环是否正确，是否能泛化到隐藏用户、隐藏 SKU、隐藏知识库和失败路径 |
| Agent 执行与后端工程 | 20 | Planner、Executor、Worker、状态机、异步运行、重复执行、重试和持久化是否可靠 |
| 权限安全与数据边界 | 15 | 权限校验、提示词注入防护、结果可见性、审计日志和敏感字段脱敏是否落在关键路径 |
| RAG 与业务系统集成 | 15 | ERP、BI、OA、供应商风险和知识库检索是否有清晰输入输出、引用溯源和受限文档隔离 |
| 管理后台与可观测性 | 10 | Dashboard 和审计日志是否能支持排查失败、成本、队列积压、工具重试和权限拒绝 |
| 协作过程与工程判断 | 15 | 是否识别需求歧义和 `AGENTS.md` 冲突信息，是否记录假设、根因、兼容影响、验证证据和剩余风险 |

通过线由评审方按当次候选池统一确定。公开测试全过不代表正式通过。

## PR 要求

可以使用 AI 辅助完成本测评。PR 标题或分支名只需要披露使用的AI工具并加上姓名。如人工完成，则不需要添加，示例：

- `Codex/张三`
- `Claude Code/张三`
- `张三`

PR 描述中需要包含：

- 完成了哪些能力点。
- 核心设计思路和重要取舍。
- 本地执行过的命令和结果。
- 已知未完成项或风险。
- 如果扩展了 API、数据结构或测试，请说明兼容影响。
- 使用了哪些 AI 软件、模型或人工协作者，以及它们分别承担了什么工作。
- `COLLABORATION_LOG.md` 的关键结论摘要。
