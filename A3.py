#!/usr/bin/env python3
"""
UDP Server (Python-only)
- Listens on assigned port (50995) on linux-01.socs.uoguelph.ca.
- Simulates loss via --drop-k OR --loss-prob (exactly one active).
- Echoes JSON ACKs: { "seq": <int>, "server_recv_ts": <float> }.
Allowed libs: argparse, json, random, socket, time, sys, signal
"""
import argparse, json, random, socket, time, sys, signal

def main():
    ap = argparse.ArgumentParser(description="UDP ACK server with optional loss models")
    ap.add_argument("--host", default="0.0.0.0", help="Bind address on school server")
    ap.add_argument("--port", type=int, default=50995, help="Assigned UDP port")
    ap.add_argument("--loss-prob", type=float, default=0.0, help="Bernoulli drop probability [0,1]")
    ap.add_argument("--drop-k", type=int, default=0, help="Drop every k-th packet (0=off)")
    ap.add_argument("--seed", type=int, default=32101211950, help="RNG seed for reproducibility")
    ap.add_argument("--verbose", action="store_true", help="Print per-packet events")
    args = ap.parse_args()

    # Only one loss model active
    if args.loss_prob > 0.0 and args.drop_k > 0:
        print("Use only one loss model at a time (--loss-prob OR --drop-k).", file=sys.stderr)
        sys.exit(1)

    random.seed(args.seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.host, args.port))

    if args.verbose:
        print(f"[SERVER] Listening on {args.host}:{args.port} | "
              f"loss_prob={args.loss_prob} drop_k={args.drop_k} seed={args.seed}")

    recv_count = 0

    def _print_summary():
        model = "drop-k" if args.drop_k > 0 else ("bernoulli" if args.loss_prob > 0.0 else "none")
        print(f"\n[SERVER] Summary: recv_count={recv_count}, loss_model={model}, "
              f"k={args.drop_k}, p={args.loss_prob}, seed={args.seed}")

    def _sigint(*_):
        _print_summary()
        sys.exit(0)

    signal.signal(signal.SIGINT, _sigint)

    while True:
        data, addr = sock.recvfrom(65535)
        recv_ts = time.time()
        recv_count += 1

        try:
            payload = json.loads(data.decode("utf-8"))
            seq = int(payload.get("seq"))
        except Exception:
            continue

        # Deterministic drop-k
        if args.drop_k > 0 and seq % args.drop_k == 0:
            if args.verbose: print(f"[SERVER] DROP-K seq={seq}")
            continue

        # Bernoulli loss
        if args.loss_prob > 0.0 and random.random() < args.loss_prob:
            if args.verbose: print(f"[SERVER] LOSS-PROB seq={seq}")
            continue

        ack = {"seq": seq, "server_recv_ts": recv_ts}
        sock.sendto(json.dumps(ack, separators=(",", ":")).encode("utf-8"), addr)
        if args.verbose:
            print(f"[SERVER] ACK seq={seq} (recv_count={recv_count})")

if __name__ == "__main__":
    main()
