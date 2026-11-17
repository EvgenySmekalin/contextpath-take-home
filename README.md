# ContextPath take-home

Recordings are replayed tick by tick (streamer), checked against `rules.json` (agent), and the
popups are stored and served by `GET /audit` (server). Part 2 is in [PART2.md](PART2.md).

## How to run it

```bash
docker compose up --build
```

The replay of `./data/*.tar.gz` takes about 72 seconds (`TICK_MS` defaults to 20). Popups appear
in `/audit` as they fire; all 14 are there when `employees` exits with code 0 (emp-1: 7,
emp-2: 4, emp-3: 3). `server` keeps running.

```bash
curl 'localhost:8080/audit?employee=emp-3&rule=salesforce-record-deleted'
```

The API can also be tried in the browser: http://localhost:8080/docs

Tests: `pip install -r requirements-dev.txt`, then `pytest` (unit tests and the pipeline as real
processes) and `pytest -m docker` (the compose stack against the expected popups).

## Decisions I made and why

- **Three packages that share no code** (`src/streamer`, `src/agent`, `src/server`), talking
  JSON over HTTP. Each can be read, tested and replaced alone.
- **A launcher starts one agent and one streamer per tarball.** Compose cannot create a service
  per file, and services listed by hand would ignore a fourth tarball.
- **The agent sends each popup while handling the tick** and repeats it until the server takes
  it; the server stores a repeated popup once. No queue; a server outage pauses the replay.
- **Small on purpose.** My first version had a delivery queue, tick numbering and metrics, and
  was twice the size. I removed what the task does not need; Part 2 says where it belongs.
- **Clicked text is the OCR block under the cursor**, because a click has coordinates only.
- **The window in front comes from focus events**, not from the click, which names the process
  under the cursor (`msedgewebview2.exe` inside Outlook).
- **A rule without `click` is a state**: it fires when it becomes true, with that event's time.
- **A double click is one click.** The task does not say; the recorder marks the 2nd and 3rd
  click as `double` and `triple`, and I skip them.

## What I would do next

1. Take the clicked text from the accessibility tree instead of OCR, the least certain step.
2. An outbox on disk in the agent, so a server outage neither pauses it nor loses popups.
3. Skip and count broken events instead of failing the run; authentication on the server.
4. Run every test scenario through `docker compose`, with coverage. Did not fit in the day.

## How I used AI

Claude Code throughout: to explore the recordings with scripts before any design, to write down
the expected popups before the engine (now `tests/test_golden.py`), and to generate code that
was then run at every level. The decisions above stayed with me, including a second pass that
cut the AI's over-engineered first version in half.
