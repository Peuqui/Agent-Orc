"""Kölner Phonetik against the examples of its description."""

import pytest

from agent_orc.phonetics import cologne


@pytest.mark.parametrize(
    ("text", "code"),
    [
        ("Müller-Lüdenscheidt", "65752682"),
        ("Wikipedia", "3412"),
        ("Breschnew", "17863"),
        ("Whisper", "3817"),
        ("Visper", "3817"),
    ],
)
def test_the_code_of_a_word(text: str, code: str) -> None:
    assert cologne(text) == code


def test_spellings_that_sound_alike_share_a_code() -> None:
    assert len({cologne(word) for word in ("Orc", "Org", "Ork")}) == 1
    assert cologne("Agent Orc") == cologne("Agent-Org")
