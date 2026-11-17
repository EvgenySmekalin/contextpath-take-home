"""Engine behaviour on small hand-made event sequences.

Each test reproduces one situation found in the real recordings.
"""

from agent.engine import Engine, Popup
from agent.rules import Rule
from agent.screen import Screen

Event = tuple[str, str, dict]  # kind, timestamp, the recorded row

RULES = [
    Rule.model_validate(rule)
    for rule in (
        [
            {
                "id": "forwarded",
                "when": {"click": "FW:*", "process": ["OUTLOOK.EXE", "olk.exe"]},
                "popup": {"title": "Forwarded", "body": "Opened: {click}"},
            },
            {
                "id": "deleted",
                "when": {
                    "click": "Delete",
                    "window_title": "*| Salesforce*",
                    "ocr": "Are you sure you want to delete*",
                },
                "popup": {"title": "Deleted", "body": "{window_title} / {ocr}"},
            },
            {
                "id": "invoice",
                "when": {"clipboard": "INV-*", "process": ["OUTLOOK.EXE", "olk.exe"]},
                "popup": {"title": "Invoice", "body": "You copied {clipboard}"},
            },
        ]
    )
]

# A primary display and a second one to the upper left of it, as in the recordings.
DISPLAYS = {0: (0, 0, 1920, 1080), 1: (-3840, -500, 3840, 2160)}


def ts(seconds: float) -> str:
    whole = int(seconds)
    millis = round((seconds - whole) * 1000)
    return f"2026-03-10T10:{whole // 60:02d}:{whole % 60:02d}.{millis:03d}Z"


def focus(at: float, process: str, title: str = "Inbox - Outlook") -> Event:
    data = {"event": "focus_change", "process_name": process, "window_title": title}
    return ("windows", ts(at), data)


def clipboard(at: float, text: str | None) -> Event:
    data = {"event": "clipboard_change", "clipboard_content_text": text}
    return ("clipboard", ts(at), data)


def ocr(
    at: float,
    blocks: list[tuple[str, list[int]]] | None = None,
    *,
    display: int = 0,
    resolution: tuple[int, int] = (1920, 1080),
    filename: str | None = None,
    same_as: str | None = None,
) -> Event:
    data = {
        "filename": same_as or filename or f"{at}.jpg",
        "display_id": display,
        "resolution": list(resolution),
        "ocr_text_blocks": [{"text": t, "bounding_box": box} for t, box in blocks or []],
    }
    if same_as:
        data["deduplicated_from"] = same_as
    return ("ocr", ts(at), data)


def click(at: float, x: int, y: int, *, count: str = "single", button: str = "left") -> Event:
    data = {
        "event": "click",
        "button": button,
        "mouse_x": x,
        "mouse_y": y,
        "click_count": count,
        # Deliberately misleading, like the real click events.
        "process_name": "msedgewebview2.exe",
        "window_title": "Chrome Legacy Window",
    }
    return ("mouse", ts(at), data)


def run(*events: Event) -> list[Popup]:
    engine = Engine(RULES, "emp-1", Screen(DISPLAYS))
    return [popup for event in events for popup in engine.feed(*event)]


FW = ("FW: Q3 plan", [100, 200, 300, 20])


def test_click_on_text_fires_with_event_time_and_matched_text():
    (popup,) = run(focus(1, "olk.exe"), ocr(2, [FW]), click(2.5, 150, 210))
    assert popup == Popup(
        employee="emp-1",
        rule="forwarded",
        ts=ts(2.5),
        title="Forwarded",
        body="Opened: FW: Q3 plan",
    )


def test_process_comes_from_the_focused_window_not_from_the_click():
    # The click says msedgewebview2.exe; the window in front decides.
    assert len(run(focus(1, "olk.exe"), ocr(2, [FW]), click(2.5, 150, 210))) == 1
    assert run(focus(1, "explorer.exe"), ocr(2, [FW]), click(2.5, 150, 210)) == []


def test_no_window_known_yet_means_window_conditions_fail():
    assert run(ocr(2, [FW]), click(2.5, 150, 210)) == []


def test_click_next_to_the_text_does_not_count():
    assert run(focus(1, "olk.exe"), ocr(2, [FW]), click(2.5, 150, 260)) == []


def test_click_outside_every_display_is_ignored():
    assert run(focus(1, "olk.exe"), ocr(2, [FW]), click(2.5, 5000, 5000)) == []


def test_right_click_is_not_a_click_on_the_text():
    assert run(focus(1, "olk.exe"), ocr(2, [FW]), click(2.5, 150, 210, button="right")) == []


def test_downscaled_snapshot_on_a_display_with_negative_origin():
    # Display 1 is 3840x2160 at (-3840, -500) but captured as 1920x1080, so a
    # block at snapshot pixel (100, 200) is at screen pixel (-3640, -100).
    snapshot = ocr(2, [FW], display=1, resolution=(1920, 1080))
    assert len(run(focus(1, "olk.exe"), snapshot, click(2.5, -3840 + 300, -500 + 420))) == 1
    # The same numbers without scaling would be a miss.
    assert run(focus(1, "olk.exe"), snapshot, click(2.5, -3840 + 900, -500 + 420)) == []


def test_smallest_box_wins_when_boxes_nest():
    blocks = [("Whole paragraph FW: x", [0, 0, 1000, 500]), FW]
    (popup,) = run(focus(1, "olk.exe"), ocr(2, blocks), click(2.5, 150, 210))
    assert popup.body == "Opened: FW: Q3 plan"


def test_deduplicated_row_has_the_text_of_the_row_it_points_to():
    events = [
        focus(1, "olk.exe"),
        ocr(2, [FW], filename="a.jpg"),
        ocr(3, [("Something else", [100, 200, 300, 20])], filename="b.jpg"),
        ocr(4, same_as="a.jpg"),  # not the previous row: the one before it
        click(4.5, 150, 210),
    ]
    assert len(run(*events)) == 1


def test_deduplicated_row_pointing_before_the_recording_is_unknown_text():
    events = [focus(1, "olk.exe"), ocr(2, [FW]), ocr(3, same_as="never-seen.jpg")]
    assert run(*events, click(3.5, 150, 210)) == []


def test_click_is_checked_against_the_screen_before_it():
    """Salesforce: the first Delete opens the dialog, only the second one confirms."""
    title = "00482913 | Case | Salesforce - Google Chrome"
    delete = ("Delete", [500, 500, 60, 20])
    sure = ("Are you sure you want to delete this case?", [300, 400, 400, 20])
    popups = run(
        focus(1, "chrome.exe", title),
        ocr(2, [delete]),
        click(2.8, 520, 510),  # dialog is not on screen yet
        ocr(3, [delete, sure]),
        click(3.4, 520, 510),
        ocr(4, []),
    )
    assert [p.ts for p in popups] == [ts(3.4)]
    assert popups[0].body == f"{title} / Are you sure you want to delete this case?"


def test_double_click_is_one_gesture():
    popups = run(
        focus(1, "olk.exe"),
        ocr(2, [FW]),
        click(2.50, 150, 210),
        click(2.66, 150, 210, count="double"),
        click(2.80, 150, 210, count="triple"),
    )
    assert [p.ts for p in popups] == [ts(2.5)]


def test_two_separate_clicks_are_two_popups():
    popups = run(focus(1, "olk.exe"), ocr(2, [FW]), click(2.5, 150, 210), click(3.5, 150, 210))
    assert len(popups) == 2


def test_rule_without_click_fires_when_it_becomes_true():
    """Copy an invoice number in Excel, then switch to Outlook."""
    popups = run(
        focus(1, "EXCEL.EXE"),
        clipboard(2, "INV-20417"),
        focus(9, "olk.exe"),
        focus(10, "olk.exe", "Another Outlook window"),  # still true: no repeat
    )
    assert [(p.ts, p.body) for p in popups] == [(ts(9), "You copied INV-20417")]


def test_rule_without_click_fires_again_after_it_was_false_or_changed():
    popups = run(
        clipboard(1, "INV-1"),
        focus(2, "olk.exe"),
        clipboard(3, "INV-2"),  # still true, different text
        focus(4, "EXCEL.EXE"),
        focus(5, "olk.exe"),  # became true again
    )
    assert [p.body for p in popups] == ["You copied INV-1", "You copied INV-2", "You copied INV-2"]


def test_overwritten_clipboard_does_not_fire():
    popups = run(
        focus(1, "chrome.exe"),
        clipboard(2, "INV-99120"),
        clipboard(3, "Thanks, will do"),
        focus(4, "olk.exe"),
    )
    assert popups == []


def test_non_text_clipboard_clears_the_text():
    assert run(clipboard(1, "INV-1"), clipboard(2, None), focus(3, "olk.exe")) == []


def test_other_event_kinds_are_accepted_and_ignored():
    typing = ("keystrokes", ts(1), {"keystroke": "A"})
    scroll = ("mouse_scroll", ts(1), {"event": "scroll"})
    assert run(typing, scroll) == []
