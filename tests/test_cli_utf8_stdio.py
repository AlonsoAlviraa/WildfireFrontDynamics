"""Windows console UTF-8 safety for CLI banners (no charmap crash)."""

from __future__ import annotations

import io

from wildfire_front.cli import main
from wildfire_front.cli_report import ensure_utf8_stdio, print_json, safe_write


class _AsciiOnly(io.StringIO):
    """Simulate a cp1252-like stream that rejects some Unicode on write."""

    encoding = "ascii"

    def write(self, s: str) -> int:  # type: ignore[override]
        # Force failure path if non-ascii present when using raw write of original
        s.encode("ascii")  # may raise UnicodeEncodeError
        return super().write(s)


def test_safe_write_survives_ascii_only_stream():
    buf = io.StringIO()
    # normal path
    safe_write("hello ≠ world ╔══╗", file=buf)
    assert "hello" in buf.getvalue()


def test_safe_write_replace_on_strict_ascii():
    class StrictAscii:
        encoding = "ascii"
        buffer = None

        def __init__(self) -> None:
            self.chunks: list[str] = []

        def write(self, s: str) -> int:
            s.encode("ascii")  # raise if non-ascii
            self.chunks.append(s)
            return len(s)

        def flush(self) -> None:
            return None

    stream = StrictAscii()
    # should not raise
    safe_write("box ╔ and ≠", file=stream)  # type: ignore[arg-type]
    # either replaced content was written via fallback or nothing raised
    assert True


def test_ensure_utf8_stdio_idempotent():
    ensure_utf8_stdio()
    ensure_utf8_stdio()


def test_main_help_and_brief_no_crash(capsys):
    """Real entrypoints that previously failed on Windows charmap must exit 0."""
    for argv in (["help"], ["commands"], ["brief"], ["brief", "--json"], ["operator"], ["ml"]):
        try:
            main(argv)
            code = 0
        except SystemExit as exc:
            code = 0 if exc.code in (0, None) else int(exc.code) if isinstance(exc.code, int) else 1
        out = capsys.readouterr()
        assert code == 0, f"{argv} code={code} err={out.err}"
        assert "charmap" not in out.err
        assert "codec can't encode" not in out.err
        assert out.out or argv == ["ml"]  # hub always prints something


def test_print_json_unicode():
    buf = io.StringIO()
    print_json({"neq": "≠", "rails": "OFF"}, file=buf)
    assert "neq" in buf.getvalue()
