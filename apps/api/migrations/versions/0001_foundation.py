"""Foundation: extension, roles, reference + tenant + queue tables, RLS spine.

Revision ID: 0001
Revises:
Create Date: 2026-06-06

Security model (docs/ARCHITECTURE.md §3.5):
- cg_owner  — migrations only; owns all tables. NEVER a runtime credential.
- cg_app    — API request path. Not owner, no BYPASSRLS ⇒ RLS always binds it.
- cg_worker — background worker + ingestion CLI. RLS-bound on tenant tables.

Roles are created NOLOGIN if absent (cluster-level, idempotent); LOGIN +
passwords are environment bootstrap (infra/db-init locally, runbook on Neon) —
credentials never live in migrations.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY, JSONB

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

RUNTIME_ROLES = ("cg_app", "cg_worker")


def _create_roles() -> None:
    for role in RUNTIME_ROLES:
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') THEN
                    CREATE ROLE {role} NOLOGIN;
                END IF;
            END
            $$;
            """
        )


def _create_functions() -> None:
    # THE tenant-context reader. NULLIF guard: unset AND empty-string both yield
    # NULL -> RLS predicate UNKNOWN -> zero rows. Fail-closed by construction.
    op.execute(
        """
        CREATE FUNCTION app_current_tenant() RETURNS bigint
        LANGUAGE sql STABLE
        AS $$
            SELECT NULLIF(current_setting('app.tenant_id', true), '')::bigint
        $$;
        """
    )
    op.execute(
        """
        CREATE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            -- clock_timestamp(), not now(): now() is frozen per-transaction,
            -- so claim-then-update within one txn would never advance it.
            NEW.updated_at := clock_timestamp();
            RETURN NEW;
        END;
        $$;
        """
    )


