#!/usr/bin/env python3
"""
TCP Client (Assignment Part B — Timing & Latency Study)
- Sends 100 sequential messages (seq = 1..100) to the TCP server.
- Each message: {"seq": <int>, "send_ts": <float>, "msg": "Hello <seq>"}
- Waits for ACK from server: {"seq": <int>, "server_recv_ts": <float>}
- Computes RTT = (ack_ts - send_ts) * 1000  (per assignment specification)
- Logs seq, send_ts, ack_ts, rtt_ms to CSV.
- Prints handshake time, RTT stats, and total session duration.
"""

import argparse
import csv
import json
import socket
import statistics
import time

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="linux-01.socs.uoguelph.ca", help="Server hostname or IP")
    ap.add_argument("--port", type=int, default=50995, help="Server TCP port")
    ap.add_argument("--n", type=int, default=100, help="Number of messages (default 100)")
    ap.add_argument("--log-csv", default="tcp_client_log.csv", help="CSV output path")
    ap.add_argument("--connect-timeout", type=float, default=10.0, help="TCP connect timeout (s)")
    ap.add_argument("--recv-timeout", type=float, default=2.0, help="ACK receive timeout (s)")
    ap.add_argument("--verbose", action="store_true", help="Verbose output")
    args = ap.parse_args()

    # --- Measure handshake time ---
    t_syn = time.perf_counter()
    sock = socket.create_connection((args.host, args.port), timeout=args.connect_timeout)
    t_ack = time.perf_counter()
    handshake_time_ms = (t_ack - t_syn) * 1000.0

    if args.verbose:
        print(f"[TCP] Connected to {args.host}:{args.port}")
        print(f"[TCP] Handshake time = {handshake_time_ms:.3f} ms")

    sock.settimeout(args.recv_timeout)

    # --- Send N messages and compute RTT per spec ---
    results = []
    rtts = []
    t_session_start = time.perf_counter()

    for seq in range(1, args.n + 1):
        send_ts = time.time()
        msg = {"seq": seq, "send_ts": send_ts, "msg": f"Hello {seq}"}
        payload = json.dumps(msg) + "\n"

        try:
            sock.sendall(payload.encode())
            data = sock.recv(1024)
            ack = json.loads(data.decode().strip())
            ack_ts = ack.get("server_recv_ts", time.time())

            # Assignment-specified RTT formula
            rtt_ms = (ack_ts - send_ts) * 1000.0
            rtts.append(rtt_ms)
            results.append((seq, send_ts, ack_ts, rtt_ms))

            if args.verbose:
                print(f"[TCP] ACK seq={seq} RTT={rtt_ms:.3f} ms")

        except socket.timeout:
            if args.verbose:
                print(f"[TCP] Timeout waiting for ACK for seq={seq}")
            results.append((seq, send_ts, None, None))
        except Exception as e:
            print(f"[TCP] Error on seq={seq}: {e}")
            break

    t_session_end = time.perf_counter()
    session_duration_ms = (t_session_end - t_session_start) * 1000.0
    sock.close()

    # --- Save CSV log ---
    with open(args.log_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["seq", "send_ts", "ack_ts", "rtt_ms"])
        writer.writerows(results)

    # --- Compute summary ---
    if rtts:
        summary = {
            "sent": args.n,
            "acked": len(rtts),
            "rtt_ms": {
                "avg": round(statistics.mean(rtts), 3),
                "min": round(min(rtts), 3),
                "max": round(max(rtts), 3),
                "median": round(statistics.median(rtts), 3)
            },
            "handshake_ms": round(handshake_time_ms, 3),
            "session_duration_ms": round(session_duration_ms, 3)
        }
    else:
        summary = {
            "sent": args.n,
            "acked": 0,
            "rtt_ms": None,
            "handshake_ms": round(handshake_time_ms, 3),
            "session_duration_ms": round(session_duration_ms, 3)
        }

    print(json.dumps(summary))
    print(f"[TCP] CSV saved to {args.log_csv}")

if __name__ == "__main__":
    main()
