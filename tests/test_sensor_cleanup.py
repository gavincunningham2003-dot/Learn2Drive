import pandas as pd
import pytest

from sensor_cleanup import process_sensor_data


def _write_log(path, rows):
    cols = ["offsetMs", "wallClockTimestamp", "accX", "accY", "accZ", "speed", "latitude", "longitude"]
    pd.DataFrame(rows, columns=cols).to_csv(path, index=False)


def test_rows_sharing_a_gps_fix_collapse_into_one_segment(tmp_path):
    src, out = tmp_path / "sensor_data.csv", tmp_path / "gps_time_periods.csv"
    _write_log(src, [
        [0,   "t0", 0, 9.8, 0, 2.0, 53.0, -6.0],
        [20,  "t1", 0, 9.8, 0, 4.0, 53.0, -6.0],   # same fix as the row above
        [40,  "t2", 0, 9.8, 0, 6.0, 53.1, -6.0],   # new fix
        [60,  "t3", 0, 9.8, 0, 6.0, 53.1, -6.0],
        [80,  "t4", 0, 9.8, 0, 1.0, 53.1, -6.1],   # new fix
    ])

    process_sensor_data(str(src), str(out))
    summary = pd.read_csv(out)

    assert len(summary) == 3
    assert list(summary["start_offsetMs"]) == [0, 40, 80]
    assert list(summary["end_offsetMs"]) == [20, 60, 80]
    assert summary.loc[0, "avg_speed_mps"] == pytest.approx(3.0)
    assert summary.loc[0, "avg_speed_kph"] == pytest.approx(3.0 * 3.6)


def test_tiny_coordinate_noise_does_not_split_a_segment(tmp_path):
    src, out = tmp_path / "sensor_data.csv", tmp_path / "gps_time_periods.csv"
    _write_log(src, [
        [0,  "t0", 0, 9.8, 0, 1.0, 53.0, -6.0],
        [20, "t1", 0, 9.8, 0, 1.0, 53.0 + 1e-9, -6.0],   # below the 1e-7 tolerance
    ])

    process_sensor_data(str(src), str(out), tol=1e-7)

    assert len(pd.read_csv(out)) == 1
