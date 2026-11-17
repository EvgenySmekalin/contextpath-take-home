import pytest

from agent.rules import Rule, fill, matches


def rule(**overrides):
    base = {
        "id": "r1",
        "when": {"click": "FW:*"},
        "popup": {"title": "T", "body": "{click}"},
    }
    return {**base, **overrides}


class TestMatches:
    def test_star_matches_any_characters_including_none(self):
        assert matches("FW:*", "FW: hello")
        assert matches("FW:*", "FW:")
        assert matches("*urgent*", "very urgent thing")

    def test_must_match_the_whole_text(self):
        assert not matches("Delete", "Delete Case")
        assert not matches("FW:*", "Re: FW: hello")

    def test_case_does_not_matter(self):
        assert matches("*urgent*", "FW: URGENT - pay")
        assert matches("OUTLOOK.EXE", "outlook.exe")

    def test_everything_but_the_star_is_literal(self):
        assert matches("*| Salesforce*", "00482913 | Case | Salesforce - Google Chrome")
        assert matches("[OPS-1]*", "[OPS-1] title")
        assert not matches("OUTLOOK.EXE", "OUTLOOKxEXE")
        assert not matches("a?c", "abc")

    def test_star_spans_line_breaks(self):
        assert matches("INV-*", "INV-1\r\nINV-2")

    def test_list_matches_if_any_pattern_matches(self):
        assert matches(["OUTLOOK.EXE", "olk.exe"], "olk.exe")
        assert not matches(["OUTLOOK.EXE", "olk.exe"], "chrome.exe")


class TestRule:
    def test_null_and_missing_conditions_are_ignored(self):
        parsed = Rule.model_validate(rule(when={"click": "x", "process": None, "ocr": None}))
        assert parsed.conditions == {"click": "x"}

    @pytest.mark.parametrize(
        "bad",
        [
            rule(when={"clik": "x"}),  # a typo would otherwise be silently ignored
            rule(when={"click": None}),  # no conditions at all
            rule(when={"click": 5}),
            rule(popup=None),
            {"when": {"click": "x"}, "popup": {}},  # no id
        ],
    )
    def test_rejects_invalid_rules(self, bad):
        with pytest.raises(ValueError):
            Rule.model_validate(bad)


def test_fill_replaces_known_placeholders_and_leaves_other_braces_alone():
    assert fill("{click} {} { x } {other}", {"click": "FW: a {b}"}) == "FW: a {b} {} { x } {other}"
