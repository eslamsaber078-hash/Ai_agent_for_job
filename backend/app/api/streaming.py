"""SSE bridge: run a blocking import in a worker thread and stream its real per-site
progress to the browser as it happens — the percentage the user sees is the actual
number of sites finished, not an estimate."""

import json
import threading
import time
from collections import deque

from fastapi.responses import StreamingResponse

from ..database import SessionLocal


def _sse_payload(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def stream_run(sites: list[str], runner) -> StreamingResponse:
    """Run `runner(session, sites, on_progress)` in a worker thread and stream events.

    `runner` must call `on_progress(done, total, name, label, line)` once per finished
    site and return the dict for the final `done` event.

    The thread opens its own session instead of borrowing the request's. That session is
    closed the moment the response ends, so closing the tab mid-import used to pull it out
    from under a running `db.commit()` and lose the sites already fetched. Shutting the
    browser now stops the pictures, not the import.
    """
    queue: deque = deque()
    final: dict = {}

    def on_progress(done, total, name, label, line):
        queue.append({
            "type": "progress", "done": done, "total": total,
            "name": name, "label": label, "line": line,
        })

    def worker():
        session = SessionLocal()
        try:
            final.update(runner(session, sites, on_progress))
        except Exception as exc:  # noqa: BLE001 - surface it as a stream event
            # RuntimeError is the "already importing" guard: that text is meant for
            # the user, so it is shown as written instead of leaking the class name.
            message = str(exc) if isinstance(exc, RuntimeError) else f"{type(exc).__name__}: {exc}"
            final.update({"type": "error", "message": message})
        finally:
            session.close()
        queue.append(None)  # sentinel: the run is over, whatever happened

    threading.Thread(target=worker, daemon=True).start()

    def gen():
        while True:
            while queue:
                item = queue.popleft()
                if item is None:
                    if not final:
                        final.update({"type": "error", "message": "The import finished without a result."})
                    yield _sse_payload(final)
                    return
                yield _sse_payload(item)
            time.sleep(0.15)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
