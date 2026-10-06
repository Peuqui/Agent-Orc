"""Kölner Phonetik: words that sound alike get the same digit code. Made for German; for names
from other languages it is only an approximation, but a spelling and its misspelling still end
up with the same code, which is all it is used for (see voice.py)."""

_VOWELS = "AEIJOUY"
_UMLAUTS = str.maketrans({"Ä": "A", "Ö": "O", "Ü": "U", "ß": "S"})
# Letters with one code regardless of their neighbours.
_FIXED = {"B": "1", "F": "3", "V": "3", "W": "3", "G": "4", "K": "4", "Q": "4", "L": "5"}
_FIXED |= {"M": "6", "N": "6", "R": "7", "S": "8", "Z": "8"}
_FIXED |= dict.fromkeys(_VOWELS, "0")
_HARD_C_AT_START = "AHKLOQRUX"
_HARD_C_INSIDE = "AHKOQUX"


def _code(letters: str, index: int) -> str:
    letter = letters[index]
    before = letters[index - 1] if index > 0 else ""
    after = letters[index + 1] if index + 1 < len(letters) else ""
    if letter in _FIXED:
        return _FIXED[letter]
    if letter == "H":
        return ""
    if letter == "P":
        return "3" if after == "H" else "1"
    if letter in "DT":
        return "8" if after in ("C", "S", "Z") else "2"
    if letter == "X":
        return "8" if before in ("C", "K", "Q") else "48"
    # C is the only one left.
    if index == 0:
        return "4" if after in _HARD_C_AT_START else "8"
    if before in ("S", "Z"):
        return "8"
    return "4" if after in _HARD_C_INSIDE else "8"


def cologne(text: str) -> str:
    """The digit code of a text; everything that is not a letter is left out."""
    letters = "".join(c for c in text.upper().translate(_UMLAUTS) if c.isalpha() and c.isascii())
    codes = "".join(_code(letters, index) for index in range(len(letters)))
    # The same digit twice in a row counts once; vowels (0) only count at the start.
    squeezed = "".join(c for index, c in enumerate(codes) if index == 0 or c != codes[index - 1])
    return squeezed[:1] + squeezed[1:].replace("0", "")
