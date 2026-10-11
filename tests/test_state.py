import json
import threading
from pathlib import Path

from agent_orc.state import write_atomically


def test_writes_at_once_never_leave_a_mixture(tmp_path: Path) -> None:
    target = tmp_path / "state.json"
    texts = [json.dumps({"writer": number, "padding": "x" * (number * 500)}) for number in range(8)]
    for _ in range(50):
        threads = [threading.Thread(target=write_atomically, args=(target, text)) for text in texts]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert target.read_text(encoding="utf-8") in texts
    assert list(tmp_path.iterdir()) == [target]
