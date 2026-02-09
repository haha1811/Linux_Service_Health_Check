import importlib.util
import os
import unittest
from datetime import datetime, timezone


def load_monitor_module():
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    monitor_path = os.path.join(repo_root, "src", "monitor.py")
    spec = importlib.util.spec_from_file_location("monitor", monitor_path)
    module = importlib.util.module_from_spec(spec)
    if spec and spec.loader:
        spec.loader.exec_module(module)
    return module


class SubjectFormatTests(unittest.TestCase):
    def test_alert_subject(self) -> None:
        monitor = load_monitor_module()
        subject = monitor.format_subject("ALERT", "port 80", "example-host")
        self.assertEqual(subject, "[ALERT] port 80 on example-host")

    def test_recovered_subject(self) -> None:
        monitor = load_monitor_module()
        subject = monitor.format_subject("RECOVERED", "nginx.service", "example-host")
        self.assertEqual(subject, "[RECOVERED] nginx.service on example-host")


class BodyFormatTests(unittest.TestCase):
    def test_body_time_zone_taipei(self) -> None:
        monitor = load_monitor_module()
        now_dt = datetime(2026, 2, 9, 7, 26, 1, tzinfo=timezone.utc)
        body = monitor.format_body(
            "ALERT",
            "port 80",
            "example-host",
            time_zone="Asia/Taipei",
            now_dt=now_dt,
        )
        self.assertIn("Time (Asia/Taipei): 2026-02-09T15:26:01+08:00", body)

    def test_body_time_zone_utc(self) -> None:
        monitor = load_monitor_module()
        now_dt = datetime(2026, 2, 9, 7, 26, 1, tzinfo=timezone.utc)
        body = monitor.format_body(
            "ALERT",
            "port 80",
            "example-host",
            time_zone="UTC",
            now_dt=now_dt,
        )
        self.assertIn("Time (UTC): 2026-02-09T07:26:01+00:00", body)

    def test_body_time_zone_invalid(self) -> None:
        monitor = load_monitor_module()
        now_dt = datetime(2026, 2, 9, 7, 26, 1, tzinfo=timezone.utc)
        with self.assertRaises(ValueError) as ctx:
            monitor.format_body(
                "ALERT",
                "port 80",
                "example-host",
                time_zone="Asia/Taipeii",
                now_dt=now_dt,
            )
        message = str(ctx.exception)
        self.assertIn("Asia/Taipeii", message)
        self.assertIn("UTC", message)
        self.assertIn("Asia/Taipei", message)


if __name__ == "__main__":
    unittest.main()
