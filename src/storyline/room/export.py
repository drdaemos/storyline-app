"""Write the room protocol description that interfaces in other languages are checked against.

Run ``uv run python -m storyline.room.export`` after changing ``storyline.room.protocol``.
"""

import json
import sys
from pathlib import Path

from storyline.room.protocol import protocol_schema

FRONTEND_PROTOCOL_PATH = Path("frontend/src/protocol/protocol.json")


def protocol_document() -> str:
    """Return the protocol description as the text of the checked-in file."""
    return json.dumps(protocol_schema(), indent=2, sort_keys=True) + "\n"


def main() -> None:
    """Write the protocol description to the path given on the command line, or to the frontend's copy."""
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else FRONTEND_PROTOCOL_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(protocol_document(), encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
