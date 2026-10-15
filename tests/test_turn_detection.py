import pandas as pd
import pytest

from turn_detection import calculate_bearing, detect_turns, merge_events


# ---------------------------------------------------------------- calculate_bearing

@pytest.mark.parametrize(
    "lat2, lon2, expected",
    [
        (1.0, 0.0, 0.0),     # due north
        (0.0, 1.0, 90.0),    # due east
        (-1.0, 0.0, 180.0),  # due south
        (0.0, -1.0, 270.0),  # due west
    ],
)
def test_bearing_cardinal_directions(lat2, lon2, expected):
    assert calculate_bearing(0.0, 0.0, lat2, lon2) == pytest.approx(expected, abs=1e-6)


def test_bearing_is_always_in_0_360():
    for lat2, lon2 in [(1, 1), (-1, 1), (-1, -1), (1, -1)]:
        assert 0.0 <= calculate_bearing(0.0, 0.0, lat2, lon2) < 360.0


# ---------------------------------------------------------------- detect_turns

def _track(points, speed=5.0, step_ms=1000):
    """Build a gps_time_periods-style frame from (lat, lon) points one second apart."""
    return pd.DataFrame({
        "start_offsetMs": [i * step_ms for i in range(len(points))],
        "latitude": [p[0] for p in points],
        "longitude": [p[1] for p in points],
        "avg_speed_mps": [speed] * len(points),
    })


def test_right_angle_turn_is_detected_as_right():
    # drive north for five fixes, then east for five fixes
    north = [(0.001 * i, 0.0) for i in range(5)]
    east = [(0.004, 0.001 * i) for i in range(1, 6)]
    events = detect_turns(_track(north + east), speed_threshold=0.1, turn_threshold=30, smoothing_window=1)

    assert len(events) == 1
    assert events[0]["turn_type"] == "right"
    assert events[0]["turn_angle"] == pytest.approx(90.0, abs=0.5)


def test_left_turn_has_negative_angle():
    north = [(0.001 * i, 0.0) for i in range(5)]
    west = [(0.004, -0.001 * i) for i in range(1, 6)]
    events = detect_turns(_track(north + west), speed_threshold=0.1, turn_threshold=30, smoothing_window=1)

    assert len(events) == 1
    assert events[0]["turn_type"] == "left"
    assert events[0]["turn_angle"] == pytest.approx(-90.0, abs=0.5)


def test_straight_line_produces_no_turns():
    straight = [(0.001 * i, 0.0) for i in range(10)]
    assert detect_turns(_track(straight), speed_threshold=0.1, turn_threshold=30) == []


def test_stationary_fixes_are_ignored():
    # every fix is below the speed threshold, so there is nothing to analyse
    df = _track([(0.0, 0.0), (0.001, 0.0), (0.002, 0.001)], speed=0.0)
    assert detect_turns(df, speed_threshold=0.1) == []


def test_turn_times_are_relative_to_first_moving_fix():
    north = [(0.001 * i, 0.0) for i in range(5)]
    east = [(0.004, 0.001 * i) for i in range(1, 6)]
    df = _track(north + east)
    df["start_offsetMs"] += 50_000           # the recording started 50 s before the first fix

    events = detect_turns(df, speed_threshold=0.1, turn_threshold=30, smoothing_window=1)

    assert 0 <= events[0]["video_time_offset"] < 10_000


# ---------------------------------------------------------------- merge_events

def test_merge_events_groups_nearby_detections():
    events = [
        {"video_time_offset": 100, "turn_type": "right", "turn_angle": 20.0},
        {"video_time_offset": 500, "turn_type": "right", "turn_angle": 40.0},
        {"video_time_offset": 3000, "turn_type": "left", "turn_angle": -25.0},
    ]
    merged = merge_events(events, merge_threshold_ms=1000)

    assert len(merged) == 2
    assert merged[0] == {"video_time_offset": 300.0, "turn_type": "right", "turn_angle": 30.0}
    assert merged[1]["turn_type"] == "left"


def test_merge_events_sorts_before_merging():
    events = [
        {"video_time_offset": 3000, "turn_type": "left", "turn_angle": -25.0},
        {"video_time_offset": 100, "turn_type": "right", "turn_angle": 20.0},
    ]
    merged = merge_events(events, merge_threshold_ms=1000)
    assert [e["video_time_offset"] for e in merged] == [100.0, 3000.0]


def test_merge_events_empty_input():
    assert merge_events([]) == []
