"""
Step 3.4H.2 zero-provider-call probe: what happens to a provider call when a deadline cancels it? Uses a LOCAL stub HTTP server only (127.0.0.1), the real `ai_service._call_provider` and `_tier_slot`.

  PYTHONIOENCODING=utf-8 PYTHONPATH=. python benchmarks/ai_search/baseline_2026_10_04/step3_4h/cancellation_probe.py

Questions answered (printed as PASS/INFO lines):
  1. Does cancelling a slow in-flight provider call close the connection (server sees EOF) promptly?
  2. Is the tier slot released when the call is cancelled?
  3. Is the (provider, model) pair marked exhausted when the call is CANCELLED (deadline) vs when httpx's own read timeout fires?
  4. Does the 30 s read timeout bound the whole call, or only the gap between bytes (a server that dribbles bytes)?
  5. Does cancelling an `await loop.run_in_executor(...)` stop the thread?
"""
from __future__ import annotations

import asyncio
import sys
import threading
import time

sys.path.insert(0, ".")
import httpx  # noqa: E402

from app.services import ai_service as S  # noqa: E402

log: list[str] = []


def say(tag: str, msg: str) -> None:
    print(f"{tag:5s} {msg}", flush=True)


class Stub:
    """mode 'hang': accept, read the request, never answer. mode 'dribble': send headers then one byte every `gap` s (a response that never completes within a total budget)."""

    def __init__(self, mode: str, gap: float = 0.5):
        self.mode, self.gap = mode, gap
        self.eof_at: float | None = None
        self.opened_at: float | None = None

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.opened_at = time.monotonic()
        try:
            head = await reader.readuntil(b"\r\n\r\n")
            n = 0
            for line in head.split(b"\r\n"):
                if line.lower().startswith(b"content-length:"):
                    n = int(line.split(b":")[1])
            await reader.readexactly(n)
            if self.mode == "dribble":
                writer.write(b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: 100000\r\n\r\n")
                await writer.drain()
                while True:
                    writer.write(b" ")
                    await writer.drain()
                    await asyncio.sleep(self.gap)
            else:
                while True:
                    data = await reader.read(1024)
                    if not data:
                        self.eof_at = time.monotonic()
                        return
        except (ConnectionError, asyncio.IncompleteReadError):
            self.eof_at = time.monotonic()
        finally:
            writer.close()


async def serve(stub: Stub):
    srv = await asyncio.start_server(stub.handle, "127.0.0.1", 0)
    return srv, srv.sockets[0].getsockname()[1]


async def main():
    # 1-3: hang server, deadline cancels the call via the tier slot exactly as _call_with_fallback uses it
    stub = Stub("hang")
    srv, port = await serve(stub)
    url = f"http://127.0.0.1:{port}/v1/chat/completions"
    provider = S._provider_name_for_url(url)
    limiter = S._TIER_LIMITERS["groq-hq"]
    before = limiter._in_flight

    async def attempt():
        async with S._tier_slot("groq-hq", "interactive") as acquired:
            if acquired:
                return await S._call_provider(url, "k", "probe-model-a", "p", "s", 50)

    t0 = time.monotonic()
    task = asyncio.ensure_future(attempt())
    await asyncio.sleep(0.5)
    say("INFO", f"in flight during call: {limiter._in_flight} (before {before})")
    try:
        await asyncio.wait_for(task, timeout=1.5)
    except asyncio.TimeoutError:
        pass
    waited = time.monotonic() - t0
    await asyncio.sleep(0.3)
    say("PASS" if task.cancelled() else "FAIL", f"1. wait_for deadline cancelled the provider task (cancelled={task.cancelled()}) after {waited:.2f}s")
    say("PASS" if stub.eof_at is not None else "FAIL", f"1. server saw the connection close ({'%.2fs after the cancel' % (stub.eof_at - (t0 + 2.0)) if stub.eof_at else 'never'})")
    say("PASS" if limiter._in_flight == before else "FAIL", f"2. tier slot released after cancel (in_flight {limiter._in_flight}, before {before})")
    say("PASS" if not S._is_exhausted(provider, "probe-model-a") else "FAIL", f"3a. a CANCELLED call does not mark the model exhausted (provider={provider})")
    srv.close()

    # 3b: httpx's own timeout (what a shortened per-attempt budget would produce) DOES mark exhausted
    stub2 = Stub("hang")
    srv2, port2 = await serve(stub2)
    url2 = f"http://127.0.0.1:{port2}/v1/chat/completions"
    saved = S._HTTP_TIMEOUT
    S._HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=1.0, write=10.0, pool=5.0)
    fl: list = []
    t0 = time.monotonic()
    out = await S._call_provider(url2, "k", "probe-model-b", "p", "s", 50, failure_log=fl)
    S._HTTP_TIMEOUT = saved
    say("INFO", f"3b. read timeout 1s returned {out!r} after {time.monotonic() - t0:.2f}s, failure_log={fl}")
    say("PASS" if S._is_exhausted(S._provider_name_for_url(url2), "probe-model-b") else "INFO", "3b. a timeout-shortened call marks the model exhausted (30 s cooldown): a budget cut-off would be charged to the provider")
    srv2.close()

    # 4: dribbling server, read timeout 1 s, bytes every 0.4 s: does the timeout ever fire?
    stub3 = Stub("dribble", gap=0.4)
    srv3, port3 = await serve(stub3)
    url3 = f"http://127.0.0.1:{port3}/v1/chat/completions"
    S._HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=1.0, write=10.0, pool=5.0)
    t0 = time.monotonic()
    try:
        await asyncio.wait_for(S._call_provider(url3, "k", "probe-model-c", "p", "s", 50), timeout=4.0)
        say("INFO", "4. call returned")
    except asyncio.TimeoutError:
        say("PASS", f"4. with bytes arriving every 0.4s the 1s read timeout never fired in {time.monotonic() - t0:.1f}s: the read timeout bounds the gap between bytes, NOT the total call")
    S._HTTP_TIMEOUT = saved
    srv3.close()

    # 5: executor thread is not stopped by cancelling the await
    done = threading.Event()

    def blocking():
        time.sleep(2.0)
        done.set()

    loop = asyncio.get_running_loop()
    fut = loop.run_in_executor(None, blocking)
    try:
        await asyncio.wait_for(fut, timeout=0.5)
    except asyncio.TimeoutError:
        pass
    say("INFO", f"5. after wait_for cancelled the executor await, thread still running: {not done.is_set()}")
    await asyncio.sleep(2.0)
    say("PASS" if done.is_set() else "INFO", "5. thread ran to completion anyway (cancel does not stop it; it occupies a default-executor worker until it returns)")


asyncio.run(main())
