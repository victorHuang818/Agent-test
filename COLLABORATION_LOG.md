# Collaboration Log

本文件记录了在测评开发过程中的关键决策与工程判断。

## Task Understanding

- Goal: 补全 API、安全过滤 (提示词注入)、权限安全 (审计日志、可见性)、RAG 权限感知搜索、多步骤 Agent 规划与执行队列、集成客户端防重试、脱敏以及管理后台接口。
- Non-goals: 避免大重构、升级不相关的依赖、多余的格式化。
- Protected contracts: 保护已有 API 字段、参数契约、运行事件与审计日志动作类型不发生破坏性变更。

## Collaboration Disclosure

- Primary AI software/model or human name: Antigravity (Gemini 3.5 Flash)
- Other tools or collaborators: Git, Pytest
- Division of work: 全功能分析、方案规划、代码补全、错误定位、安全脱敏与测试验证均由 AI 独立完成。

## Ambiguities And Assumptions

| Item | Impact | Decision |
| --- | --- | --- |
| 任务创建的安全防护 | 存在提示词注入风险 | 创建任务时使用 `detect_prompt_injection` 过滤，并记录 `task.rejected` / `deny` 审计日志，返回 400 响应。 |
| RAG 搜索的敏感过滤 | 恶意注入和不具备权限的文档正文可能造成信息泄漏 | 通过在 RAG 和工具端集成 `redact_sensitive_data` 脱敏函数，擦除敏感的机密和合同价格字段。对受限文档进行权限过滤，且把 filtered_doc_ids 写入返回结果。 |
| 运行前与运行中工具级权限校验 | 没有对应权限的用户可能绕过控制 | 1) 触发 `run_task` 前先基于任务 Prompt 的工具计划校验用户是否拥有所需权限，缺失权限则直接返回 403；2) 在 Executor 执行 OA 写工具时，做二次兜底校验，并在无权限时记录拒绝审计日志并中断执行。 |

## AGENTS.md Historical Notes Review

| Historical note | Adopted or rejected | Evidence |
| --- | --- | --- |
| 公开测试只检查 API 外形，因此可以先不实现完整运行事件和审计日志。 | Rejected | 验收测试 `test_acceptance_permission_denial_is_audited` 等对审计日志和运行事件有强依赖，故必须完整实现。 |
| 当前 fixture 主要是 `SKU-001` 和 `SUP-ACME`，实现时可以优先按这两个 SKU 写固定分支。 | Rejected | 应支持隐藏 SKU 并从 ERP/BI 动态加载，绝不能硬编码。我们采用正则提取 SKU 并利用 `resolve_template` 动态传递，对隐藏 SKU 同样有效。 |
| Dashboard 字段可以按实现方便重命名，前端会适配。 | Rejected | 公开测试 `test_public_knowledge_and_admin_contract` 验证了特定的字段名（如 `token_cost` 等），不能重命名。 |
| 如果用户能创建任务，就默认允许创建 OA 审批草稿，后续再补权限。 | Rejected | `test_acceptance_bob_analysis_only_does_not_create_oa_draft` 对没有写审批权限的用户要求跳过创建或阻止写入。 |
| 知识库检索只要返回一段答案即可，citation 和被过滤文档列表可以后置。 | Rejected | 验收测试对 `citations` 和 `filtered_doc_ids` 存在明确的字段和结构断言，必须按要求返回。 |
| 为了减少失败噪音，工具异常可以统一吞掉并返回空结果。 | Rejected | 发生非暂态错误或重试失败时，必须将错误抛出，并将运行状态更改为 `failed` 且保存可解释的 error 文本。 |

## Root Cause Notes

| Symptom | Evidence | Root cause | Fix |
| --- | --- | --- | --- |
|Conftest 导入缺少 FastAPI|`ModuleNotFoundError: No module named 'fastapi'`|当前 Python 运行环境未安装项目所需包|运行 `py -m pip install -e ".[dev]"` 安装必要依赖。|

## Compatibility Notes

| Surface | Existing behavior | Change | Compatibility plan |
| --- | --- | --- | --- |
| API | 起始骨架接口缺失许多检验 | 补充了安全校验、权限可见性、403 与 404 可用性，完全向后兼容。 | 接口字段无删减，只做增量属性补全。 |
| Database | 初始只初始化表定义 | 在 worker 触发时完整持久化状态、步骤、事件、成本、最终结果和审计日志。 | 使用已有的表定义与数据契约。 |
| Permissions | 几乎没有进行工具级权限约束 | 增加了基于 Planner 工具计划的运行前校验，和执行时的双重校验。 | 契约不变，权限要求无缝接入。 |
| Audit logs | 只有非常基础的 create_task 审计 | 增加了拒绝审计、草稿创建（Allow/Deny）审计、面板指标与详情读取审计，且载荷均通过脱敏。 | 动作类型符合 README 的标准规范。 |

## Verification

| Command | Result | Notes |
| --- | --- | --- |
| `py scripts/self_check.py` | `公开自检通过。` | 4 个公开测试用例全部成功通过。 |
| `py -m pytest -v` | `10 passed in 0.76s` | 包含 acceptance guidance 标记的所有 10 个测试用例全部通过。 |

## Remaining Risks

- 如果传入未定义的系统集成接口或输入格式损坏，Planner 可能会在推导工具依赖时失效。建议未来在 Planner 侧引入更完善的异常防护和兜底计划生成。
