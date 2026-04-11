# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Paul Chen / axoviq.com
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch


def test_health(tmp_wiki):
    from synthadoc.integration.http_server import create_app
    with TestClient(create_app(wiki_root=tmp_wiki)) as client:
        assert client.get("/health").json()["status"] == "ok"


def test_status_returns_page_count(tmp_wiki):
    from synthadoc.integration.http_server import create_app
    with TestClient(create_app(wiki_root=tmp_wiki)) as client:
        data = client.get("/status").json()
    assert "pages" in data


def test_query_endpoint(tmp_wiki):
    from synthadoc.integration.http_server import create_app
    from synthadoc.agents.query_agent import QueryResult
    app = create_app(wiki_root=tmp_wiki)
    mock = QueryResult(question="q", answer="answer", citations=["p1"])
    with patch("synthadoc.core.orchestrator.Orchestrator.query",
               new=AsyncMock(return_value=mock)):
        with TestClient(app) as client:
            resp = client.post("/query", json={"question": "What is AI?"})
    assert resp.json()["answer"] == "answer"


def test_ingest_endpoint_returns_job_id(tmp_wiki):
    """POST /jobs/ingest enqueues a job and returns its ID."""
    from synthadoc.integration.http_server import create_app
    app = create_app(wiki_root=tmp_wiki)
    # The endpoint calls queue.enqueue(), not orch.ingest() directly
    with patch("synthadoc.core.queue.JobQueue.enqueue",
               new=AsyncMock(return_value="job-abc")):
        with TestClient(app) as client:
            resp = client.post("/jobs/ingest", json={"source": "paper.pdf"})
    assert resp.status_code == 200
    assert resp.json()["job_id"] == "job-abc"


def test_lint_report_shows_contradictions_and_orphans(tmp_wiki):
    """GET /lint/report reads wiki files and returns contradicted pages and orphans."""
    wiki_dir = tmp_wiki / "wiki"
    # A page marked contradicted in its frontmatter
    (wiki_dir / "conflicted-page.md").write_text(
        "---\nstatus: contradicted\n---\n# Conflicted Page\n",
        encoding="utf-8",
    )
    # An orphan page — no other page links to it
    (wiki_dir / "orphan-page.md").write_text(
        "---\nstatus: active\ntags: [test]\n---\n# Orphan Page\n",
        encoding="utf-8",
    )
    from synthadoc.integration.http_server import create_app
    with TestClient(create_app(wiki_root=tmp_wiki)) as client:
        resp = client.get("/lint/report")
    assert resp.status_code == 200
    data = resp.json()
    assert "conflicted-page" in data["contradictions"]
    assert "orphan-page" in data["orphans"]


def test_query_empty_question_returns_422(tmp_wiki):
    from synthadoc.integration.http_server import create_app
    with TestClient(create_app(wiki_root=tmp_wiki)) as client:
        resp = client.post("/query", json={"question": ""})
    assert resp.status_code == 422
