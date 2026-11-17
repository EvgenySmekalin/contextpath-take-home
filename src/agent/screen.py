"""What is on the employee's displays, according to the OCR snapshots."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Block:
    """A piece of text and its box, in pixels of the snapshot (not of the display)."""

    text: str
    x: float
    y: float
    width: float
    height: float

    def contains(self, x: float, y: float) -> bool:
        return self.x <= x <= self.x + self.width and self.y <= y <= self.y + self.height


@dataclass(frozen=True)
class Snapshot:
    width: float
    height: float
    blocks: list[Block]


class Screen:
    """The latest snapshot of every display."""

    def __init__(self, displays: dict[int, tuple[float, float, float, float]]):
        # display id -> (left, top, width, height) on the virtual desktop;
        # left and top are negative for a display left of or above the primary one.
        self._displays = displays
        self._snapshots: dict[int, Snapshot] = {}
        self._blocks_by_filename: dict[str, list[Block]] = {}

    def update(self, ocr: dict) -> None:
        """Take in one row of ``ocr.jsonl``."""
        same_as = ocr.get("deduplicated_from")
        if same_as:
            # The row has no text of its own: the screen looks like it did in
            # that earlier snapshot. If we never saw it, the text is unknown.
            blocks = self._blocks_by_filename.get(same_as, [])
        else:
            blocks = [
                Block(block["text"].strip(), *block["bounding_box"])
                for block in ocr["ocr_text_blocks"]
            ]
            self._blocks_by_filename[ocr["filename"]] = blocks
        width, height = ocr["resolution"]
        self._snapshots[ocr["display_id"]] = Snapshot(width, height, blocks)

    def text_at(self, x: float, y: float) -> str | None:
        """The text under a point of the virtual desktop, or None."""
        for display_id, (left, top, width, height) in self._displays.items():
            inside = left <= x < left + width and top <= y < top + height
            snapshot = self._snapshots.get(display_id)
            if not inside or snapshot is None:
                continue
            # A snapshot can be smaller than its display: a 3840x2160 display
            # is captured as 1920x1080.
            snapshot_x = (x - left) * snapshot.width / width
            snapshot_y = (y - top) * snapshot.height / height
            hits = [b for b in snapshot.blocks if b.contains(snapshot_x, snapshot_y)]
            if hits:
                # Boxes can nest (a line inside a paragraph): the smallest is the most specific.
                return min(hits, key=lambda b: b.width * b.height).text
        return None

    def texts(self) -> list[str]:
        """Every piece of text visible on any display."""
        return [block.text for snapshot in self._snapshots.values() for block in snapshot.blocks]
