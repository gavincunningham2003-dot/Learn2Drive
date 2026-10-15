"""TCP file receiver (port 5001).

The phone uploads sensor_data.csv, front_video.mp4 and rear_video.mp4 one connection each.
Once all three have arrived, run_pipeline.py is started in the background.
"""
import socket, subprocess, threading, os, sys

SERVER_IP   = "0.0.0.0"
SERVER_PORT = 5001

# the three files we expect from the phone
EXPECT = {"sensor_data.csv", "front_video.mp4", "rear_video.mp4"}

# keep track of arrivals
seen = set()
lock = threading.Lock()      

def run_pipeline():
    """Run the analysis pipeline (run_pipeline.py) on the files in the current directory."""
    try:
        print("▶ running analysis pipeline")
        subprocess.run([sys.executable, "run_pipeline.py"], check=True)
        print("✓ pipeline finished")
    except subprocess.CalledProcessError as e:
        print(f"✖ pipeline failed: {e}", file=sys.stderr)
    finally:
        with lock:
            seen.clear()                 # ready for next batch, even if the run failed

def recv_exact(conn, n):
    """Read exactly n bytes from the socket (recv may return fewer bytes than asked for)."""
    buf = b""
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("connection closed before all data was received")
        buf += chunk
    return buf

def receive_file(conn, addr):
    try:
        # protocol matches DataOutputStream.writeUTF / writeLong on the phone:
        # 2-byte name length, file name, 8-byte file size, then the raw bytes
        name_len = int.from_bytes(recv_exact(conn, 2), 'big')
        fname    = os.path.basename(recv_exact(conn, name_len).decode())  # never allow path components
        fsize    = int.from_bytes(recv_exact(conn, 8), 'big')

        dest = os.path.join(os.getcwd(), fname)
        with open(dest, "wb") as f:
            remain = fsize
            while remain:
                chunk = conn.recv(min(4096, remain))
                if not chunk: break
                f.write(chunk)
                remain -= len(chunk)
        print(f"↳ saved {fname} ({fsize} bytes)")

        with lock:
            seen.add(fname)
            if seen >= EXPECT:
                # start pipeline in a background thread so the server keeps accepting connections
                threading.Thread(target=run_pipeline, daemon=True).start()
    finally:
        conn.close()

def serve():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((SERVER_IP, SERVER_PORT))
        srv.listen(5)
        print(f"🚀 listening on port {SERVER_PORT}")
        while True:
            conn, addr = srv.accept()
            print(f"🔗 {addr} connected")
            threading.Thread(target=receive_file, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    serve()
