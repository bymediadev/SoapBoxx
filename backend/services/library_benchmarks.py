"""Library-wide metric distributions for coaching benchmarks (V1, no LLM)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.models import EpisodeFeatures

MIN_SAMPLES = 3


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


def load_library_benchmarks(db: Session) -> LibraryBenchmarks:
    rows = db.execute(select(EpisodeFeatures)).scalars().all()
    return LibraryBenchmarks(
        n_measured=len(rows),
        hook_seconds=[float(r.hook_length_seconds or 0) for r in rows],
        intro_seconds=[float(r.intro_length_seconds or 0) for r in rows],
        question_counts=[int(r.question_count or 0) for r in rows],
        speaking_turns=[int(r.speaking_turns or 0) for r in rows],
        guest_ratios=[float(r.host_guest_ratio or 0.5) for r in rows],
        topic_shifts=[int(r.topic_shift_count or 0) for r in rows],
    )


def _pct_higher_than(values: Sequence[float], current: float) -> Optional[int]:
    """Share of library with a strictly higher value than ``current``."""
    if len(values) < MIN_SAMPLES:
        return None
    return round(100 * sum(1 for v in values if v > current) / len(values))


def _pct_lower_than(values: Sequence[float], current: float) -> Optional[int]:
    if len(values) < MIN_SAMPLES:
        return None
    return round(100 * sum(1 for v in values if v < current) / len(values))


def benchmark_hook(seconds: float, lib: LibraryBenchmarks) -> Optional[str]:
    pct = _pct_higher_than(lib.hook_seconds, seconds)
    if pct is None:
        return None
    n = lib.n_measured
    if pct >= 55:
        return f"Faster opening than {pct}% of episodes measured in your library ({n} episodes)"
    if pct <= 35:
        return f"Longer opening than most measured episodes in your library ({n} episodes)"
    return f"Near the middle of measured openings in your library ({n} episodes)"


def benchmark_intro(seconds: float, lib: LibraryBenchmarks) -> Optional[str]:
    pct = _pct_higher_than(lib.intro_seconds, seconds)
    if pct is None:
        return None
    n = lib.n_measured
    if pct >= 55:
        return f"Story or guest enters earlier than {pct}% of measured episodes ({n} episodes)"
    if pct <= 35:
        return f"Longer intro block than most measured episodes ({n} episodes)"
    return f"Intro length near the library median ({n} episodes)"


def benchmark_questions(count: int, lib: LibraryBenchmarks) -> Optional[str]:
    pct = _pct_higher_than([float(x) for x in lib.question_counts], float(count))
    if pct is None:
        return None
    n = lib.n_measured
    if pct >= 60:
        return f"Fewer questions than {pct}% of measured episodes ({n} episodes)"
    if pct <= 30:
        return f"Higher question density than most measured episodes ({n} episodes)"
    return f"Question count near the library middle ({n} episodes)"


def benchmark_turns(count: int, lib: LibraryBenchmarks) -> Optional[str]:
    pct = _pct_higher_than([float(x) for x in lib.speaking_turns], float(count))
    if pct is None:
        return None
    n = lib.n_measured
    if pct >= 60:
        return f"Fewer speaking turns than {pct}% of measured episodes ({n} episodes)"
    if pct <= 30:
        return f"More turn-taking than most measured episodes ({n} episodes)"
    return f"Turn count near the library middle ({n} episodes)"


def library_comparison_bullets(
    *,
    hook: float,
    intro: float,
    questions: int,
    turns: int,
    ratio: float,
    lib: LibraryBenchmarks,
    narrative_led: bool,
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
    q_b = benchmark_questions(questions, lib)
    if q_b and "fewer" in q_b.lower():
        bullets.append(f"Questions: {q_b}")
    t_b = benchmark_turns(turns, lib)
    if t_b and "fewer" in t_b.lower():
        bullets.append(f"Speaking turns: {t_b}")
    g_b = benchmark_guest_ratio(ratio, lib)
    if g_b and "balanced" in g_b.lower():
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


def benchmark_guest_ratio(ratio: float, lib: LibraryBenchmarks) -> Optional[str]:
    if len(lib.guest_ratios) < MIN_SAMPLES:
        return None
    n = lib.n_measured
    if 0.42 <= ratio <= 0.58:
        return f"Balanced guest/host share among measured episodes ({n} episodes)"
    if ratio < 0.42:
        return f"Guest talk share is lower than most measured episodes ({n} episodes)"
    return f"Guest talk share is higher than most measured episodes ({n} episodes)"
