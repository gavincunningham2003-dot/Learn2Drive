#!/usr/bin/env python3
"""Run the full Learn2Drive analysis pipeline on one driving session.

Usage:
    python run_pipeline.py [session_dir] [--skip-db]

session_dir must contain sensor_data.csv, front_video.mp4 and rear_video.mp4 (default: the
current directory). Each step writes its CSV next to the inputs:

    1. sensor_cleanup   sensor_data.csv                 -> gps_time_periods.csv
    2. turn_detection   gps_time_periods.csv            -> detected_turns.csv
    3. lane_departure   rear_video.mp4 + detected_turns -> departure_events.csv
    4. mirror_checks    front_video.mp4 + detected_turns -> turn_transitions.csv
    5. store_incidents  the three CSVs                  -> PostgreSQL

Pass --skip-db to stop after step 4, e.g. when exploring the detectors without a database.
"""
import argparse
import importlib
import os
import sys
import time

SERVER_DIR = os.path.dirname(os.path.abspath(__file__))

# (module name, function to call) in execution order
STEPS = [
    ("sensor_cleanup", "process_sensor_data"),
    ("turn_detection", "main"),
    ("lane_departure", "main"),
    ("mirror_checks", "main"),
    ("store_incidents", "main"),
]


def run(session_dir, skip_db=False):
    """Run every step inside session_dir; return True if all of them succeeded."""
    sys.path.insert(0, SERVER_DIR)   # the step modules live next to this file
    os.chdir(session_dir)            # the steps read and write files relative to the cwd

    steps = STEPS[:-1] if skip_db else STEPS
    for number, (module_name, func_name) in enumerate(steps, start=1):
        print(f"\n=== step {number}/{len(steps)}: {module_name} ===")
        started = time.time()
        try:
            module = importlib.import_module(module_name)
            getattr(module, func_name)()
        except SystemExit as exc:            # the steps call sys.exit() on fatal input problems
            if exc.code not in (None, 0):
                print(f"step {module_name} exited with {exc.code}", file=sys.stderr)
                return False
        except Exception as exc:             # noqa: BLE001 - report and stop, whatever went wrong
            print(f"step {module_name} failed: {exc!r}", file=sys.stderr)
            return False
        print(f"=== {module_name} done in {time.time() - started:.1f}s ===")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("session_dir", nargs="?", default=".", help="folder holding the session files")
    parser.add_argument("--skip-db", action="store_true", help="do not load results into PostgreSQL")
    args = parser.parse_args()

    for required in ("sensor_data.csv", "front_video.mp4", "rear_video.mp4"):
        if not os.path.exists(os.path.join(args.session_dir, required)):
            sys.exit(f"missing {required} in {os.path.abspath(args.session_dir)}")

    sys.exit(0 if run(args.session_dir, skip_db=args.skip_db) else 1)


if __name__ == "__main__":
    main()
