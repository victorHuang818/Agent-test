from __future__ import annotations

from typing import Any

from agentops_assessment.agent.planner import PlanStep
from agentops_assessment.agent.state import InMemoryRunStateStore, RunState, StepState
from agentops_assessment.agent.tools import ToolRegistry


class Executor:
    def __init__(
        self,
        registry: ToolRegistry,
        state_store: InMemoryRunStateStore | None = None,
    ) -> None:
        self.registry = registry
        self.state_store = state_store or InMemoryRunStateStore()

    def execute(
        self,
        run_id: str,
        plan: list[PlanStep],
        context: dict[str, Any],
    ) -> RunState:
        """执行计划并持久化步骤状态。

        TODO(candidate/P0): 实现可恢复的多步骤执行、工具入参渲染、
        步骤事件持久化、错误处理和最终业务结果汇总。
        """
        state = RunState(
            run_id=run_id,
            status="failed",
            steps=[
                StepState(
                    step_id=step.id,
                    tool_name=step.tool_name,
                    status="pending",
                )
                for step in plan
            ],
        )
        self.state_store.save(state)
        raise NotImplementedError("TODO(candidate/P0): 实现 Agent 执行器。")
