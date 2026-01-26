from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable, Dict, List, Optional, Tuple

STATE_SCORE = {"R": 0, "Y": 1, "G": 2}

@dataclass(frozen=True)
class TrendLabels:
    direction: str                 # Improve / Stable / Degrade / Unknown
    hit_red: bool                  # True if any R in window (excluding first if you want)
    worse_than_start: bool         # True if min(window) < start
    better_than_start: bool        # True if max(window) > start
    dip_and_recover: bool          # worse_than_start AND direction==Improve
    steady_degrade: bool           # monotonic non-increasing and at least one drop
    steady_improve: bool           # monotonic non-decreasing and at least one rise
    volatility: int                # number of state changes in the window
    start: Optional[str]
    end: Optional[str]
    window_len: int

def _to_scores(states: Iterable[str]) -> List[Optional[int]]:
    out: List[Optional[int]] = []
    for s in states:
        if s is None:
            out.append(None)
        else:
            s2 = str(s).strip().upper()
            out.append(STATE_SCORE.get(s2))
    return out

def label_trend_window(
    window_states: List[str],
    *,
    include_start_in_events: bool = True
) -> TrendLabels:
    """
    Labels a state window W = [S_t, S_{t+1}, ..., S_{t+H}] where each element is 'G','Y','R'.
    
    include_start_in_events:
        - True: event checks (hit_red / min/max) include S_t
        - False: event checks look only at future steps S_{t+1:t+H}
    """
    if not window_states:
        return TrendLabels(
            direction="Unknown", hit_red=False, worse_than_start=False, better_than_start=False,
            dip_and_recover=False, steady_degrade=False, steady_improve=False, volatility=0,
            start=None, end=None, window_len=0
        )

    # Clean + score
    cleaned = [str(s).strip().upper() for s in window_states]
    scores = _to_scores(cleaned)

    start_state = cleaned[0] if cleaned[0] in STATE_SCORE else None
    end_state = cleaned[-1] if cleaned[-1] in STATE_SCORE else None
    start_score = scores[0]
    end_score = scores[-1]

    # If we have unknowns, we can still compute some things using known parts,
    # but direction needs start and end.
    if start_score is None or end_score is None:
        direction = "Unknown"
    else:
        if end_score > start_score:
            direction = "Improve"
        elif end_score < start_score:
            direction = "Degrade"
        else:
            direction = "Stable"

    # Event range: include start or only future
    event_scores = scores if include_start_in_events else scores[1:]
    event_known = [v for v in event_scores if v is not None]

    hit_red = any((v == 0) for v in event_known) if event_known else False
    worse_than_start = False
    better_than_start = False
    if start_score is not None and event_known:
        worse_than_start = min(event_known) < start_score
        better_than_start = max(event_known) > start_score

    dip_and_recover = worse_than_start and (direction == "Improve")

    # Volatility: count state changes (ignore unknowns)
    volatility = 0
    prev = None
    for v in scores:
        if v is None:
            continue
        if prev is None:
            prev = v
            continue
        if v != prev:
            volatility += 1
        prev = v

    # Monotonic trends (steady)
    known_seq = [v for v in scores if v is not None]
    steady_degrade = False
    steady_improve = False
    if len(known_seq) >= 2:
        non_increasing = all(known_seq[i] <= known_seq[i-1] for i in range(1, len(known_seq)))
        non_decreasing = all(known_seq[i] >= known_seq[i-1] for i in range(1, len(known_seq)))
        any_drop = any(known_seq[i] < known_seq[i-1] for i in range(1, len(known_seq)))
        any_rise = any(known_seq[i] > known_seq[i-1] for i in range(1, len(known_seq)))
        steady_degrade = non_increasing and any_drop
        steady_improve = non_decreasing and any_rise

    return TrendLabels(
        direction=direction,
        hit_red=hit_red,
        worse_than_start=worse_than_start,
        better_than_start=better_than_start,
        dip_and_recover=dip_and_recover,
        steady_degrade=steady_degrade,
        steady_improve=steady_improve,
        volatility=volatility,
        start=start_state,
        end=end_state,
        window_len=len(window_states)
    )

w = ["Y", "R", "Y", "G"]
labels = label_trend_window(w, include_start_in_events=False)
print(labels)