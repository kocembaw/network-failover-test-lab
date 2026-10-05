#!/usr/bin/env python3
"""Measure how long traffic is lost while the network fails over.

Sends ICMP echo requests at a fixed interval (iputils ping) and looks for
gaps in the replies. Every gap is an outage; its length is estimated as
lost probes x probe interval.

Examples (run on a lab host, as root):
  failover-probe run 10.2.10.10 --log /root/TC-07.log      # stop with Ctrl+C
  failover-probe run 10.2.10.10 --duration 120 --max-outage 5 --log /root/TC-07.log
  failover-probe analyze /root/TC-07.log --max-outage 5

Exit code: 0 = no threshold given or within threshold, 1 = threshold exceeded
or traffic not recovered, 2 = usage / environment error.
"""
from __future__ import annotations

import argparse
import re
import signal
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_INTERVAL = 0.1

TS_RE = re.compile(r"^\[(?P<ts>\d+(?:\.\d+)?)\]\s*(?P<rest>.*)$")
REPLY_RE = re.compile(r"bytes from .*?icmp_seq=(?P<seq>\d+)")
ERROR_RE = re.compile(r"^From (?P<src>\S+?):? icmp_seq=(?P<seq>\d+)\s+(?P<msg>.+)$")
NO_ANSWER_RE = re.compile(r"no answer yet for icmp_seq=(?P<seq>\d+)")
HEADER_RE = re.compile(r"^# failover-probe .*interval=(?P<interval>[\d.]+)")
TRANSMITTED_RE = re.compile(r"^(?P<n>\d+) packets transmitted")
TARGET_RE = re.compile(r"^PING (?P<target>\S+)")


@dataclass
class Outage:
    first_lost: int          # first lost sequence number (unwrapped)
    lost: int                # number of lost probes
    start_ts: float | None   # time of the last reply before the gap
    end_ts: float | None     # time of the first reply after the gap (None = ongoing)

    def duration(self, interval: float) -> float:
        return self.lost * interval


@dataclass
class ProbeLog:
    interval: float = DEFAULT_INTERVAL
    target: str = "?"
    replies: dict[int, float] = field(default_factory=dict)   # seq -> timestamp
    errors: list[tuple[float, int, str, str]] = field(default_factory=list)
    max_seq: int = 0
    transmitted: int | None = None


class SeqUnwrapper:
    """iputils icmp_seq is 16 bit and wraps to 0; make it monotonic."""

    def __init__(self) -> None:
        self.offset = 0
        self.last_raw: int | None = None

    def __call__(self, raw: int) -> int:
        if self.last_raw is not None and raw < self.last_raw - 32768:
            self.offset += 65536
        self.last_raw = raw
        return raw + self.offset


def parse(lines, interval: float | None = None) -> ProbeLog:
    """Parse `ping -D -O` output (optionally with a failover-probe header)."""
    log = ProbeLog()
    header_interval = None
    unwrap = SeqUnwrapper()

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        header = HEADER_RE.match(line)
        if header:
            header_interval = float(header.group("interval"))
            continue
        target = TARGET_RE.match(line)
        if target:
            log.target = target.group("target")
            continue
        transmitted = TRANSMITTED_RE.match(line)
        if transmitted:
            log.transmitted = int(transmitted.group("n"))
            continue

        stamped = TS_RE.match(line)
        if not stamped:
            continue
        ts = float(stamped.group("ts"))
        rest = stamped.group("rest")

        reply = REPLY_RE.search(rest)
        if reply:
            seq = unwrap(int(reply.group("seq")))
            log.max_seq = max(log.max_seq, seq)
            if "(DUP!)" not in rest:
                log.replies.setdefault(seq, ts)
            continue
        error = ERROR_RE.match(rest)
        if error:
            seq = unwrap(int(error.group("seq")))
            log.max_seq = max(log.max_seq, seq)
            log.errors.append((ts, seq, error.group("src"), error.group("msg").strip()))
            continue
        no_answer = NO_ANSWER_RE.search(rest)
        if no_answer:
            seq = unwrap(int(no_answer.group("seq")))
            log.max_seq = max(log.max_seq, seq)

    log.interval = interval or header_interval or DEFAULT_INTERVAL
    return log


def find_outages(log: ProbeLog) -> tuple[list[Outage], int]:
    """Return (outages, probes lost before the first reply)."""
    seqs = sorted(log.replies)
    if not seqs:
        sent = log.transmitted or log.max_seq
        return ([Outage(1, sent, None, None)] if sent else []), 0

    leading = seqs[0] - 1
    outages = []
    for prev, nxt in zip(seqs, seqs[1:]):
        if nxt - prev > 1:
            outages.append(Outage(prev + 1, nxt - prev - 1,
                                  log.replies[prev], log.replies[nxt]))

    # Probes sent after the last reply. The very last probe may still have
    # been in flight when ping stopped, so one missing probe is not an outage.
    last_sent = max(log.max_seq, log.transmitted or 0)
    trailing = last_sent - seqs[-1]
    if trailing > 1:
        outages.append(Outage(seqs[-1] + 1, trailing, log.replies[seqs[-1]], None))
    return outages, leading


def clock(ts: float | None) -> str:
    if ts is None:
        return "?"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def report(log: ProbeLog, max_outage: float | None = None) -> tuple[str, bool]:
    """Build the text report; second value is False if the threshold is exceeded."""
    outages, leading = find_outages(log)
    sent = max(log.transmitted or 0, log.max_seq)
    received = len(log.replies)
    lost = max(sent - received, 0)
    loss_pct = (100.0 * lost / sent) if sent else 0.0

    out = [
        f"Target: {log.target}   probe interval: {log.interval:.3f} s",
        f"Probes sent: {sent}   replies: {received}   lost: {lost} ({loss_pct:.1f}%)",
    ]
    if leading:
        out.append(f"Note: {leading} probe(s) lost before the first reply "
                   "(target was not reachable when the probe started).")

    if outages:
        out.append("Outages (times in UTC):")
        for i, o in enumerate(outages, 1):
            end = clock(o.end_ts) if o.end_ts is not None else "not recovered"
            out.append(f"  #{i}  {clock(o.start_ts)} -> {end}   "
                       f"lost {o.lost} probe(s)  ~ {o.duration(log.interval):.1f} s")
    else:
        out.append("Outages: none")

    if log.errors:
        out.append(f"ICMP errors received: {len(log.errors)}")
        seen = {}
        for ts, _seq, src, msg in log.errors:
            seen.setdefault((src, msg), ts)
        for (src, msg), ts in seen.items():
            out.append(f"  first at {clock(ts)} UTC: From {src}: {msg}")

    ok = True
    longest = max((o.duration(log.interval) for o in outages), default=0.0)
    not_recovered = any(o.end_ts is None for o in outages)
    out.append(f"Longest outage: ~ {longest:.1f} s"
               + ("  (traffic NOT recovered when the probe stopped)" if not_recovered else ""))
    if max_outage is not None:
        ok = (longest <= max_outage) and not not_recovered
        out.append(f"Threshold: {max_outage:.1f} s -> {'WITHIN' if ok else 'EXCEEDED'}")
    return "\n".join(out), ok


def check_ping() -> None:
    try:
        result = subprocess.run(["ping", "-V"], capture_output=True, text=True)
    except FileNotFoundError:
        sys.exit("failover-probe: 'ping' not found. Install iputils.")
    if "iputils" not in (result.stdout + result.stderr):
        sys.exit("failover-probe: this ping is not iputils (BusyBox ping has no -D). "
                 "Install iputils, e.g. 'apk add iputils'.")


def run(args) -> int:
    check_ping()
    log_path = Path(args.log or f"probe-{args.target}-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.log")
    # No "ping -w": with a deadline, iputils ping exits on the first ICMP error
    # (e.g. Destination Net Unreachable), which is exactly what some tests expect.
    cmd = ["ping", "-D", "-O", "-n", "-i", str(args.interval), "-W", "1", args.target]

    print(f"failover-probe: logging to {log_path}  (Ctrl+C to stop)", flush=True)
    with log_path.open("w") as f:
        f.write(f"# failover-probe target={args.target} interval={args.interval} "
                f"started={datetime.now(timezone.utc).isoformat(timespec='seconds')}\n")
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        timer = None
        if args.duration:
            timer = threading.Timer(args.duration, proc.send_signal, [signal.SIGINT])
            timer.start()

        def pump():
            for line in proc.stdout:
                f.write(line)
                f.flush()
                if not args.quiet or not REPLY_RE.search(line):
                    sys.stdout.write(line)

        try:
            pump()
        except KeyboardInterrupt:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)
            pump()
        proc.wait()
        if timer:
            timer.cancel()

    with log_path.open() as f:
        text, ok = report(parse(f, args.interval), args.max_outage)
    print("\n" + text)
    print(f"\nRaw log: {log_path}")
    return 0 if ok else 1


def analyze(args) -> int:
    with open(args.logfile) as f:
        text, ok = report(parse(f, args.interval), args.max_outage)
    print(text)
    return 0 if ok else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Measure traffic loss during network failover.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="probe a target and report outages")
    p_run.add_argument("target")
    p_run.add_argument("--interval", type=float, default=DEFAULT_INTERVAL,
                       help="seconds between probes (default 0.1; below 0.2 needs root)")
    p_run.add_argument("--duration", type=int, help="stop after N seconds")
    p_run.add_argument("--log", help="raw log file (default: probe-<target>-<time>.log)")
    p_run.add_argument("--max-outage", type=float,
                       help="pass/fail threshold in seconds for the longest outage")
    p_run.add_argument("--quiet", action="store_true",
                       help="print only lost probes and errors, not every reply")
    p_run.set_defaults(func=run)

    p_an = sub.add_parser("analyze", help="analyse a saved log")
    p_an.add_argument("logfile")
    p_an.add_argument("--interval", type=float,
                      help="override the probe interval stored in the log")
    p_an.add_argument("--max-outage", type=float,
                      help="pass/fail threshold in seconds for the longest outage")
    p_an.set_defaults(func=analyze)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
