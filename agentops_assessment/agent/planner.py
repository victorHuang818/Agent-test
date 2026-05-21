from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentops_assessment.agent.fake_llm import FakeLLM


@dataclass(frozen=True)
class PlanStep:
    id: str
    tool_name: str
    description: str
    input_template: dict[str, Any] = field(default_factory=dict)


class Planner:
    def __init__(self, llm: FakeLLM | None = None) -> None:
        self.llm = llm or FakeLLM()

    def create_plan(self, prompt: str, context: dict[str, Any] | None = None) -> list[PlanStep]:
        """为业务请求创建多步骤工具计划。

        TODO(candidate/P0): 推断 SKU 和业务意图，选择必要工具，并返回一个
        确定性的计划。计划应覆盖 ERP、BI、知识库、必要的供应商风险
        和可能的 OA 审批步骤，不能写死单个用户、SKU 或样例 prompt。
        """
        self.llm.complete(prompt)
        return [
            PlanStep(
                id="understand_request",
                tool_name="llm.summarize",
                description="占位步骤。请替换为真实的业务执行计划。",
            )
        ]
