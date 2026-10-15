"""Event API (port 9000).

The phone's map screen sends the line GET_EVENTS and receives a 4-byte big-endian length
followed by a JSON array of events (time, coordinates, type and look counts).
"""

import os
import socket
import threading
import json
from contextlib import closing
import psycopg2

# connection settings default to the values in docker-compose.yaml; override with environment variables
PG = dict(
    host=os.environ.get("PG_HOST", "localhost"),
    port=int(os.environ.get("PG_PORT", "5432")),
    dbname=os.environ.get("PG_DB", "Incidents"),
    user=os.environ.get("PG_USER", "Learner"),
    password=os.environ.get("PG_PASSWORD", "Cars2025")
)

SQL = """
SELECT
  -- pick the timestamp from whichever table has it
  COALESCE(i.event_time_ms, dt.event_time_ms, de.event_time_ms) AS event_time_ms,

  -- pick whichever coords exist
  COALESCE(dt.latitude, de.latitude)   AS latitude,
  COALESCE(dt.longitude, de.longitude) AS longitude,

  -- classify row
  CASE
    WHEN de.id IS NOT NULL THEN 'departure'
    WHEN dt.id IS NOT NULL THEN 'turn'
    ELSE 'other'
  END                                    AS type,

  -- look counts only make sense for turns
  COALESCE(dt.center_to_left,  0)        AS center_to_left,
  COALESCE(dt.center_to_right, 0)        AS center_to_right

FROM incidents i
  FULL OUTER JOIN detected_turns dt
    ON dt.id = i.detected_turn_id
  FULL OUTER JOIN departure_events de
    ON de.id = i.departure_event_id;
"""
# Run the SQL above and return rows
def fetch_events():
    # closing() is needed because psycopg2's "with conn" only ends the transaction, it does not close the connection
    with closing(psycopg2.connect(**PG)) as conn, conn.cursor() as cur:
        cur.execute(SQL)
        cols = [desc.name for desc in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]

def handle_client(conn, addr):  #Serve client expect GET_EVENTS then send JSON
    try:
        cmd = b""
        while not cmd.endswith(b"\n"):
            chunk = conn.recv(1)
            if not chunk:
                return
            cmd += chunk

        if cmd.strip() != b"GET_EVENTS":
            print(f"✖ unknown command from {addr}: {cmd!r}")
            return

        payload = json.dumps(fetch_events()).encode("utf-8")
        conn.sendall(len(payload).to_bytes(4, "big") + payload)
        print(f"✔ sent {len(payload)} bytes to {addr}")
    finally:
        conn.close()

def serve():        #Start TCP server on port 9000
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0", 9000))
    srv.listen()
    print(" TCP server ready on port 9000")

    while True:
        client, addr = srv.accept()
        threading.Thread(
            target=handle_client,
            args=(client, addr),
            daemon=True
        ).start()

if __name__ == "__main__":
    serve()
