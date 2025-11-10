#!/usr/bin/env python3
"""
UDP Client (Python-only)
- Sends N JSON messages (seq 1..N) to linux-01.socs.uoguelph.ca:50995.
- Measures RTT with time.perf_counter(), handles out-of-order ACKs.
- Logs CSV: seq,send_ts,ack_ts,rtt_ms,outcome; prints JSON + human summary.
- Now prints real-time RTT per ACK as soon as it is first observed.
"""
import argparse, csv, json, random, socket, time, statistics

def now_perf(): return time.perf_counter()
def jitter_sleep(interval, jitter): time.sleep(interval * (1.0 + random.uniform(-jitter, jitter)))

def main():
    ap = argparse.ArgumentParser(description="UDP client with real-time RTT prints and OOO ACK handling")
    ap.add_argument("--host", default="linux-01.socs.uoguelph.ca", help="Server hostname / IP")
    ap.add_argument("--port", type=int, default=50995, help="Assigned UDP port")
    ap.add_argument("--n", type=int, default=100, help="Number of messages (seq 1..N)")
    ap.add_argument("--interval", type=float, default=0.1, help="Base interval (s)")
    ap.add_argument("--jitter", type=float, default=0.1, help="±proportional jitter")
    ap.add_argument("--timeout", type=float, default=1.0, help="Socket timeout (s)")
    ap.add_argument("--seed", type=int, default=32101211950, help="RNG seed for reproducibility")
    ap.add_argument("--log-csv", default="udp_client_log.csv", help="CSV log file")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    random.seed(args.seed)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(args.timeout)

    fields = ["seq", "send_ts", "ack_ts", "rtt_ms", "outcome"]
    f = open(args.log_csv, "w", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()

    sent_count = ack_count = 0
    seen_seqs, send_perf, send_wall, ack_perf, ack_wall, finalized = set(), {}, {}, {}, {}, set()

    def finalize(seq, outcome):
        if seq in finalized: return
        row = {
            "seq": seq,
            "send_ts": f"{send_wall.get(seq,0):.6f}" if seq in send_wall else "",
            "ack_ts": f"{ack_wall.get(seq,0):.6f}" if outcome=="ACKED" and seq in ack_wall else "",
            "rtt_ms": "",
            "outcome": outcome
        }
        if outcome=="ACKED" and seq in send_perf and seq in ack_perf:
            row["rtt_ms"]=f"{(ack_perf[seq]-send_perf[seq])*1000:.3f}"
        writer.writerow(row)
        finalized.add(seq)

    for seq in range(1, args.n + 1):
        if seq in seen_seqs:
            raise RuntimeError(f"Duplicate seq {seq}")
        seen_seqs.add(seq)

        payload = {"seq": seq, "send_ts": time.time(), "msg": f"Hello {seq}"}
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        send_perf[seq]=now_perf(); send_wall[seq]=payload["send_ts"]
        sock.sendto(data,(args.host,args.port))
        sent_count+=1
        if args.verbose: print(f"[CLIENT] Sent seq={seq}")

        deadline=now_perf()+args.timeout; got_current=False
        while True:
            remaining=deadline-now_perf()
            if remaining<=0: break
            sock.settimeout(remaining)
            try:
                rx,_=sock.recvfrom(65535)
                t_perf,t_wall=now_perf(),time.time()
                ack=json.loads(rx.decode("utf-8",errors="strict"))
                s=int(ack.get("seq"))

                # First observation of ACK for seq s → store times and print RTT immediately
                if s not in ack_perf:
                    ack_perf[s],ack_wall[s]=t_perf,t_wall
                    if s in send_perf and args.verbose:
                        rtt_ms = (t_perf - send_perf[s]) * 1000.0
                        print(f"[CLIENT] ACKED seq={s} RTT={rtt_ms:.3f} ms")

                # If this ACK is for the current seq, finalize now
                if s==seq and seq not in finalized:
                    ack_count+=1; finalize(seq,"ACKED"); got_current=True; break
            except socket.timeout:
                break
            except Exception as e:
                if args.verbose: print(f"[CLIENT] RX error: {e}")

        # If current seq wasn’t ACKed in time, either it was ACKed earlier (OOO) or it timed out
        if not got_current and seq not in finalized:
            if seq in ack_perf:
                ack_count+=1; finalize(seq,"ACKED")
            else:
                finalize(seq,"TIMEOUT")
                if args.verbose:
                    print(f"[CLIENT] TIMEOUT seq={seq}")

        jitter_sleep(args.interval,args.jitter)

    f.flush(); f.close()

    # RTT stats
    rtts=[]
    with open(args.log_csv,"r",encoding="utf-8") as rf:
        for row in csv.DictReader(rf):
            if row["outcome"]=="ACKED" and row["rtt_ms"]:
                try: rtts.append(float(row["rtt_ms"]))
                except ValueError: pass

    loss=(sent_count-ack_count)/sent_count if sent_count else 0
    summary={
        "sent":sent_count,"acked":ack_count,
        "loss_ratio":round(loss,2),"seed":args.seed,
        "rtt_ms":{
            "avg":round(statistics.mean(rtts),3) if rtts else None,
            "min":round(min(rtts),3) if rtts else None,
            "max":round(max(rtts),3) if rtts else None
        }
    }
    print(json.dumps(summary,separators=(",",":")))
    print(f"[CLIENT] sent={sent_count} acked={ack_count} loss_ratio={summary['loss_ratio']} "
          f"rtt_ms(avg/min/max)={summary['rtt_ms']['avg']}/{summary['rtt_ms']['min']}/{summary['rtt_ms']['max']}")
    if args.verbose: print(f"[CLIENT] Log saved to {args.log_csv}")

if __name__=="__main__":
    main()
