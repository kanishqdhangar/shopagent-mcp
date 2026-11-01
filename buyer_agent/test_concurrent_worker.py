import asyncio
import outbox_worker as worker

async def main():
    print(f"Worker ID: {worker.WORKER_ID}", flush=True)

    try:
        events = await worker.claim_events()

        event_ids = [str(event["id"]) for event in events]
        print(f"Claimed {len(events)} events:", flush=True)
        for event_id in event_ids:
            print(event_id, flush=True)

        await asyncio.gather(
            *(worker.process_one_event(event) for event in events)
        )

        print(f"Processed events: {len(events)}", flush=True)
    finally:
        await worker.engine.dispose()

asyncio.run(main())
