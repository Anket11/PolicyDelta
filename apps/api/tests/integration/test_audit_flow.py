"""The core loop, end-to-end: POST 202 → worker → poll → grounded findings.

This is the spec's PocketPay demo as an executable test: the same policy is a
HIGH violation as of June 2026 (3-day amendment in force) and compliant as of
January 2025 (old 7-day rule governed). Plus: grounding gate, partial-failure
semantics, job retry/lease recovery, and worker-path RLS proofs.
"""

import datetime as dt
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from policydelta.audit.schema import ClauseFinding, ClauseVerdict, RiskLevel, Verdict
from policydelta.providers import FakeChat, FakeEmbeddings
from policydelta.worker.runner import Worker
from tests.conftest import issue_key

pytestmark = [pytest.mark.integration, pytest.mark.anyio]

POCKETPAY_POLICY = (
    "PocketPay will hold user funds for up to 7 business days before clearing.\n\n"
    "Customer KYC records are retained for 5 years after account closure."
)


@pytest.fixture
async def audit_key(owner_engine: AsyncEngine, two_orgs: tuple[int, int]) -> str:
    return await issue_key(owner_engine, two_orgs[0], ["audit"])


def make_worker(engine: AsyncEngine, chat: FakeChat | None = None) -> Worker:
    return Worker(engine, FakeEmbeddings(), chat or FakeChat(), name="test-worker")


async def _post_audit(
    api: AsyncClient,
    key: str,
    *,
    as_of: str,
    policy_text: str = POCKETPAY_POLICY,
    jurisdiction: str = "PK",
) -> dict[str, Any]:
    response = await api.post(
        "/api/v1/audits",
        json={"policy_text": policy_text, "jurisdiction": jurisdiction, "as_of_date": as_of},
        headers={"X-API-Key": key},
    )
    assert response.status_code == 202, response.text
    assert response.headers["Location"].startswith("/api/v1/audits/")
    body: dict[str, Any] = response.json()
    assert body["status"] == "queued"
    return body


async def _get_run(api: AsyncClient, key: str, run_id: int) -> dict[str, Any]:
    response = await api.get(f"/api/v1/audits/{run_id}", headers={"X-API-Key": key})
    assert response.status_code == 200
    return response.json()  # type: ignore[no-any-return]


class TestPocketPayDemo:
    async def test_violation_found_after_amendment(
        self,
        seeded_corpus: None,
        api: AsyncClient,
        audit_key: str,
        worker_engine: AsyncEngine,
    ) -> None:
        run = await _post_audit(api, audit_key, as_of="2026-06-06")
        assert await make_worker(worker_engine).drain() >= 1

        finished = await _get_run(api, audit_key, run["id"])
        assert finished["status"] == "succeeded"
        assert finished["verdict"] == "VIOLATIONS_FOUND"
        assert finished["coverage"]["violation"] >= 1
        assert finished["model"] == "fake-chat-v1"
        assert finished["finished_at"] is not None

        findings = (
            await api.get(f"/api/v1/audits/{run['id']}/findings", headers={"X-API-Key": audit_key})
        ).json()
        assert findings["total"] >= 1
        finding = findings["items"][0]
        assert finding["risk_level"] == "HIGH"
        assert finding["citation"] == "Regulation 12-B(4) (as amended)"
        assert finding["source_url"] == "https://example-secp.gov.pk/sro/1234-2026.pdf"
        assert "three (3) business days" in finding["grounding_quote"]
        assert "7 business days" in finding["offending_policy_text"]
        assert finding["source_chunk_id"] is not None  # citation tracing for the UI

    async def test_same_policy_compliant_before_amendment(
        self,
        seeded_corpus: None,
        api: AsyncClient,
        audit_key: str,
        worker_engine: AsyncEngine,
    ) -> None:
        """Point-in-time: in January 2025 the 7-day rule governed — no violation."""
        run = await _post_audit(api, audit_key, as_of="2025-01-01")
        await make_worker(worker_engine).drain()

        finished = await _get_run(api, audit_key, run["id"])
        assert finished["status"] == "succeeded"
        assert finished["verdict"] == "COMPLIANT"
        assert finished["coverage"]["violation"] == 0

    async def test_run_snapshots_inputs_for_reproducibility(
        self,
        seeded_corpus: None,
        api: AsyncClient,
        audit_key: str,
        worker_engine: AsyncEngine,
        owner_engine: AsyncEngine,
    ) -> None:
        run = await _post_audit(api, audit_key, as_of="2026-06-06")
        await make_worker(worker_engine).drain()
        async with owner_engine.connect() as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT policy_text_snapshot, clauses_snapshot, retrieved_chunk_ids "
                        "FROM audit_runs WHERE id = :id"
                    ),
                    {"id": run["id"]},
                )
            ).one()
        assert row.policy_text_snapshot == POCKETPAY_POLICY
        assert len(row.clauses_snapshot) == 2
        assert len(row.retrieved_chunk_ids) >= 1


class TestHonestVerdicts:
    async def test_no_applicable_law_is_insufficient_never_compliant(
        self,
        seeded_corpus: None,
        api: AsyncClient,
        audit_key: str,
        worker_engine: AsyncEngine,
        owner_engine: AsyncEngine,
    ) -> None:
        async with owner_engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO jurisdictions (code, name) VALUES ('EU', 'European Union') "
                    "ON CONFLICT (code) DO NOTHING"
                )
            )
        run = await _post_audit(api, audit_key, as_of="2026-06-06", jurisdiction="EU")
        await make_worker(worker_engine).drain()

