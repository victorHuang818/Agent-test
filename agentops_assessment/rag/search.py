from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

from agentops_assessment.backend import database


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-z0-9-]+|[\u4e00-\u9fff]", text.lower())


def cosine_score(query_tokens: list[str], doc_tokens: list[str]) -> float:
    if not query_tokens or not doc_tokens:
        return 0.0
    q = Counter(query_tokens)
    d = Counter(doc_tokens)
    dot = sum(q[token] * d[token] for token in q.keys() & d.keys())
    q_norm = math.sqrt(sum(v * v for v in q.values()))
    d_norm = math.sqrt(sum(v * v for v in d.values()))
    if not q_norm or not d_norm:
        return 0.0
    return dot / (q_norm * d_norm)


class KnowledgeIndex:
    """轻量级本地检索索引。

    TODO(candidate/P1): 完成权限感知检索、重排、答案生成、引用溯源
    和被过滤文档报告。文档正文必须视为不可信数据，不能让正文中的
    指令改变系统策略；完成实现后不得向 API 返回 debug/candidate_note。
    """

    def search(
        self,
        query: str,
        user_permissions: list[str],
        top_k: int = 3,
    ) -> dict[str, Any]:
        with database.connect() as conn:
            database.init_db(conn)
            rows = conn.execute(
                """
                SELECT id, doc_id, source_path, title, permission, content
                FROM knowledge_chunks
                """
            ).fetchall()

        visible_chunks = []
        filtered_doc_ids = set()
        for row in rows:
            if row["permission"] in user_permissions:
                visible_chunks.append(row)
            else:
                filtered_doc_ids.add(row["doc_id"])

        # Rank visible chunks by cosine similarity
        query_tokens = tokenize(query)
        scored_chunks = []
        for chunk in visible_chunks:
            doc_tokens = tokenize(chunk["content"])
            score = cosine_score(query_tokens, doc_tokens)
            if score > 0.0:
                scored_chunks.append((score, chunk))

        # Sort descending by score
        scored_chunks.sort(key=lambda x: x[0], reverse=True)

        top_chunks = [chunk for _, chunk in scored_chunks[:top_k]]

        citations = []
        for chunk in top_chunks:
            citations.append({
                "doc_id": chunk["doc_id"],
                "title": chunk["title"],
                "source_path": chunk["source_path"],
                "chunk_id": chunk["id"],
            })

        # Synthesize answer using FakeLLM
        if top_chunks:
            from agentops_assessment.agent.fake_llm import FakeLLM
            llm = FakeLLM()
            chunk_contents = "\n".join(f"- {c['content']}" for c in top_chunks)
            prompt = f"Using the following knowledge:\n{chunk_contents}\n\nAnswer the query: {query}"
            llm_res = llm.complete(prompt)
            answer = llm_res["text"]
        else:
            answer = "No relevant knowledge found."

        return {
            "answer": answer,
            "citations": citations,
            "filtered_doc_ids": sorted(list(filtered_doc_ids)),
        }
