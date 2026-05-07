"""``policydelta`` — operator CLI.

Provisioning (jurisdictions, orgs, keys) and corpus maintenance (confirm,
supersede) are owner-role operations: they bypass RLS deliberately and never
run inside the API process. Ingestion runs under the worker role.
"""

import asyncio
import datetime as dt
import json
from collections.abc import Awaitable, Callable
from pathlib import Path

import typer

from policydelta.cli import ingest_ops
from policydelta.cli.provision import (
    create_api_key,
    create_jurisdiction,
    create_organization,
)
from policydelta.cli.seed import seed_with_default_engine

app = typer.Typer(help="PolicyDelta operator CLI", no_args_is_help=True)
jurisdictions_app = typer.Typer(help="Manage jurisdiction codes", no_args_is_help=True)
org_app = typer.Typer(help="Manage organizations (tenants)", no_args_is_help=True)
keys_app = typer.Typer(help="Manage org API keys", no_args_is_help=True)
ingest_app = typer.Typer(help="Ingest regulatory documents", no_args_is_help=True)
worker_app = typer.Typer(help="Run the job worker", no_args_is_help=True)
app.add_typer(jurisdictions_app, name="jurisdictions")
app.add_typer(org_app, name="org")
app.add_typer(keys_app, name="keys")
app.add_typer(ingest_app, name="ingest")
app.add_typer(worker_app, name="worker")


def _run[T](coro: Awaitable[T]) -> T:
    return asyncio.run(_as_coro(coro))


async def _as_coro[T](awaitable: Awaitable[T]) -> T:
    return await awaitable


@jurisdictions_app.command("add")
def jurisdictions_add(code: str, name: str) -> None:
    """Register a jurisdiction code (e.g. PK 'Pakistan')."""
    created = _run(create_jurisdiction(code=code.upper(), name=name))
    typer.echo(f"{'Created' if created else 'Already exists'}: {code.upper()}")


@org_app.command("create")
def org_create(
    name: str,
    jurisdiction: str = typer.Option("PK", "--jurisdiction", "-j"),
) -> None:
    """Provision a tenant organization."""
    org_id = _run(create_organization(name=name, home_jurisdiction=jurisdiction.upper()))
    typer.echo(f"Created organization id={org_id} name={name!r}")


@keys_app.command("create")
def keys_create(
    org_id: int = typer.Option(..., "--org-id"),
    name: str = typer.Option("default", "--name"),
    scopes: str = typer.Option("read", "--scopes", help="Comma-separated: read,audit,admin"),
) -> None:
    """Issue an API key. The full key is printed ONCE and never stored."""
    scope_list = [scope.strip() for scope in scopes.split(",") if scope.strip()]
    full_key = _run(create_api_key(org_id=org_id, name=name, scopes=scope_list))
    typer.echo("API key created. Store it now — it cannot be recovered:")
    typer.echo(full_key)


@app.command("seed")
def seed() -> None:
    """Load the development corpus (idempotent; fake embeddings, zero spend)."""
    inserted = _run(seed_with_default_engine())
    typer.echo(f"Seed complete: {inserted} new document(s).")


@ingest_app.command("url")
def ingest_url(
    source_url: str,
    title: str = typer.Option(..., "--title"),
    issuing_body: str = typer.Option(..., "--body"),
    document_type: str = typer.Option("Circular", "--type"),
    jurisdiction: str = typer.Option("PK", "--jurisdiction", "-j"),
    published: str = typer.Option(..., "--published", help="YYYY-MM-DD"),
) -> None:
    """Enqueue ingestion of a regulatory document by URL."""
    job_id = _run(
        ingest_ops.enqueue_ingest(
            source_url=source_url,
            file_path=None,
            title=title,
            issuing_body=issuing_body,
            document_type=document_type,
            jurisdiction=jurisdiction.upper(),
            published_date=dt.date.fromisoformat(published),
        )
    )
    typer.echo(f"Queued ingest job {job_id}. Run `policydelta worker run-once` to process.")


@ingest_app.command("file")
def ingest_file(
    path: Path,
    title: str = typer.Option(..., "--title"),
    issuing_body: str = typer.Option(..., "--body"),
    document_type: str = typer.Option("Circular", "--type"),
    jurisdiction: str = typer.Option("PK", "--jurisdiction", "-j"),
    published: str = typer.Option(..., "--published", help="YYYY-MM-DD"),
) -> None:
    """Enqueue ingestion of a local .pdf or .md file."""
    job_id = _run(
        ingest_ops.enqueue_ingest(
            source_url=f"file://{path.resolve().as_posix()}",
            file_path=str(path.resolve()),
            title=title,
            issuing_body=issuing_body,
            document_type=document_type,
            jurisdiction=jurisdiction.upper(),
            published_date=dt.date.fromisoformat(published),
        )
    )
    typer.echo(f"Queued ingest job {job_id}. Run `policydelta worker run-once` to process.")


@worker_app.command("run-once")
def worker_run_once(max_jobs: int = typer.Option(None, "--max-jobs")) -> None:
    """Reap expired leases, then drain the queue (PaaS-cron friendly)."""
    processed = _run(ingest_ops.run_worker_once(max_jobs=max_jobs))
    typer.echo(f"Processed {processed} job(s).")


@app.command("status")
def status(
    review: bool = typer.Option(False, "--review", help="List documents awaiting review"),
    failed: bool = typer.Option(False, "--failed", help="List failed jobs"),
) -> None:
    """Queue + review-gate visibility."""
    if review:
        docs = _run(ingest_ops.list_review_documents())
        if not docs:
            typer.echo("Review queue is empty.")
        for doc_id, title, reason in docs:
            typer.echo(f"[{doc_id}] ({reason}) {title}")
        return
    jobs = _run(ingest_ops.list_jobs(status="failed" if failed else None))
    if not jobs:
        typer.echo("No jobs.")
    for job in jobs:
        error = f" error={job.error}" if job.error else ""
        typer.echo(f"[{job.id}] {job.kind} {job.status} attempts={job.attempts}{error}")


