# Sample data

`sensor_data.csv` is the accelerometer and GPS log from one real test drive, exactly as written by the
Android app (one row per accelerometer sample, roughly 50 per second).

| Column | Meaning |
|---|---|
| `offsetMs` | Milliseconds since the front-camera recording started |
| `wallClockTimestamp` | Phone wall-clock time of the sample |
| `accX`, `accY`, `accZ` | Accelerometer readings in m/s² |
| `speed` | GPS speed in m/s |
| `latitude`, `longitude` | Last GPS fix |

The matching `front_video.mp4` and `rear_video.mp4` are not committed (about 150 MB each, above
GitHub's file size limit), so only the first two pipeline steps can be run from this folder.

Note: the first 54 rows of this file were logged before the video clock started and carry stale
offsets (around 51 s). The app has since been fixed to skip those rows; they are left here so the
file matches the data used in the report.
