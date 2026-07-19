"""Published transcript fetch (show-notes links) — free STT workaround."""

from __future__ import annotations

from backend.services.published_transcript_service import (
    extract_transcript_urls,
    html_to_transcript_text,
)


def test_extract_lex_transcript_href():
    desc = (
        '<p><b>Transcript:</b><br />\n'
        '<a href="https://lexfridman.com/anthony-kaldellis-transcript">'
        "https://lexfridman.com/anthony-kaldellis-transcript</a></p>"
    )
    urls = extract_transcript_urls(desc)
    assert urls == ["https://lexfridman.com/anthony-kaldellis-transcript"]


def test_extract_ignores_non_transcript_links():
    desc = '<a href="https://lexfridman.com/sponsors/ep498-sc">sponsor</a>'
    assert extract_transcript_urls(desc) == []


def test_html_to_transcript_from_entry_content():
    html = """
    <html><body>
      <nav>Skip me</nav>
      <article class="post">
        <div class="entry-content">
          <p>Lex Fridman(00:00:00) Hello and welcome.</p>
          <p>Guest(00:00:05) Thanks for having me on the show today.</p>
        </div>
      </article>
      <script>evil()</script>
    </body></html>
    """
    text = html_to_transcript_text(html)
    assert "Hello and welcome" in text
    assert "Thanks for having me" in text
    assert "evil" not in text
    assert "Skip me" not in text
