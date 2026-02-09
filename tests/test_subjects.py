import importlib.util
import os
import unittest


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


if __name__ == "__main__":
    unittest.main()
