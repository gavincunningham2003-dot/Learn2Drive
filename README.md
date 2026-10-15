# Learn2Drive – driving-test practice assistant

Final year project, BSc in Computer Science (Infrastructure), Technological University Dublin, 2025.

Learn2Drive helps learner drivers practise for the Irish driving test without an instructor in the car.
An Android app mounted on the dashboard records the road ahead, the driver's face and the phone's
GPS/accelerometer during a practice drive. The recordings are uploaded to a small Python server that
analyses the drive with OpenCV and MediaPipe, stores the findings in PostgreSQL, and sends them back
to the app, which plots every event on a Google Map and colour-codes how well the driver handled it.

The full write-up is in [docs/Final_Year_Report.pdf](docs/Final_Year_Report.pdf) and the final
presentation in [docs/Final_Presentation.pptx](docs/Final_Presentation.pptx).

## What it detects

| Check | How | Result shown in the app |
|---|---|---|
| Turns | Bearing change computed from consecutive GPS fixes, circularly smoothed, merged when within 1 s | Marker at the turn location |
| Mirror / observation checks on turns | MediaPipe Face Mesh on the driver-facing video; counts head movements from centre to left and to right in the 15 s around each turn | Green (looked both ways twice or more), orange (once each way), red (missed a side) |
| Lane departures | MobileNet-SSD finds the car behind in the rear-facing video; if it drifts away from the frame centre for 2 s or more outside a turn window, a departure is logged | Blue marker |

## Architecture

```
┌──────────────── Android app (Java) ────────────────┐      ┌──────────────── Server (Python) ────────────────┐
│ StreamingActivity                                  │      │ tcp_server.py  :5001                             │
│   • records front + rear camera (Camera2)          │ TCP  │   receives the three files, then runs:           │
│   • logs accelerometer + GPS to sensor_data.csv    │─────▶│   sensordatacleanup → turndetect → Lanetest →    │
│   • uploads front_video.mp4, rear_video.mp4, csv   │      │   eyetrackingtest → incident_add  ──▶ PostgreSQL │
│ TrackProgressActivity                              │ TCP  │ sql_tcp.py  :9000                                │
│   • asks for GET_EVENTS, caches the JSON reply     │◀─────│   joins the tables and returns events as JSON    │
│   • plots colour-coded markers on Google Maps      │      │                                                  │
└────────────────────────────────────────────────────┘      └──────────────────────────────────────────────────┘
```

### Processing pipeline (`server/`)

| Step | Script | Input | Output |
|---|---|---|---|
| 1 | `sensordatacleanup.py` | `sensor_data.csv` | `gps_time_periods.csv` – one row per distinct GPS fix with its time span and average speed |
| 2 | `turndetect.py` | `gps_time_periods.csv` | `detected_turns.csv` – time, direction and angle of each turn |
| 3 | `Lanetest.py` | `rear_video.mp4`, `detected_turns.csv` | `departure_events.csv` – times the car left its lane |
| 4 | `eyetrackingtest.py` | `front_video.mp4`, `detected_turns.csv` | `turn_transitions.csv` – left/right look counts per turn |
| 5 | `incident_add.py` | the three CSVs above | PostgreSQL tables `detected_turns`, `departure_events`, `incidents` |

The two TCP services and the Android code use a tiny custom protocol rather than HTTP: the upload is
`writeUTF(filename)`, `writeLong(size)`, raw bytes; the event request is the line `GET_EVENTS` answered
with a 4-byte length prefix and a JSON array.

## Repository layout

```
server/        Python pipeline, TCP servers, MobileNet-SSD weights, PostgreSQL config, docker-compose.yaml
android/       Android Studio project (Java, Camera2, Google Maps SDK)
sample_data/   A real sensor log from a test drive so steps 1–2 can be run without a phone
database/      Earlier relational schema design from the interim stage (not used by the final pipeline)
docs/          Final report and presentation
```

## Running the server

Requirements: Python 3.10+, Docker, and a display (the video steps open OpenCV preview windows).

```bash
pip install -r requirements.txt
cd server
docker compose up -d          # PostgreSQL 13 on localhost:5432, user Learner, db Incidents
python tcp_server.py          # in one terminal – file receiver + pipeline runner
python sql_tcp.py             # in another – event API for the app
```

Database credentials default to the ones in `server/docker-compose.yaml`; override them with the
`PG_HOST`, `PG_PORT`, `PG_DB`, `PG_USER` and `PG_PASSWORD` environment variables.

### Trying the pipeline without a phone

Copy a `sensor_data.csv`, `front_video.mp4` and `rear_video.mp4` from a drive into `server/` and run
the five scripts in the order of the table above. The sample log in `sample_data/` lets you run the
first two steps straight away:

```bash
cp sample_data/sensor_data.csv server/
cd server
python sensordatacleanup.py
python turndetect.py
```

The test-drive videos are not committed because they are far larger than GitHub's file limit.

## Building the app

1. Open `android/` in Android Studio (compile SDK 34, min SDK 27).
2. Create `android/local.properties` if it does not exist and add your Google Maps key:
   `MAPS_API_KEY=your_key_here`. The secrets-gradle-plugin injects it into the manifest at build time,
   so the key never has to be committed.
3. Set `SERVER_IP` in `StreamingActivity.java` and `SERVER_HOST` in `TrackProgressActivity.java` to
   the LAN address of the machine running the Python servers. The phone and server must be on the
   same network.
4. Run on a real device: the app records both cameras at once, which emulators do not support.

In the app: **Practice Driving** → *Start Recording* → drive → *Stop Recording* → *Process driving
behaviour* (uploads and triggers the pipeline) → **Track Progress** shows the map. The last successful
response is cached so the map still works offline.

## Known limitations

- Front and rear camera IDs are assumed to be `1` and `0`; some devices order them differently.
- Lane position is judged from the following car's position in the rear view, so a departure can
  only be detected while there is a car behind.
- Turn timestamps are measured from the first *moving* GPS segment; if the car sits still at the start
  of the recording the turn times will be early relative to the video by that amount.
- Thresholds (turn angle, head-offset pixels, 2 s departure window) were tuned on one phone and one
  vehicle and are set as constants in the scripts.
- The custom TCP protocol has no authentication and is intended for a private LAN only.

## Tech stack

Java · Android Camera2 · Google Maps SDK · Python · pandas · NumPy · OpenCV (DNN module, MobileNet-SSD)
· MediaPipe Face Mesh · PostgreSQL · psycopg2 · Docker Compose
