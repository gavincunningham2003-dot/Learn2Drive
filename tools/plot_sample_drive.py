#!/usr/bin/env python3
"""Render the sample drive's GPS track with the turns the pipeline detects on it.

    python tools/plot_sample_drive.py            # writes docs/sample_drive_turns.png

Runs steps 1 and 2 of the pipeline (sensor_cleanup, turn_detection) on sample_data/sensor_data.csv
in a temporary folder and plots the result, so the figure in the README is reproducible.
"""
import math
import os
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "server"))

from sensor_cleanup import process_sensor_data   # noqa: E402
from turn_detection import detect_turns, merge_events   # noqa: E402

# same parameters as turn_detection.main()
SPEED_THRESHOLD, TURN_THRESHOLD, SMOOTHING_WINDOW = 0.01, 20, 2


def main():
    sample = os.path.join(ROOT, "sample_data", "sensor_data.csv")
    out_png = os.path.join(ROOT, "docs", "sample_drive_turns.png")

    with tempfile.TemporaryDirectory() as tmp:
        segments_csv = os.path.join(tmp, "gps_time_periods.csv")
        process_sensor_data(sample, segments_csv)
        gps = pd.read_csv(segments_csv)

    moving = gps[gps["avg_speed_mps"] > SPEED_THRESHOLD].reset_index(drop=True)
    events = merge_events(detect_turns(gps, SPEED_THRESHOLD, TURN_THRESHOLD, SMOOTHING_WINDOW))

    # map each event's video-relative time back to the nearest moving GPS fix
    video_start = moving.loc[0, "start_offsetMs"]
    for ev in events:
        absolute_ms = ev["video_time_offset"] + video_start
        idx = (moving["start_offsetMs"] - absolute_ms).abs().idxmin()
        ev["lat"], ev["lon"] = moving.loc[idx, "latitude"], moving.loc[idx, "longitude"]

    # plot in metres east/north of the start point: equal axes and readable tick labels
    lat0, lon0 = moving.loc[0, "latitude"], moving.loc[0, "longitude"]
    m_per_deg_lat = 111_320.0
    m_per_deg_lon = 111_320.0 * math.cos(math.radians(lat0))
    east = lambda lon: (lon - lon0) * m_per_deg_lon   # noqa: E731
    north = lambda lat: (lat - lat0) * m_per_deg_lat  # noqa: E731

    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.plot(east(moving["longitude"]), north(moving["latitude"]), color="#555", linewidth=1.5, label="GPS track")
    ax.scatter(0, 0, marker="o", s=90, color="#2a9d8f", zorder=4, label="start")
    ax.scatter(east(moving["longitude"].iloc[-1]), north(moving["latitude"].iloc[-1]), marker="s", s=90,
               color="#264653", zorder=4, label="end")
    for kind, colour, marker in (("left", "#1d6fd1", "<"), ("right", "#e76f51", ">")):
        pts = [e for e in events if e["turn_type"] == kind]
        if pts:
            ax.scatter([east(e["lon"]) for e in pts], [north(e["lat"]) for e in pts], marker=marker, s=140,
                       color=colour, edgecolor="black", zorder=5, label=f"{kind} turn ({len(pts)})")

    ax.set_aspect("equal")
    ax.set_xlabel("metres east of start")
    ax.set_ylabel("metres north of start")
    ax.set_title("Sample drive: GPS track with detected turns")
    ax.grid(alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(out_png, dpi=150)
    print(f"wrote {out_png} ({len(events)} turns)")


if __name__ == "__main__":
    main()
