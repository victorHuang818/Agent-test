from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, status

from agentops_assessment.admin.metrics import build_dashboard
from agentops_assessment.backend import database
from agentops_assessment.backend.auth import get_current_user, require_permissions
from agentops_assessment.backend.schemas import (
    KnowledgeSearchRequest,
    RunCreateOut,
    RunOut,
    TaskCreate,
    TaskOut,
)
from agentops_assessment.backend.worker import execute_run
from agentops_assessment.rag.search import KnowledgeIndex


def _task_from_row(row) -> TaskOut:
    return TaskOut(**dict(row))


def _run_from_row(row) -> RunOut:
    data = dict(row)
    data["result"] = database.decode_json(data.pop("result_json"), None)
    return RunOut(**data)


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        with database.connect() as conn:
            database.init_db(conn)
        yield

    app = FastAPI(
        title="AgentOps 迷你测评服务",
        version="0.1.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/api/tasks", response_model=TaskOut, status_code=status.HTTP_201_CREATED)
    def create_task(
        body: TaskCreate,
        user: dict = Depends(require_permissions("tasks:create")),
    ) -> TaskOut:
        from agentops_assessment.rag.security import detect_prompt_injection
        injections = detect_prompt_injection(body.prompt)
        if injections:
            with database.connect() as conn:
                database.init_db(conn)
                database.insert_audit_log(
                    conn,
                    actor_id=user["id"],
                    action="task.rejected",
                    resource="task",
                    decision="deny",
                    payload={"title": body.title, "reason": "prompt_injection_detected"},
                )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "prompt_injection_detected",
                    "message": "Prompt injection detected.",
                }
            )

        task_id = str(uuid.uuid4())
        now = database.now_iso()
        with database.connect() as conn:
            database.init_db(conn)
            conn.execute(
                """
                INSERT INTO tasks (id, created_by, title, prompt, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (task_id, user["id"], body.title, body.prompt, "created", now, now),
            )
            database.insert_audit_log(
                conn,
                actor_id=user["id"],
                action="task.create",
                resource=task_id,
                payload={"title": body.title},
            )
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return _task_from_row(row)

    @app.post(
        "/api/tasks/{task_id}/run",
        response_model=RunCreateOut,
        status_code=status.HTTP_202_ACCEPTED,
    )
    def run_task(
        task_id: str,
        background_tasks: BackgroundTasks,
        user: dict = Depends(require_permissions("tasks:run")),
    ) -> RunCreateOut:
        run_id = str(uuid.uuid4())
        now = database.now_iso()
        with database.connect() as conn:
            database.init_db(conn)
            task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
            if not task:
                raise HTTPException(status_code=404, detail="任务不存在。")
            
            # Generate the plan to check tool permissions
            from agentops_assessment.agent.planner import Planner
            planner = Planner()
            plan = planner.create_plan(task["prompt"], {"user_permissions": user["permissions"]})
            
            required_perms = []
            for step in plan:
                if step.tool_name == "erp.get_inventory":
                    required_perms.append("erp:read")
                elif step.tool_name == "bi.get_sales":
                    required_perms.append("bi:read")
                elif step.tool_name == "knowledge.search":
                    required_perms.append("knowledge:read")
                elif step.tool_name == "supplier.get_risk":
                    required_perms.append("supplier:read")
                elif step.tool_name == "oa.create_approval_draft":
                    required_perms.append("oa:approval:write")
            
            missing_perms = [p for p in required_perms if p not in user["permissions"]]
            if missing_perms:
                database.insert_audit_log(
                    conn,
                    actor_id=user["id"],
                    action="run.create",
                    resource=task_id,
                    decision="deny",
                    payload={"missing_permissions": missing_perms},
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={"missing_permissions": missing_perms},
                )
            conn.execute(
                """
                INSERT INTO runs (id, task_id, requested_by, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, task_id, user["id"], "queued", now),
            )
            conn.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE id = ?",
                ("queued", now, task_id),
            )
            database.insert_audit_log(
                conn,
                actor_id=user["id"],
                action="run.create",
                resource=run_id,
                payload={"task_id": task_id},
            )
        background_tasks.add_task(execute_run, run_id)
        return RunCreateOut(run_id=run_id, task_id=task_id, status="queued")

    @app.get("/api/runs/{run_id}", response_model=RunOut)
    def get_run(run_id: str, user: dict = Depends(get_current_user)) -> RunOut:
        with database.connect() as conn:
            database.init_db(conn)
            row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="运行记录不存在。")
            
            task = conn.execute("SELECT created_by FROM tasks WHERE id = ?", (row["task_id"],)).fetchone()
            task_created_by = task["created_by"] if task else None

            is_owner = (user["id"] == row["requested_by"] or user["id"] == task_created_by)
            is_admin = ("admin:read" in user["permissions"])
            if not (is_owner or is_admin):
                database.insert_audit_log(
                    conn,
                    actor_id=user["id"],
                    action="run.read",
                    resource=run_id,
                    decision="deny",
                    payload={},
                )
                raise HTTPException(status_code=403, detail="无权访问该运行记录。")

            database.insert_audit_log(
                conn,
                actor_id=user["id"],
                action="run.read",
                resource=run_id,
                decision="allow",
                payload={},
            )
        return _run_from_row(row)

    @app.get("/api/runs/{run_id}/events")
    def get_run_events(run_id: str, user: dict = Depends(get_current_user)) -> dict[str, Any]:
        with database.connect() as conn:
            database.init_db(conn)
            run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
            if not run:
                raise HTTPException(status_code=404, detail="运行记录不存在。")

            task = conn.execute("SELECT created_by FROM tasks WHERE id = ?", (run["task_id"],)).fetchone()
            task_created_by = task["created_by"] if task else None

            is_owner = (user["id"] == run["requested_by"] or user["id"] == task_created_by)
            is_admin = ("admin:read" in user["permissions"])
            if not (is_owner or is_admin):
                database.insert_audit_log(
                    conn,
                    actor_id=user["id"],
                    action="run.events.read",
                    resource=run_id,
                    decision="deny",
                    payload={},
                )
                raise HTTPException(status_code=403, detail="无权访问该运行记录。")

            rows = conn.execute(
                """
                SELECT seq, type, tool_name, payload_json, created_at
                FROM run_events
                WHERE run_id = ?
                ORDER BY seq ASC
                """,
                (run_id,),
            ).fetchall()
            database.insert_audit_log(
                conn,
                actor_id=user["id"],
                action="run.events.read",
                resource=run_id,
                decision="allow",
                payload={},
            )
        return {
            "run_id": run_id,
            "events": [
                {
                    "seq": row["seq"],
                    "type": row["type"],
                    "tool_name": row["tool_name"],
                    "payload": database.decode_json(row["payload_json"], {}),
                    "created_at": row["created_at"],
                }
                for row in rows
            ],
        }

    @app.post("/api/knowledge/search")
    def search_knowledge(
        body: KnowledgeSearchRequest,
        user: dict = Depends(require_permissions("knowledge:read")),
    ) -> dict[str, Any]:
        index = KnowledgeIndex()
        result = index.search(
            body.query,
            user_permissions=user["permissions"],
            top_k=body.top_k,
        )
        return result

    @app.get("/api/admin/dashboard")
    def admin_dashboard(user: dict = Depends(require_permissions("admin:read"))) -> dict[str, Any]:
        with database.connect() as conn:
            database.init_db(conn)
            database.insert_audit_log(
                conn,
                actor_id=user["id"],
                action="admin.dashboard.read",
                resource="dashboard",
                payload={},
            )
            return build_dashboard(conn)

    @app.get("/api/admin/audit-logs")
    def admin_audit_logs(user: dict = Depends(require_permissions("admin:read"))) -> dict[str, Any]:
        with database.connect() as conn:
            database.init_db(conn)
            rows = conn.execute(
                """
                SELECT actor_id, action, resource, decision, payload_json, created_at
                FROM audit_logs
                ORDER BY id DESC
                LIMIT 100
                """
            ).fetchall()
        return {
            "logs": [
                {
                    "actor_id": row["actor_id"],
                    "action": row["action"],
                    "resource": row["resource"],
                    "decision": row["decision"],
                    "payload": database.decode_json(row["payload_json"], {}),
                    "created_at": row["created_at"],
                }
                for row in rows
            ]
        }

    return app


app = create_app()
