#!/usr/bin/env python3
"""
TCP Server (Assignment Part B — Timing & Latency Study)
- Runs on the school's Linux server, listening on the assigned TCP port.
- Accepts a single client connection at a time (serially).
- Receives line-delimited JSON messages:
    {"seq": <int>, "send_ts": <float>, "msg": "Hello <seq>"}
- Waits an artificial delay (default 50 ms) before sending an ACK line:
    {"seq": <int>, "server_recv_ts": <float>}
- Prints connection establishment and closure messages.
"""
import argparse, json, socket, time

def handle_connection(conn, addr, delay_ms, verbose):
    if verbose:
        print(f"[TCP] Connected: {addr}")
    rfile = conn.makefile("r", encoding="utf-8", newline="\n")
    wfile = conn.makefile("w", encoding="utf-8", newline="\n")
    try:
        for line in rfile:
            line = line.strip()
            if not line:
                continue
            recv_ts = time.time()
            try:
                payload = json.loads(line)
                seq = int(payload.get("seq"))
            except Exception:
                # Ignore malformed input lines
                continue

            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

            ack = {"seq": seq, "server_recv_ts": recv_ts}
            wfile.write(json.dumps(ack, separators=(",", ":")) + "\n")
            wfile.flush()

            if verbose:
                print(f"[TCP] ACK seq={seq} to {addr}")
    finally:
        try:
            wfile.flush()
        except Exception:
            pass
        rfile.close()
        wfile.close()
        conn.close()
        if verbose:
            print(f"[TCP] Disconnected: {addr}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0", help="Bind address (default 0.0.0.0)")
    ap.add_argument("--port", type=int, required=True, help="Assigned TCP port to listen on")
    ap.add_argument("--delay-ms", type=float, default=50.0, help="Artificial server delay before ACK (ms)")
    ap.add_argument("--verbose", action="store_true", help="Verbose logging")
    args = ap.parse_args()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((args.host, args.port))
        srv.listen(1)
        if args.verbose:
            print(f"[TCP] Listening on {args.host}:{args.port} (delay={args.delay_ms} ms)")
        while True:
            conn, addr = srv.accept()
            handle_connection(conn, addr, args.delay_ms, args.verbose)

if __name__ == "__main__":
    main()
