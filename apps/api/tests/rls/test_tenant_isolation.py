"""Cross-tenant isolation proofs — the blocking security lane.

Every test connects as a runtime role (cg_app / cg_worker), never as the
owner: a superuser silently bypasses RLS, so an owner-connected "pass" proves
nothing. A red test in this file is a security incident, not a flaky test.
"""

import pytest
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncEngine

from tests.db import set_tenant_context

pytestmark = [pytest.mark.rls, pytest.mark.anyio]


class TestSelectIsolation:
    async def test_sees_only_own_organization(
        self, app_engine: AsyncEngine, two_orgs: tuple[int, int]
    ) -> None:
        org_a, _org_b = two_orgs
        async with app_engine.connect() as conn:
            await set_tenant_context(conn, org_a)
            rows = (await conn.execute(text("SELECT id FROM organizations"))).fetchall()
        assert [row[0] for row in rows] == [org_a]

    async def test_other_tenant_is_invisible_not_forbidden(
        self, app_engine: AsyncEngine, two_orgs: tuple[int, int]
    ) -> None:
        org_a, org_b = two_orgs
        async with app_engine.connect() as conn:
            await set_tenant_context(conn, org_a)
            result = await conn.execute(
                text("SELECT count(*) FROM organizations WHERE id = :other"), {"other": org_b}
            )
        assert result.scalar_one() == 0  # invisible — no existence leak

    async def test_no_context_returns_zero_rows(
        self, app_engine: AsyncEngine, two_orgs: tuple[int, int]
    ) -> None:
        """Fail-closed: a forgotten SET LOCAL can never leak data."""
        async with app_engine.connect() as conn:
            result = await conn.execute(text("SELECT count(*) FROM organizations"))
        assert result.scalar_one() == 0

    async def test_empty_string_context_fails_closed_not_500(
        self, app_engine: AsyncEngine, two_orgs: tuple[int, int]
    ) -> None:
        """NULLIF guard: empty string casts to NULL, not an invalid-syntax error."""
        async with app_engine.connect() as conn:
            await set_tenant_context(conn, None)  # sets ''
            result = await conn.execute(text("SELECT count(*) FROM organizations"))
        assert result.scalar_one() == 0

    async def test_context_is_transaction_local(
        self, app_engine: AsyncEngine, two_orgs: tuple[int, int]
    ) -> None:
        """A pooled connection must not inherit the previous transaction's tenant."""
        org_a, _ = two_orgs
        async with app_engine.connect() as conn:
            await set_tenant_context(conn, org_a)
            await conn.commit()  # transaction ends; SET LOCAL must die with it
            result = await conn.execute(text("SELECT count(*) FROM organizations"))
        assert result.scalar_one() == 0


class TestWriteIsolation:
    async def test_update_of_other_tenant_is_a_noop(
        self, app_engine: AsyncEngine, two_orgs: tuple[int, int]
    ) -> None:
        org_a, org_b = two_orgs
        async with app_engine.connect() as conn:
            await set_tenant_context(conn, org_a)
            result = await conn.execute(
                text("UPDATE api_keys SET last_used_at = now() WHERE tenant_id = :other"),
                {"other": org_b},
            )
        assert result.rowcount == 0

