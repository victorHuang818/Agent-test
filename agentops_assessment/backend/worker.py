import os
from agentops_assessment.backend import database
from agentops_assessment.agent.planner import Planner
from agentops_assessment.agent.executor import Executor
from agentops_assessment.agent.tools import ToolRegistry
from agentops_assessment.agent.fake_llm import FakeLLM


def execute_run(run_id: str) -> None:
    """后台执行入口。

    用完整的 Planner -> Executor 流程替换此占位实现。
    """
    # Reset global token tracker
    FakeLLM.reset_tokens()

    with database.connect() as conn:
        database.init_db(conn)
        now = database.now_iso()

        # Update run status to running
        conn.execute(
            "UPDATE runs SET status = ?, started_at = ? WHERE id = ?",
            ("running", now, run_id),
        )
        conn.commit()

        # Fetch run, task and user details
        run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not run:
            return

        task = conn.execute("SELECT * FROM tasks WHERE id = ?", (run["task_id"],)).fetchone()
        if not task:
            return

        user = conn.execute("SELECT * FROM users WHERE id = ?", (run["requested_by"],)).fetchone()
        if not user:
            return

        user_permissions = database.decode_json(user["permissions_json"], [])

        # Record run started event
        database.insert_run_event(
            conn,
            run_id,
            "run.started",
            {"message": "Agent execution loop started."},
        )

        # Build context
        context = {
            "conn": conn,
            "user_id": run["requested_by"],
            "user_permissions": user_permissions,
        }

        # Initialize clients & registry
        fixtures_dir = os.getenv("ASSESSMENT_FIXTURES_DIR", "fixtures")
        # In worker, we set retry_attempts to 3 to retry transient errors
        registry = ToolRegistry.with_default_clients(
            fixtures_dir=fixtures_dir,
            retry_attempts=3,
        )

        try:
            planner = Planner()
            plan = planner.create_plan(task["prompt"], context)

            executor = Executor(registry)
            run_state = executor.execute(run_id, plan, context)

            # Execution succeeded
            status = "completed"
            result_json = database.encode_json(run_state.result)
            error = None

        except Exception as exc:
            # Execution failed
            status = "failed"
            result_json = None
            error = str(exc)

        # Update runs and tasks status
        finished_at = database.now_iso()
        token_cost = FakeLLM.get_global_tokens()

        conn.execute(
            """
            UPDATE runs
            SET status = ?, result_json = ?, error = ?, token_cost = ?, finished_at = ?
            WHERE id = ?
            """,
            (status, result_json, error, token_cost, finished_at, run_id),
        )
        conn.execute(
            "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
            (status, finished_at, run["task_id"]),
        )
        conn.commit()
