"""Library-wide metric distributions for coaching benchmarks (V1, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import EpisodeFeatures
from backend.services.measurement_versions import filter_comparable_rows, stamp_for_row

MIN_SAMPLES = 3
# Below this count, use "most / few" language — not hard percentiles.
PCT_PRECISION_MIN = 10


@dataclass(frozen=True)
class LibraryBenchmarks:
    n_measured: int
    hook_seconds: List[float]
    intro_seconds: List[float]
    question_counts: List[int]
    speaking_turns: List[int]
    guest_ratios: List[float]
    topic_shifts: List[int]

    @property
    def avg_questions(self) -> float:
        if not self.question_counts:
            return 0.0
        return sum(self.question_counts) / len(self.question_counts)

    @property
    def avg_turns(self) -> float:
        if not self.speaking_turns:
            return 0.0
        return sum(self.speaking_turns) / len(self.speaking_turns)


def library_from_rows(rows: Sequence[EpisodeFeatures]) -> LibraryBenchmarks:
    return LibraryBenchmarks(
        n_measured=len(rows),
        hook_seconds=[float(r.hook_length_seconds or 0) for r in rows],
        intro_seconds=[float(r.intro_length_seconds or 0) for r in rows],
        question_counts=[int(r.question_count or 0) for r in rows],
        speaking_turns=[int(r.speaking_turns or 0) for r in rows],
        guest_ratios=[float(r.host_guest_ratio or 0.5) for r in rows],
        topic_shifts=[int(r.topic_shift_count or 0) for r in rows],
    )


def load_library_benchmarks(
    db: Session, *, anchor: Optional[EpisodeFeatures] = None
) -> tuple[LibraryBenchmarks, int]:
    rows = list(db.execute(select(EpisodeFeatures)).scalars().all())
    stamp = stamp_for_row(anchor)
    kept, excluded = filter_comparable_rows(rows, stamp)
    return library_from_rows(kept), excluded


def _pct_higher_than(values: Sequence[float], current: float) -> Optional[int]:
    """Share of library with a strictly higher value than ``current``."""
    if len(values) < MIN_SAMPLES:
        return None
    return round(100 * sum(1 for v in values if v > current) / len(values))


def _pct_lower_than(values: Sequence[float], current: float) -> Optional[int]:
    if len(values) < MIN_SAMPLES:
        return None
    return round(100 * sum(1 for v in values if v < current) / len(values))


def _library_ctx(n: int) -> str:
    word = "episode" if n == 1 else "episodes"
    return f"in your current library ({n} measured {word})"


def _compare_higher_is_faster(
    pct_more: int,
    n: int,
    *,
    fast_label: str,
    slow_label: str,
    mid_label: str,
) -> str:
    """``pct_more`` = share of library with a higher (slower) value than current."""
    ctx = _library_ctx(n)
    if n >= PCT_PRECISION_MIN:
        if pct_more >= 55:
            return f"{fast_label} than {pct_more}% of measured episodes {ctx}"
        if pct_more <= 35:
            return f"{slow_label} than most measured episodes {ctx}"
        return f"{mid_label} {ctx}"
    if pct_more >= 50:
        return f"{fast_label} than most episodes {ctx}"
    if pct_more <= 25:
        return f"{slow_label} than most episodes {ctx}"
    return f"{mid_label} {ctx}"


def _compare_higher_means_more(
    pct_more: int,
    n: int,
    *,
    more_label: str,
    fewer_label: str,
    mid_label: str,
) -> str:
    """``pct_more`` = share of library strictly above current (current is lower)."""
    ctx = _library_ctx(n)
    if n >= PCT_PRECISION_MIN:
        if pct_more >= 55:
            return f"{fewer_label} than {pct_more}% of measured episodes {ctx}"
        if pct_more <= 35:
            return f"{more_label} than most measured episodes {ctx}"
        return f"{mid_label} {ctx}"
    if pct_more >= 50:
        return f"{fewer_label} than most episodes {ctx}"
    if pct_more <= 25:
        return f"{more_label} than most episodes {ctx}"
    return f"{mid_label} {ctx}"


def benchmark_hook(seconds: float, lib: LibraryBenchmarks) -> Optional[str]:
    pct = _pct_higher_than(lib.hook_seconds, seconds)
    if pct is None:
        return None
    return _compare_higher_is_faster(
        pct,
        lib.n_measured,
        fast_label="Faster opening",
        slow_label="Longer opening",
        mid_label="Opening length near the middle of your library",
    )


def benchmark_intro(seconds: float, lib: LibraryBenchmarks) -> Optional[str]:
    pct = _pct_higher_than(lib.intro_seconds, seconds)
    if pct is None:
        return None
    return _compare_higher_is_faster(
        pct,
        lib.n_measured,
        fast_label="Story or guest enters earlier",
        slow_label="Longer intro block",
        mid_label="Intro length near the middle of your library",
    )


def benchmark_questions(
    count: int, lib: LibraryBenchmarks, *, rhetorical_heavy: bool = False
) -> Optional[str]:
    pct = _pct_higher_than([float(x) for x in lib.question_counts], float(count))
    if pct is None:
        return None
    label = _compare_higher_means_more(
        pct,
        lib.n_measured,
        more_label="Higher question density",
        fewer_label="Fewer questions",
        mid_label="Question count near the middle of your library",
    )
    if rhetorical_heavy and label:
        return f"{label} (may include rhetorical narration, not interview Q&A)"
    return label


def benchmark_turns(count: int, lib: LibraryBenchmarks) -> Optional[str]:
    values = [float(x) for x in lib.speaking_turns]
    current = float(count)
    pct_more = _pct_higher_than(values, current)
    pct_less = _pct_lower_than(values, current)
    if pct_more is None:
        return None
    n = lib.n_measured
    ctx = _library_ctx(n)

    if values and current >= max(values) and (pct_less or 0) >= 50:
        return (
            f"Turn count at the high end of your measured library ({int(current)}) — "
            f"handoffs can still read as long narrative blocks {ctx}"
        )

    if n >= PCT_PRECISION_MIN:
        if pct_more >= 55:
            return f"Longer uninterrupted segments than {pct_more}% of measured episodes {ctx}"
        if pct_less is not None and pct_less >= 55:
            return f"More frequent handoffs than {pct_less}% of measured episodes {ctx}"
        return f"Turn count near the middle {ctx}"

    if pct_more >= 50:
        return f"Longer uninterrupted segments than most episodes {ctx}"
    if pct_less is not None and pct_less >= 50:
        return f"More frequent handoffs than most episodes {ctx}"
    return f"Turn count near the middle {ctx}"


def benchmark_guest_ratio(
    ratio: float, lib: LibraryBenchmarks, *, turns: int = 0
) -> Optional[str]:
    if turns == 0:
        return "Speaker labels not detected — talk share unavailable"
    if len(lib.guest_ratios) < MIN_SAMPLES:
        return None
    ctx = _library_ctx(lib.n_measured)
    if 0.42 <= ratio <= 0.58:
        return f"Balanced guest/host share among measured episodes {ctx}"
    if ratio < 0.42:
        return f"Guest talk share is lower than most measured episodes {ctx}"
    return f"Guest talk share is higher than most measured episodes {ctx}"


def library_comparison_bullets(
    *,
    hook: float,
    intro: float,
    questions: int,
    turns: int,
    ratio: float,
    lib: LibraryBenchmarks,
    narrative_led: bool,
    rhetorical_heavy: bool = False,
    has_diarization: bool = True,
) -> List[str]:
    """Game-film lines: this episode vs measured library (no quality judgment)."""
    if lib.n_measured < MIN_SAMPLES:
        return [
            "Compared with your library: add more measured episodes to unlock "
            "side-by-side structural comparisons."
        ]

    bullets: List[str] = []
    hook_b = benchmark_hook(hook, lib)
    if hook_b and "faster" in hook_b.lower():
        bullets.append(f"Opening: {hook_b}")
    q_b = benchmark_questions(questions, lib, rhetorical_heavy=rhetorical_heavy)
    if q_b and "fewer" in q_b.lower() and not rhetorical_heavy:
        bullets.append(f"Questions: {q_b}")
    t_b = benchmark_turns(turns, lib)
    if t_b and ("longer" in t_b.lower() or "high end" in t_b.lower()):
        bullets.append(f"Speaking turns: {t_b}")
    g_b = benchmark_guest_ratio(ratio, lib, turns=turns if has_diarization else 0)
    if g_b and "balanced" in g_b.lower() and has_diarization:
        bullets.append(f"Talk share: {g_b}")

    if narrative_led and bullets:
        bullets.append(
            "Shape: sits in the narrative-led band in your library "
            "(sparse questions, longer segments)."
        )
    elif not bullets:
        bullets.append(
            f"Compared with {lib.n_measured} measured episodes in your library, "
            "this episode sits near the middle on opening length, questions, and turns."
        )
    return bullets[:5]
