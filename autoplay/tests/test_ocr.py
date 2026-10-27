import pytest

pytest.importorskip("Vision")

from autoplay import ocr  # noqa: E402
from fakeboard import render  # noqa: E402

BOARDS = [
    ("GSYNROASRKNAEEVG", "Helvetica-Bold"),
    ("QUIZJOCKEYWAXHMP", "Avenir-Black"),
    ("ITCUEHEFICFTSALL", "ArialRoundedMTBold"),
]


@pytest.mark.parametrize("letters, font", BOARDS)
def test_reads_letters_positions_and_clock(tmp_path, letters, font):
    centres = render(letters, tmp_path / "board.png", font=font, timer="01:18")
    reading = ocr.read(ocr.load(tmp_path / "board.png"))
    assert reading.letters == letters
    assert reading.seconds_left == 78
    pitch = reading.grid.dx
    for (x, y), (tx, ty) in zip(reading.grid.centres(), centres):
        assert abs(x - tx) < 0.05 * pitch and abs(y - ty) < 0.05 * pitch


def test_rejects_the_how_to_play_card(tmp_path):
    render("CATDWOFOIRDGNOAS", tmp_path / "card.png", timer="How to play:")
    assert ocr.read(ocr.load(tmp_path / "card.png")) is None


def test_rejects_a_small_board(tmp_path):
    # Like the sample board on the start card or a game bubble in the chat.
    render("CATDWOFOIRDGNOAS", tmp_path / "small.png", pitch=0.09)
    assert ocr.read(ocr.load(tmp_path / "small.png")) is None


def test_rejects_a_screen_without_a_board(tmp_path):
    render("", tmp_path / "empty.png")
    assert ocr.read(ocr.load(tmp_path / "empty.png")) is None


@pytest.mark.parametrize("text, seconds", [("01:18", 78), ("00:03", 3), ("01:20", 80),
                                           ("12:28", None), ("3:18", None), ("WORDS: 0", None)])
def test_game_clock(text, seconds):
    assert ocr.seconds_left([(text, (0, 0, 10, 10))]) == seconds


@pytest.mark.parametrize("char, expected", [("A", "A"), ("c", "C"), ("0", "O"), ("1", "I"), ("l", "I"),
                                            ("|", "I"), ("e", None), ("7", None), ("?", None)])
def test_letter_cleanup(char, expected):
    assert ocr.letter(char) == expected
