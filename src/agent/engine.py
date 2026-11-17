"""The rule engine: events in, popups out. No network, no clock."""

from dataclasses import dataclass

from agent.rules import Rule, fill, matches
from agent.screen import Screen


@dataclass(frozen=True)
class Popup:
    employee: str
    rule: str
    ts: str
    title: str
    body: str


class Engine:
    """One employee's desktop and the rules checked against it.

    A click is a moment. The window in front, the clipboard and the text on
    screen are states: they last until the next event changes them. So:

    * a rule with a ``click`` condition is checked on every click, against
      the states at that moment;
    * a rule without one is checked whenever a state changes, and fires when
      it becomes true (or stays true with a different matched text).
    """

    def __init__(self, rules: list[Rule], employee: str, screen: Screen):
        self._click_rules = [rule for rule in rules if "click" in rule.conditions]
        self._state_rules = [rule for rule in rules if "click" not in rule.conditions]
        self._employee = employee
        self._screen = screen
        self._window_title: str | None = None
        self._process: str | None = None
        self._clipboard: str | None = None
        # rule id -> what the rule matched the last time it was checked.
        self._last_match: dict[str, dict[str, str] | None] = {}

    def feed(self, kind: str, ts: str, data: dict) -> list[Popup]:
        """Take in one recorded event; return the popups it causes, stamped with its time."""
        if kind == "mouse":
            return self._on_click(ts, data) if _is_new_left_click(data) else []
        if kind == "windows":
            # Only focus events say which window is in front. A click event
            # names a process too, but it is the one under the cursor
            # (msedgewebview2.exe inside the new Outlook, which is olk.exe).
            self._window_title = _text(data.get("window_title"))
            self._process = _text(data.get("process_name"))
        elif kind == "clipboard":
            # No text means the clipboard holds something else, an image for example.
            self._clipboard = _text(data.get("clipboard_content_text"))
        elif kind == "ocr":
            self._screen.update(data)
        else:
            # keyboard, keystrokes, mouse_scroll, mouse_drag: no rule looks at them.
            return []
        return self._on_state_change(ts)

    def _on_click(self, ts: str, data: dict) -> list[Popup]:
        click_text = self._screen.text_at(data["mouse_x"], data["mouse_y"])
        popups = []
        for rule in self._click_rules:
            matched = self._match(rule, click_text)
            if matched is not None:
                popups.append(self._popup(rule, ts, matched))
        return popups

    def _on_state_change(self, ts: str) -> list[Popup]:
        popups = []
        for rule in self._state_rules:
            matched = self._match(rule, click_text=None)
            if matched is not None and matched != self._last_match.get(rule.id):
                popups.append(self._popup(rule, ts, matched))
            self._last_match[rule.id] = matched
        return popups

    def _match(self, rule: Rule, click_text: str | None) -> dict[str, str] | None:
        """The text each condition matched, or None if any condition fails."""
        current = {
            "click": click_text,
            "process": self._process,
            "window_title": self._window_title,
            "clipboard": self._clipboard,
        }
        matched = {}
        for name, pattern in rule.conditions.items():
            candidates = self._screen.texts() if name == "ocr" else [current[name]]
            hit = next((t for t in candidates if t is not None and matches(pattern, t)), None)
            if hit is None:
                return None
            matched[name] = hit
        return matched

    def _popup(self, rule: Rule, ts: str, matched: dict[str, str]) -> Popup:
        return Popup(
            employee=self._employee,
            rule=rule.id,
            ts=ts,
            title=fill(rule.popup.title, matched),
            body=fill(rule.popup.body, matched),
        )


def _is_new_left_click(data: dict) -> bool:
    """Whether a mouse event is a click that starts a new gesture.

    A right click opens a context menu, it does not act on the text. The 2nd
    and 3rd click of a double or triple click are recorded as "double" and
    "triple": they belong to the gesture the preceding "single" click
    started, and one gesture is one click.
    """
    return (
        data.get("event") == "click"
        and data.get("button") == "left"
        and data.get("click_count") == "single"
    )


def _text(value: str | None) -> str | None:
    # Window titles in the recordings can end with a space, copied text with a line break.
    return value.strip() if value is not None else None
