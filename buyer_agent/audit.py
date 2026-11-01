
import logging
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    insert,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import create_async_engine

from config import settings


logger = logging.getLogger(__name__)

engine = create_async_engine(
    settings.database_url,
    pool_pre_ping=True,
)

metadata = MetaData()


audit_outbox = Table(
    "audit_outbox",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("node_name", Text, nullable=False),
    Column("decision", Text, nullable=False),
    Column("reasoning", Text, nullable=True),
    Column("tokens_used", Integer, nullable=True),
    Column("latency_ms", Integer, nullable=True),
    Column("status", Text, nullable=False, server_default="pending"),
    Column("attempts", Integer, nullable=False, server_default="0"),
    Column("max_attempts", Integer, nullable=False, server_default="5"),
    Column("next_retry_at", DateTime(timezone=True), nullable=False,
           server_default=func.now()),
    Column("created_at", DateTime(timezone=True), nullable=False,
           server_default=func.now()),
)


async def write_audit_log(
    run_id: str,
    node_name: str,
    decision: str,
    reasoning: str,
    tokens_used: int,
    latency_ms: int,
):
    if not run_id:
        raise ValueError("run_id is required for audit logging")

    event_id = uuid.uuid4()

    statement = insert(audit_outbox).values(
        id=event_id,
        run_id=uuid.UUID(str(run_id)),
        node_name=node_name,
        decision=decision,
        reasoning=reasoning,
        tokens_used=tokens_used,
        latency_ms=latency_ms,
    )

    async with engine.begin() as connection:
        await connection.execute(statement)

    logger.info(
        "Audit event queued: event_id=%s run_id=%s node=%s",
        event_id,
        run_id,
        node_name,
    )


async def close_audit_db():
    await engine.dispose()
