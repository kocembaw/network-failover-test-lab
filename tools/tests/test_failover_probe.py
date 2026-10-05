"""Unit tests for failover_probe.py. Run: python3 -m unittest discover -s tools/tests -v

The ping logs below are synthetic fixtures built in code, not lab results.
"""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import failover_probe as fp  # noqa: E402

T0 = 1_700_000_000.0


def reply(seq, interval=0.1, dup=False):
    ts = T0 + seq * interval
    line = f"[{ts:.6f}] 64 bytes from 10.2.10.10: icmp_seq={seq % 65536} ttl=62 time=0.4 ms"
    return line + (" (DUP!)" if dup else "")


def no_answer(seq, interval=0.1):
    return f"[{T0 + seq * interval:.6f}] no answer yet for icmp_seq={seq % 65536}"


def unreachable(seq, interval=0.1):
    return (f"[{T0 + seq * interval:.6f}] From 10.1.10.1 icmp_seq={seq % 65536} "
            "Destination Net Unreachable")


HEADER = ["# failover-probe target=10.2.10.10 interval=0.1 started=2026-01-01T12:00:00",
          "PING 10.2.10.10 (10.2.10.10) 56(84) bytes of data."]


class ParseAndReport(unittest.TestCase):
    def test_no_loss(self):
        log = fp.parse(HEADER + [reply(s) for s in range(1, 21)])
        outages, leading = fp.find_outages(log)
        self.assertEqual(outages, [])
        self.assertEqual(leading, 0)
        _, ok = fp.report(log, max_outage=5)
        self.assertTrue(ok)

    def test_single_outage_duration(self):
        lines = (HEADER + [reply(s) for s in range(1, 11)]
                 + [no_answer(s) for s in range(11, 48)]
                 + [reply(s) for s in range(48, 61)])
        log = fp.parse(lines)
        outages, _ = fp.find_outages(log)
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0].first_lost, 11)
        self.assertEqual(outages[0].lost, 37)
        self.assertAlmostEqual(outages[0].duration(log.interval), 3.7)
        _, ok = fp.report(log, max_outage=5)
        self.assertTrue(ok)
        _, ok = fp.report(log, max_outage=3)
        self.assertFalse(ok)

    def test_interval_from_header_and_override(self):
        log = fp.parse(["# failover-probe target=x interval=0.2 started=now"])
        self.assertEqual(log.interval, 0.2)
        log = fp.parse(["# failover-probe target=x interval=0.2 started=now"], interval=0.5)
        self.assertEqual(log.interval, 0.5)

    def test_not_recovered_with_icmp_errors(self):
        lines = (HEADER + [reply(s) for s in range(1, 6)]
                 + [unreachable(s) for s in range(6, 30)]
                 + ["", "--- 10.2.10.10 ping statistics ---",
                    "29 packets transmitted, 5 received, +24 errors, 82.7586% packet loss"])
        log = fp.parse(lines)
        self.assertEqual(len(log.errors), 24)
        outages, _ = fp.find_outages(log)
        self.assertEqual(len(outages), 1)
        self.assertIsNone(outages[0].end_ts)
        text, ok = fp.report(log, max_outage=5)
        self.assertFalse(ok)
        self.assertIn("Destination Net Unreachable", text)
        self.assertIn("NOT recovered", text)

    def test_last_probe_in_flight_is_not_an_outage(self):
        lines = HEADER + [reply(s) for s in range(1, 11)] + [no_answer(11)]
        outages, _ = fp.find_outages(fp.parse(lines))
        self.assertEqual(outages, [])

    def test_duplicates_ignored(self):
        lines = HEADER + [reply(1), reply(1, dup=True), reply(2), reply(3)]
        log = fp.parse(lines)
        self.assertEqual(sorted(log.replies), [1, 2, 3])

    def test_sequence_wraparound(self):
        # 65534, 65535 received; 0 and 1 (= 65536, 65537) lost; 2 (= 65538) received
        lines = HEADER + [reply(65534), reply(65535), no_answer(65536),
                          no_answer(65537), reply(65538)]
        outages, _ = fp.find_outages(fp.parse(lines))
        self.assertEqual(len(outages), 1)
        self.assertEqual(outages[0].lost, 2)

    def test_leading_loss_reported_separately(self):
        lines = HEADER + [no_answer(1), no_answer(2), reply(3), reply(4)]
        outages, leading = fp.find_outages(fp.parse(lines))
        self.assertEqual(outages, [])
        self.assertEqual(leading, 2)

    def test_no_replies_at_all(self):
        lines = HEADER + [no_answer(s) for s in range(1, 11)]
        log = fp.parse(lines)
        outages, _ = fp.find_outages(log)
        self.assertEqual(len(outages), 1)
        _, ok = fp.report(log, max_outage=5)
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
