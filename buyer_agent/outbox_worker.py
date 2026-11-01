
import asyncio
import logging
import os
import socket
import uuid

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    Table,
    Text,
    and_,
    insert,
    or_,
    select,
    update,
    func,
)
from sqlalchemy.dialects.postgresql import UUID, insert as pg_insert
from sqlalchemy.ext.asyncio import create_async_engine


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

logger = logging.getLogger("outbox_worker")

DATABASE_URL = os.environ["DATABASE_URL"]

POLL_INTERVAL = float(os.getenv("OUTBOX_POLL_INTERVAL", "2"))
BATCH_SIZE = int(os.getenv("OUTBOX_BATCH_SIZE", "10"))
LOCK_TIMEOUT_SECONDS = int(os.getenv("OUTBOX_LOCK_TIMEOUT", "120"))

WORKER_ID = f"{socket.gethostname()}-{uuid.uuid4()}"

engine = create_async_engine(
    DATABASE_URL,
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
    Column("reasoning", Text),
    Column("tokens_used", Integer),
    Column("latency_ms", Integer),
    Column("status", Text, nullable=False),
    Column("attempts", Integer, nullable=False),
    Column("max_attempts", Integer, nullable=False),
    Column("next_retry_at", DateTime(timezone=True), nullable=False),
    Column("locked_at", DateTime(timezone=True)),
    Column("locked_by", Text),
    Column("last_error", Text),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("processed_at", DateTime(timezone=True)),
)

audit_log = Table(
    "audit_log",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("node_name", Text, nullable=False),
    Column("decision", Text, nullable=False),
    Column("reasoning", Text),
    Column("tokens_used", Integer),
    Column("latency_ms", Integer),
    Column("created_at", DateTime(timezone=True)),
)


async def claim_events():
    """
    Claim a batch of events in a short transaction.

    SKIP LOCKED allows multiple worker instances to process
    different events without waiting on one another.
    """
    async with engine.begin() as connection:
        # Recover events abandoned by workers that crashed.
        # Recover abandoned events whose retry limit is exhausted.
        expired_lock = (
            audit_outbox.c.status == "processing",
        ) 

        expired_condition = and_(
            expired_lock[0],
            audit_outbox.c.locked_at
            < func.now()
            - func.make_interval(0, 0, 0, 0, 0, 0, LOCK_TIMEOUT_SECONDS),
        )

        # Exhausted events go directly to dead-letter status.
        await connection.execute(
            update(audit_outbox)
            .where(
                and_(
                    expired_condition,
                    audit_outbox.c.attempts >= audit_outbox.c.max_attempts,
                )
            )
            .values(
                status="dead",
                locked_at=None,
                locked_by=None,
                processed_at=func.now(),
                last_error="Worker lock expired after maximum attempts",
            )
        )

        # Events with retries remaining become eligible again.
        await connection.execute(
            update(audit_outbox)
            .where(
                and_(
                    expired_condition,
                    audit_outbox.c.attempts < audit_outbox.c.max_attempts,
                )
            )
            .values(
                status="pending",
                locked_at=None,
                locked_by=None,
                next_retry_at=func.now(),
                last_error="Worker lock expired; event recovered",
            )
        )

        statement = (
            select(audit_outbox)
            .where(
                and_(
                    audit_outbox.c.status == "pending",
                    audit_outbox.c.next_retry_at <= func.now(),
                    audit_outbox.c.attempts < audit_outbox.c.max_attempts,
                )
            )
            .order_by(
                audit_outbox.c.next_retry_at,
                audit_outbox.c.created_at,
            )
            .limit(BATCH_SIZE)
            .with_for_update(skip_locked=True)
        )

        result = await connection.execute(statement)
        events = result.mappings().all()

        claimed = []

        for event in events:
            new_attempt = event["attempts"] + 1

            await connection.execute(
                update(audit_outbox)
                .where(audit_outbox.c.id == event["id"])
                .values(
                    status="processing",
                    attempts=new_attempt,
                    locked_at=func.now(),
                    locked_by=WORKER_ID,
                )
            )

            claimed.append({
                **dict(event),
                "attempts": new_attempt,
            })

        return claimed



async def deliver_event(event):
    """
    Deliver an event only if this worker still owns it.

    Audit insertion and outbox completion happen atomically.
    """
    async with engine.begin() as connection:

        # Verify ownership and lock the outbox row.
        ownership = await connection.execute(
            select(audit_outbox.c.id)
            .where(
                and_(
                    audit_outbox.c.id == event["id"],
                    audit_outbox.c.status == "processing",
                    audit_outbox.c.locked_by == WORKER_ID,
                )
            )
            .with_for_update()
        )

        if ownership.first() is None:
            logger.warning(
                "Skipping event %s: worker no longer owns it",
                event["id"],
            )
            return False

        # Insert audit record idempotently.
        await connection.execute(
            pg_insert(audit_log)
            .values(
                id=event["id"],
                run_id=event["run_id"],
                node_name=event["node_name"],
                decision=event["decision"],
                reasoning=event["reasoning"],
                tokens_used=event["tokens_used"],
                latency_ms=event["latency_ms"],
                created_at=event["created_at"],
            )
            .on_conflict_do_nothing(
                index_elements=[audit_log.c.id]
            )
        )

        # Complete the outbox event.
        result = await connection.execute(
            update(audit_outbox)
            .where(
                and_(
                    audit_outbox.c.id == event["id"],
                    audit_outbox.c.status == "processing",
                    audit_outbox.c.locked_by == WORKER_ID,
                )
            )
            .values(
                status="delivered",
                processed_at=func.now(),
                locked_at=None,
                locked_by=None,
                last_error=None,
            )
        )

        if result.rowcount != 1:
            raise RuntimeError(
                f"Could not complete owned outbox event {event['id']}"
            )

        return True


async def record_failure(event, error):
    error_message = str(error)[:4000]

    if event["attempts"] >= event["max_attempts"]:
        new_status = "dead"
        next_retry = func.now()
    else:
        new_status = "pending"
        delay_seconds = min(
            2 ** event["attempts"],
            300,
        )
        next_retry = func.now() + func.make_interval(
            0, 0, 0, 0, 0, 0, delay_seconds
        )

    async with engine.begin() as connection:
        await connection.execute(
            update(audit_outbox)
            .where(
                and_(
                    audit_outbox.c.id == event["id"],
                    audit_outbox.c.status == "processing",
                    audit_outbox.c.locked_by == WORKER_ID,
                )
            )
            .values(
                status=new_status,
                next_retry_at=next_retry,
                locked_at=None,
                locked_by=None,
                last_error=error_message,
            )
        )

    logger.exception(
        "Failed to deliver event %s (attempt %s/%s)",
        event["id"],
        event["attempts"],
        event["max_attempts"],
    )



async def process_one_event(event):
    try:
        delivered = await deliver_event(event)

        if delivered:
            logger.info(
                "Delivered event=%s run_id=%s node=%s",
                event["id"],
                event["run_id"],
                event["node_name"],
            )

    except Exception as error:
        logger.exception(
            "Delivery failed for event=%s",
            event["id"],
        )

        try:
            await record_failure(event, error)
        except Exception:
            logger.exception(
                "Could not record failure for event=%s",
                event["id"],
            )


async def process_batch():
    events = await claim_events()

    if not events:
        return 0

    await asyncio.gather(
        *(process_one_event(event) for event in events)
    )

    return len(events)



async def main():
    logger.info("Outbox worker started: %s", WORKER_ID)

    try:
        while True:
            try:
                processed = await process_batch()

                if processed == 0:
                    await asyncio.sleep(POLL_INTERVAL)

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception(
                    "Outbox worker batch failed. "
                    "Retrying after %s seconds.",
                    POLL_INTERVAL,
                )

                await asyncio.sleep(POLL_INTERVAL)

    finally:
        logger.info("Outbox worker shutting down")
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Outbox worker stopped")
