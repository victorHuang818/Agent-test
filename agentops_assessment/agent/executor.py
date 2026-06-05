from __future__ import annotations

from typing import Any

from agentops_assessment.agent.planner import PlanStep
from agentops_assessment.agent.state import InMemoryRunStateStore, RunState, StepState
from agentops_assessment.agent.tools import ToolRegistry


from agentops_assessment.backend import database
from agentops_assessment.agent.tools import redact_sensitive_data

def resolve_template(template: Any, step_outputs: dict[str, Any]) -> Any:
    if isinstance(template, dict):
        return {k: resolve_template(v, step_outputs) for k, v in template.items()}
    elif isinstance(template, list):
        return [resolve_template(item, step_outputs) for item in template]
    elif isinstance(template, str) and template.startswith("$"):
        path = template[1:]
        if "." in path:
            step_id, key = path.split(".", 1)
            step_out = step_outputs.get(step_id)
            if isinstance(step_out, dict):
                return step_out.get(key)
            return None
        else:
            return step_outputs.get(path)
    return template


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
        conn = context.get("conn")
        user_permissions = context.get("user_permissions", [])
        user_id = context.get("user_id", "unknown")

        steps_states = [
            StepState(
                step_id=step.id,
                tool_name=step.tool_name,
                status="pending",
            )
            for step in plan
        ]

        state = RunState(
            run_id=run_id,
            status="running",
            steps=steps_states,
        )
        self.state_store.save(state)

        step_outputs = {}
        for step in plan:
            # Find the corresponding StepState
            step_state = next(s for s in steps_states if s.step_id == step.id)
            step_state.status = "running"
            self.state_store.save(state)

            # Resolve input arguments
            args = resolve_template(step.input_template, step_outputs)
            if step.tool_name == "knowledge.search":
                args["user_permissions"] = user_permissions

            # Check permission for protected write tool
            if step.tool_name == "oa.create_approval_draft":
                if "oa:approval:write" not in user_permissions:
                    if conn:
                        database.insert_audit_log(
                            conn,
                            actor_id=user_id,
                            action="approval.draft.create",
                            resource="approval_draft",
                            decision="deny",
                            payload={"reason": "Permission denied: missing oa:approval:write"},
                        )
                        database.insert_run_event(
                            conn,
                            run_id=run_id,
                            event_type="tool.skipped",
                            tool_name="oa.create_approval_draft",
                            payload={"reason": "Permission denied: missing oa:approval:write"}
                        )
                    step_state.status = "failed"
                    step_state.error = "Permission denied: missing oa:approval:write"
                    state.status = "failed"
                    self.state_store.save(state)
                    raise PermissionError("Permission denied: missing oa:approval:write")

            try:
                result = self.registry.call(step.tool_name, args)

                # Write audit log for draft creation
                if step.tool_name == "oa.create_approval_draft":
                    if conn:
                        database.insert_audit_log(
                            conn,
                            actor_id=user_id,
                            action="approval.draft.create",
                            resource=result.get("approval_draft_id", "unknown"),
                            decision="allow",
                            payload=result,
                        )

                # Record run event
                if conn:
                    database.insert_run_event(
                        conn,
                        run_id=run_id,
                        event_type="tool.call",
                        tool_name=step.tool_name,
                        payload={
                            "args": redact_sensitive_data(args),
                            "result": result,
                            "attempts": self.registry.last_call_attempts.get(step.tool_name, 1),
                        }
                    )

                step_state.status = "completed"
                step_state.output = result
                step_outputs[step.id] = result
                self.state_store.save(state)

            except Exception as exc:
                step_state.status = "failed"
                step_state.error = str(exc)

                if conn:
                    database.insert_run_event(
                        conn,
                        run_id=run_id,
                        event_type="tool.call",
                        tool_name=step.tool_name,
                        payload={
                            "args": redact_sensitive_data(args),
                            "error": str(exc),
                            "attempts": self.registry.last_call_attempts.get(step.tool_name, 1),
                        }
                    )

                state.status = "failed"
                self.state_store.save(state)
                raise exc

        # All steps succeeded, compile final results
        state.status = "completed"

        sku = step_outputs.get("get_inventory", {}).get("sku") or step_outputs.get("get_sales", {}).get("sku") or "UNKNOWN"
        warehouse = step_outputs.get("get_inventory", {}).get("warehouse")
        stock_gap = step_outputs.get("get_inventory", {}).get("stock_gap")
        forecast_units_next_14d = step_outputs.get("get_sales", {}).get("forecast_units_next_14d")

        supplier_id = step_outputs.get("get_inventory", {}).get("supplier_id")
        supplier_risk_raw = step_outputs.get("get_supplier_risk", {})
        supplier_risk = {
            "supplier_id": supplier_id or supplier_risk_raw.get("supplier_id"),
            "risk_level": supplier_risk_raw.get("risk_level", "unknown"),
        }

        citations = step_outputs.get("search_rules", {}).get("citations", [])

        res = {
            "sku": sku,
            "warehouse": warehouse,
            "stock_gap": stock_gap,
            "forecast_units_next_14d": forecast_units_next_14d,
            "supplier_risk": supplier_risk,
            "citations": citations,
        }

        if "create_approval" in step_outputs:
            res["recommended_action"] = "create_replenishment_approval"
            res["approval_draft_id"] = step_outputs["create_approval"].get("approval_draft_id")
        else:
            res["recommended_action"] = "analyze_only"

        state.result = redact_sensitive_data(res)
        self.state_store.save(state)
        return state
