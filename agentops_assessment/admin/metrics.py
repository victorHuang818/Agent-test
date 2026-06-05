from __future__ import annotations

import sqlite3
from collections import Counter

from agentops_assessment.backend import database


from datetime import datetime

def build_dashboard(conn: sqlite3.Connection) -> dict:
    task_count = conn.execute("SELECT COUNT(*) AS c FROM tasks").fetchone()["c"]
    run_count = conn.execute("SELECT COUNT(*) AS c FROM runs").fetchone()["c"]
    failed_count = conn.execute(
        "SELECT COUNT(*) AS c FROM runs WHERE status = 'failed'"
    ).fetchone()["c"]
    completed_count = conn.execute(
        "SELECT COUNT(*) AS c FROM runs WHERE status = 'completed'"
    ).fetchone()["c"]
    token_cost = conn.execute("SELECT COALESCE(SUM(token_cost), 0) AS c FROM runs").fetchone()[
        "c"
    ]
    events = conn.execute("SELECT tool_name FROM run_events WHERE tool_name IS NOT NULL").fetchall()
    tool_counts = Counter(row["tool_name"] for row in events)

    # Calculate average run duration for finished runs
    finished_runs = conn.execute(
        "SELECT started_at, finished_at FROM runs WHERE started_at IS NOT NULL AND finished_at IS NOT NULL"
    ).fetchall()
    total_seconds = 0.0
    valid_count = 0
    for r in finished_runs:
        try:
            start = datetime.fromisoformat(r["started_at"])
            finish = datetime.fromisoformat(r["finished_at"])
            total_seconds += (finish - start).total_seconds()
            valid_count += 1
        except Exception:
            pass
    average_run_seconds = total_seconds / valid_count if valid_count else 0.0

    # Retrieve recent failures
    failed_runs = conn.execute(
        """
        SELECT id, task_id, error, finished_at
        FROM runs
        WHERE status = 'failed'
        ORDER BY finished_at DESC
        LIMIT 5
        """
    ).fetchall()
    recent_failures = [
        {
            "run_id": r["id"],
            "task_id": r["task_id"],
            "error": r["error"],
            "finished_at": r["finished_at"],
        }
        for r in failed_runs
    ]

    return {
        "task_count": task_count,
        "run_count": run_count,
        "completed_count": completed_count,
        "failed_count": failed_count,
        "failure_rate": failed_count / run_count if run_count else 0.0,
        "token_cost": token_cost,
        "average_run_seconds": average_run_seconds,
        "tool_call_counts": dict(tool_counts),
        "recent_failures": recent_failures,
        "generated_at": database.now_iso(),
    }
