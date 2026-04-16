"""youtube_subtitles helpers (no network)."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from youtube_subtitles import (  # noqa: E402
    parse_youtube_video_id,
    resolve_existing_en_vtt,
)


class TestYoutubeSubtitles(unittest.TestCase):
    def test_parse_id_plain(self) -> None:
        self.assertEqual(parse_youtube_video_id("DfTU5LA_kw8"), "DfTU5LA_kw8")

    def test_parse_id_watch_url(self) -> None:
        self.assertEqual(
            parse_youtube_video_id("https://www.youtube.com/watch?v=DfTU5LA_kw8"),
            "DfTU5LA_kw8",
        )

    def test_resolve_existing_exact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            d = Path(td)
            p = d / "abc.en.vtt"
            p.write_text("WEBVTT\n", encoding="utf-8")
            self.assertEqual(resolve_existing_en_vtt(d, "abc"), p)


if __name__ == "__main__":
    unittest.main()
