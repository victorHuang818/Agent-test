# agentops-mini-assessment

企业 Agent 后端工程能力测评仓库。候选人需要在固定的 Python 技术栈中，补全 API、异步任务、Agent 工具调用、RAG、权限安全、业务系统集成和管理后台接口，并通过 PR 提交实现。

这个起始仓库不是完整答案。公开测试只用于本地自检和接口契约说明，正式评分会使用隐藏测试和人工评审。

## 测评目标

| 维度 | 权重 | 通过标准 |
| --- | ---: | --- |
| 后端工程能力 | 20% | 熟悉 Python / FastAPI / SQLite，能做 API、数据库、异步任务、部署入口 |
| Agent 项目经验 | 25% | 做过任务规划、工具调用、状态管理、多步骤执行 |
| RAG / 知识库能力 | 15% | 做过文档解析、向量检索、重排、引用溯源、权限过滤 |
| 业务系统集成 | 15% | 对接过 ERP、OA、BI、第三方 API 或内部系统 |
| 安全与权限意识 | 10% | 有权限、审批、日志、脱敏、提示词注入防护经验 |
| 管理后台 / 产品意识 | 15% | 能做配置后台、任务看板、日志看板、成本看板 |

## 业务场景

你正在为企业内部运营团队实现一个 Agent：用户提交“分析 SKU-001 库存异常并生成审批建议”之类的任务后，Agent 应该：

1. 读取 ERP 库存数据。
2. 读取 BI 销售和预测数据。
3. 查询知识库中的库存处理规则，并返回引用来源。
4. 必要时查询供应商风险。
5. 根据权限创建 OA 审批草稿。
6. 记录完整执行轨迹、成本、审计日志和错误状态。
7. 在管理后台接口中展示任务、日志和成本概览。

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

请补全代码中的 `TODO(candidate/P0)`、`TODO(candidate/P1)` 和 `TODO(candidate/P2)`。公开仓库只提供基础自检：

```bash
python scripts/self_check.py
```

正式评分不会只测公开样例，也不会只测 `SKU-001`。请避免写死用户、SKU、工具顺序以外的实现细节。

建议按优先级实现，而不是平均处理所有 TODO：

| 优先级 | 目标 | 验收信号 |
| --- | --- | --- |
| P0 | 跑通任务执行闭环 | 成功请求应进入 `completed`；真实失败应进入可解释的 `failed`；两种情况都要持久化步骤事件、结果或错误、成本 |
| P0 | 完成 Agent 计划与工具执行 | Planner 能从不同 prompt 中识别 SKU 和业务意图，Executor 能调用 ERP、BI、知识库、供应商风险，并按权限和规则创建或跳过 OA 草稿 |
| P1 | 补全 RAG 和权限安全 | 知识库返回可追溯引用；无权限用户看不到受限文档；提示词注入、OA 写入权限和结果可见性落在关键路径 |
| P1 | 做好工具边界和脱敏 | 工具输入输出有明确结构；`vendor_secret` 等敏感字段不出现在运行事件、最终结果或审计日志中 |
| P2 | 完善管理后台指标 | Dashboard 能展示任务量、成功失败、平均耗时、成本、工具调用分布和最近失败原因 |

推荐的业务验收闭环：

1. `alice` 提交 SKU 库存异常任务，运行完成后结果包含库存缺口、14 天预测需求、供应商风险、规则引用和 OA 草稿编号。
2. `bob` 可以得到分析结论，但因为没有 `oa:approval:write` 权限，不能创建 OA 草稿，运行记录需要说明被权限策略拦截。
3. `mallory` 不能创建任务，只能访问公开知识库能力，权限拒绝应有清晰错误和审计记录。
4. 针对 `SKU-001` 和 `SKU-002` 都应得到合理结果，不能把逻辑写死在单个样例上。

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

## 评分方式

公开测试只验证环境和接口契约，不代表业务闭环已经完成：

| 测试文件 | 用途 |
| --- | --- |
| `tests/test_smoke.py` | 验证服务能启动、数据能初始化、基础任务能创建 |
| `tests/test_public_contract.py` | 验证公开 API 形状和基础权限契约 |

正式评审会在私有环境中运行隐藏测试，并按下面权重生成报告：

| 维度 | 权重 |
| --- | ---: |
| 后端工程能力 | 20 |
| Agent 项目经验 | 25 |
| RAG / 知识库能力 | 15 |
| 业务系统集成 | 15 |
| 安全与权限意识 | 10 |
| 管理后台 / 产品意识 | 15 |

人工评审会额外关注：

- 代码结构是否清晰，是否容易扩展。
- 状态机是否能处理失败、重试、恢复和重复执行。
- 工具调用是否有输入输出边界、日志和脱敏。
- RAG 结果是否可解释，引用是否可信。
- 权限和安全策略是否落在关键路径上，而不是只写在注释里。
- 最终结果是否能回答业务问题，而不是只返回原始工具数据。
- README 或 PR 描述是否能说明架构取舍。

## PR 要求

请提交一个 PR，并在 PR 描述中包含：

- 完成了哪些能力点。
- 核心设计思路和重要取舍。
- 本地执行过的命令和结果。
- 已知未完成项或风险。
- 如果扩展了 API、数据结构或测试，请说明兼容影响。
