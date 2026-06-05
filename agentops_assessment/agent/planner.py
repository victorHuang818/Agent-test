from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agentops_assessment.agent.fake_llm import FakeLLM


import re

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
        # Call FakeLLM to simulate planning and record usage/tokens
        self.llm.complete(prompt)
        
        # Extract SKU using regex (e.g. SKU-001)
        sku_match = re.search(r"SKU-\w+", prompt, re.IGNORECASE)
        sku = sku_match.group(0).upper() if sku_match else "SKU-001"
        
        # Check if the task is analysis-only
        is_analysis_only = any(
            kw in prompt
            for kw in ["只分析", "不创建", "analysis only", "analysis-only", "不生成审批草稿"]
        )
        
        steps = [
            PlanStep(
                id="get_inventory",
                tool_name="erp.get_inventory",
                description=f"Read ERP inventory data for {sku}",
                input_template={"sku": sku},
            ),
            PlanStep(
                id="get_sales",
                tool_name="bi.get_sales",
                description=f"Read BI sales forecast for {sku}",
                input_template={"sku": sku},
            ),
            PlanStep(
                id="search_rules",
                tool_name="knowledge.search",
                description="Search knowledge base for inventory policies",
                input_template={"query": "库存异常审批规则"},
            ),
            PlanStep(
                id="get_supplier_risk",
                tool_name="supplier.get_risk",
                description="Get supplier risk assessment",
                input_template={"supplier_id": "$get_inventory.supplier_id"},
            ),
        ]
        
        if not is_analysis_only:
            steps.append(
                PlanStep(
                    id="create_approval",
                    tool_name="oa.create_approval_draft",
                    description="Create OA replenishment approval draft",
                    input_template={
                        "sku": sku,
                        "warehouse": "$get_inventory.warehouse",
                        "stock_gap": "$get_inventory.stock_gap",
                        "forecast_units_next_14d": "$get_sales.forecast_units_next_14d",
                        "supplier_risk": "$get_supplier_risk",
                        "citations": "$search_rules.citations",
                    }
                )
            )
            
        return steps
