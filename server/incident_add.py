#!/usr/bin/env python3
import os
import pandas as pd
import psycopg2
import sys
from datetime import timedelta


# CSV file paths
DEPARTURES_FILE = "departure_events.csv"   
TURNS_FILE = "turn_transitions.csv"           
GPS_FILE = "gps_time_periods.csv"          

# PostgreSQL connection settings (defaults match docker-compose.yaml; override with environment variables)
PG_HOST = os.environ.get("PG_HOST", "localhost")
PG_PORT = int(os.environ.get("PG_PORT", "5432"))
PG_USER = os.environ.get("PG_USER", "Learner")
PG_PASSWORD = os.environ.get("PG_PASSWORD", "Cars2025")
PG_DB = os.environ.get("PG_DB", "Incidents")

# Time matching threshold for GPS
MAX_TIME_DELTA = timedelta(seconds=30)

def read_csv_or_empty(path, columns):
    """Load a CSV, or return an empty frame with the expected columns if the
    previous pipeline step produced no events (and therefore no file)."""
    try:
        return pd.read_csv(path)
    except FileNotFoundError:
        print(f"Note: '{path}' not found, treating as no events.")
        return pd.DataFrame(columns=columns)

def standardize_columns(df):

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df

def rename_column_if_exists(df, old_name, new_name):

    if old_name in df.columns:
        df.rename(columns={old_name: new_name}, inplace=True)

def parse_ms_offset(value):

    try:
        val = float(value)
        val = val * 1000
        return pd.to_timedelta(val, unit='ms')
    except (ValueError, TypeError):
        return pd.NaT

def get_nearest_gps(event_td, gps_df):
    """
    Return (latitude, longitude) from gps_df for the row whose offset_td is
    within MAX_TIME_DELTA of event_td. If none found, return (None, None).
    """
    gps_df["time_diff"] = (gps_df["offset_td"] - event_td).abs()
    within = gps_df[gps_df["time_diff"] <= MAX_TIME_DELTA]
    if not within.empty:
        nearest_row = within.sort_values("time_diff").iloc[0]
        return nearest_row["latitude"], nearest_row["longitude"]
    return None, None

def main():

    departures = read_csv_or_empty(DEPARTURES_FILE, ["departure_time"])
    departures = standardize_columns(departures)
    print("DEBUG: departure_events.csv columns:", departures.columns.tolist())

    # Example: rename "departure_time" -> "event_time_ms" if needed
    rename_column_if_exists(departures, "departure_time", "event_time_ms")
    if "event_time_ms" not in departures.columns:
        sys.exit("ERROR: departure_events.csv doesn't have 'event_time_ms' or 'departure_time'. Columns: " + str(departures.columns.tolist()))

    # Convert the offset to a Timedelta
    departures["event_td"] = departures["event_time_ms"].apply(parse_ms_offset)


    turns = read_csv_or_empty(TURNS_FILE, ["turn_index", "turn_time_s", "center_to_left", "center_to_right"])
    turns = standardize_columns(turns)
    print("DEBUG: turn_transitions.csv columns:", turns.columns.tolist())

    # Example: rename "turn_time" -> "event_time_ms"
    rename_column_if_exists(turns, "turn_time_s", "event_time_ms")
    if "event_time_ms" not in turns.columns:
        sys.exit("ERROR: turn_transitions.csv missing 'turn_time_s' or 'event_time_ms'. Columns: " + str(turns.columns.tolist()))

    # Suppose your CSV uses center_to_left / center_to_right
    if "center_to_left" not in turns.columns or "center_to_right" not in turns.columns:
        sys.exit("ERROR: turn_transitions.csv must have 'center_to_left' and 'center_to_right'. Columns: " + str(turns.columns.tolist()))

    turns["event_td"] = turns["event_time_ms"].apply(parse_ms_offset)

    gps = pd.read_csv(GPS_FILE)
    gps = standardize_columns(gps)
    print("DEBUG: gps_time_periods.csv columns:", gps.columns.tolist())

    # Suppose we rename "start_offsetms" -> "gps_offset_ms"
    rename_column_if_exists(gps, "start_offsetms", "gps_offset_ms")
    if "gps_offset_ms" not in gps.columns:
        sys.exit("ERROR: gps_time_periods.csv missing 'start_offsetms'. Columns: " + str(gps.columns.tolist()))

    # Convert GPS offset to Timedelta
    gps["offset_td"] = pd.to_timedelta(gps["gps_offset_ms"].astype(float), unit="ms")


    # connect to postgres
    try:
        conn = psycopg2.connect(
            host=PG_HOST,
            port=PG_PORT,
            user=PG_USER,
            password=PG_PASSWORD,
            dbname=PG_DB
        )
        cursor = conn.cursor()


        # drop old tables

        cursor.execute("""
            DROP TABLE IF EXISTS incidents;
            DROP TABLE IF EXISTS departure_events;
            DROP TABLE IF EXISTS detected_turns;
        """)
        conn.commit()

        # create tables
        # departure_events
        cursor.execute("""
            CREATE TABLE departure_events (
                id SERIAL PRIMARY KEY,
                event_time_ms BIGINT NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                details TEXT
            );
        """)

        # detected_turns
        cursor.execute("""
            CREATE TABLE detected_turns (
                id SERIAL PRIMARY KEY,
                event_time_ms BIGINT NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                center_to_left INT,
                center_to_right INT
            );
        """)

        #incidents 
        cursor.execute("""
            CREATE TABLE incidents (
                id SERIAL PRIMARY KEY,
                event_time_ms BIGINT NOT NULL,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                event_type TEXT,
                details TEXT,
                departure_event_id INT REFERENCES departure_events(id),
                detected_turn_id INT REFERENCES detected_turns(id)
            );
        """)
        conn.commit()

        for idx, row in departures.iterrows():
            event_td = row["event_td"]
            if pd.isna(event_td):
                print(f"Warning: No valid time for departure row {idx}. Skipped.")
                continue

            # get nearest GPS coords if desired
            lat, lon = get_nearest_gps(event_td, gps)
            event_ms = int(event_td.total_seconds() * 1000)
            if lat is None or lon is None:
                lat, lon = (None, None)

            # Insert departure event
            cursor.execute("""
                INSERT INTO departure_events (event_time_ms, latitude, longitude, details)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, (event_ms, lat, lon, ""))
            dep_id = cursor.fetchone()[0]

            # Also insert into incidents referencing that departure
            cursor.execute("""
                INSERT INTO incidents (
                    event_time_ms, latitude, longitude, event_type, details, departure_event_id
                )
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (event_ms, lat, lon, "departure", "Left the lane", dep_id))


        for idx, row in turns.iterrows():
            event_td = row["event_td"]
            if pd.isna(event_td):
                print(f"Warning: No valid time for turn row {idx}. Skipped.")
                continue

            lat, lon = get_nearest_gps(event_td, gps)
            event_ms = int(event_td.total_seconds() * 1000)
            if lat is None or lon is None:
                lat, lon = (None, None)

            c_left = int(row["center_to_left"])
            c_right = int(row["center_to_right"])

            # Insert turn event
            cursor.execute("""
                INSERT INTO detected_turns (
                    event_time_ms, latitude, longitude, center_to_left, center_to_right
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id;
            """, (event_ms, lat, lon, c_left, c_right))
            turn_id = cursor.fetchone()[0]

            # If user did not look both sides >= 2 times => insert into incidents
            if (c_left < 2) or (c_right < 2):
                note = f"Insufficient looks: L={c_left}, R={c_right}"
                cursor.execute("""
                    INSERT INTO incidents (
                        event_time_ms, latitude, longitude, event_type, details, detected_turn_id
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (event_ms, lat, lon, "turn", note, turn_id))

        conn.commit()
        print("SUCCESS: Created tables with foreign keys, inserted data, and updated incidents accordingly.")

    except psycopg2.Error as e:
        print("PostgreSQL Error:", e)
    except Exception as e:
        print("General Error:", e)
    finally:
        if 'conn' in locals() and conn:
            cursor.close()
            conn.close()

if __name__ == "__main__":
    main()
