"""Start one agent and one streamer for every recording in DATA_DIR.

Docker Compose cannot create a service per file, and the number of recordings
in ./data is not fixed, so this script starts the pairs. It only starts and
stops processes: it never sees an event, a rule or a popup.

Environment: DATA_DIR (default data), AGENT_BASE_PORT (default 9100); everything
else (TICK_MS, SERVER_URL, RULES_PATH) is passed on to the processes it starts.
"""

import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    data_dir = Path(os.environ.get("DATA_DIR", "data"))
    base_port = int(os.environ.get("AGENT_BASE_PORT", "9100"))
    # macOS leaves "._name" files next to copied files; they are not recordings.
    recordings = sorted(p for p in data_dir.glob("*.tar.gz") if not p.name.startswith("."))
    if not recordings:
        print(f"no recordings in {data_dir}", file=sys.stderr)
        return 1

    agents, streamers = [], []
    for port, recording in enumerate(recordings, start=base_port):
        agents.append(start("agent.main", AGENT_PORT=str(port)))
        streamers.append(
            start("streamer.main", RECORDING=str(recording), AGENT_URL=f"http://127.0.0.1:{port}")
        )

    try:
        # Done when every streamer has finished. An agent never finishes by
        # itself, so one that has stopped has crashed.
        while any(s.poll() is None for s in streamers) and all(a.poll() is None for a in agents):
            time.sleep(0.2)
        return 0 if all(s.poll() == 0 for s in streamers) else 1
    finally:
        for process in streamers + agents:
            process.terminate()


def start(module: str, **settings: str) -> subprocess.Popen:
    return subprocess.Popen([sys.executable, "-m", module], env={**os.environ, **settings})


if __name__ == "__main__":
    sys.exit(main())
