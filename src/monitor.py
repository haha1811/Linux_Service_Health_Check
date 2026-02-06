#!/usr/bin/env python3
import argparse
import json
import os
import shlex
import socket
import subprocess
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List


def load_env(env_path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not env_path:
        return env
    if not os.path.exists(env_path):
        return env
    with open(env_path, "r", encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip().strip("\"")
    return env


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str, payload: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_command(command: List[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, check=False)


def run_shell(command: str) -> subprocess.CompletedProcess:
    return subprocess.run(command, capture_output=True, text=True, shell=True, check=False)


def is_service_active(service_name: str) -> bool:
    result = run_command(["systemctl", "is-active", "--quiet", service_name])
    return result.returncode == 0


def restart_service(service_name: str) -> subprocess.CompletedProcess:
    return run_command(["systemctl", "restart", service_name])


def format_subject(prefix: str, service_name: str, host: str) -> str:
    return f"[{prefix}] {service_name} on {host}"


def format_body(prefix: str, service_name: str, host: str) -> str:
    timestamp = utc_now()
    return (
        f"Service: {service_name}\n"
        f"Host: {host}\n"
        f"Time (UTC): {timestamp}\n"
        f"Status: {prefix}\n"
    )


def send_sendgrid(env: Dict[str, str], subject: str, body: str) -> None:
    import urllib.request
    import urllib.error

    api_key = env.get("SENDGRID_API_KEY", "")
    sender = env.get("SENDGRID_FROM", "")
    recipient = env.get("SENDGRID_TO", "")
    if not api_key or not sender or not recipient:
        raise RuntimeError("SendGrid env vars missing. Require SENDGRID_API_KEY, SENDGRID_FROM, SENDGRID_TO")

    payload = {
        "personalizations": [{"to": [{"email": recipient}]}],
        "from": {"email": sender},
        "subject": subject,
        "content": [{"type": "text/plain", "value": body}],
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.sendgrid.com/v3/mail/send",
        data=data,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        if response.status >= 300:
            raise RuntimeError(f"SendGrid response status {response.status}")


def send_smtp(env: Dict[str, str], subject: str, body: str) -> None:
    import smtplib
    from email.message import EmailMessage

    host = env.get("SMTP_HOST", "")
    port = int(env.get("SMTP_PORT", "587"))
    user = env.get("SMTP_USER", "")
    password = env.get("SMTP_PASSWORD", "")
    sender = env.get("SMTP_FROM", user)
    recipient = env.get("SMTP_TO", "")
    use_tls = env.get("SMTP_TLS", "true").lower() == "true"
    use_ssl = env.get("SMTP_SSL", "false").lower() == "true"

    if not host or not recipient:
        raise RuntimeError("SMTP env vars missing. Require SMTP_HOST, SMTP_TO")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    if use_ssl:
        server = smtplib.SMTP_SSL(host, port, timeout=10)
    else:
        server = smtplib.SMTP(host, port, timeout=10)

    with server:
        if use_tls and not use_ssl:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(message)


def send_email(provider: str, env: Dict[str, str], subject: str, body: str) -> None:
    if provider == "sendgrid":
        send_sendgrid(env, subject, body)
        return
    if provider == "smtp":
        send_smtp(env, subject, body)
        return
    raise RuntimeError(f"Unsupported email provider: {provider}")


def should_check(service_state: Dict[str, Any], interval_seconds: int, now_ts: float) -> bool:
    last_checked = service_state.get("last_checked", 0)
    if interval_seconds <= 0:
        return True
    return now_ts - last_checked >= interval_seconds


def update_service_state(
    service_name: str,
    service_config: Dict[str, Any],
    service_state: Dict[str, Any],
    provider: str,
    env: Dict[str, str],
    host: str,
) -> Dict[str, Any]:
    interval_seconds = int(service_config.get("check_interval_seconds", 30))
    fail_restart = int(service_config.get("failures_before_restart", 2))
    fail_alert = int(service_config.get("failures_before_alert", 3))
    post_restart_commands = service_config.get("post_restart_commands", [])
    now_ts = datetime.now(timezone.utc).timestamp()

    if not should_check(service_state, interval_seconds, now_ts):
        return service_state

    active = is_service_active(service_name)
    service_state["last_checked"] = now_ts

    if active:
        if service_state.get("status") == "down":
            subject = format_subject("RECOVERED", service_name, host)
            body = format_body("RECOVERED", service_name, host)
            send_email(provider, env, subject, body)
        service_state.update(
            {
                "status": "up",
                "consecutive_failures": 0,
                "alert_sent": False,
            }
        )
        return service_state

    consecutive_failures = int(service_state.get("consecutive_failures", 0)) + 1
    service_state["consecutive_failures"] = consecutive_failures
    service_state["status"] = "down"

    if consecutive_failures == fail_restart:
        restart_result = restart_service(service_name)
        service_state["last_restart_rc"] = restart_result.returncode
        service_state["last_restart_stdout"] = restart_result.stdout
        service_state["last_restart_stderr"] = restart_result.stderr
        for command in post_restart_commands:
            run_shell(command)

    if consecutive_failures >= fail_alert and not service_state.get("alert_sent"):
        subject = format_subject("ALERT", service_name, host)
        body = format_body("ALERT", service_name, host)
        send_email(provider, env, subject, body)
        service_state["alert_sent"] = True

    return service_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Monitor systemd services and send alerts.")
    parser.add_argument("--config", required=True, help="Path to config.json")
    parser.add_argument("--env", required=False, default="", help="Path to .env for mail credentials")
    args = parser.parse_args()

    config = load_json(args.config, {})
    provider = config.get("email_provider", "sendgrid").lower()
    state_path = config.get("state_path", "/var/lib/service-monitor/state.json")
    services = config.get("services", {})
    if not services:
        print("No services configured.", file=sys.stderr)
        return 1

    env = load_env(args.env)
    host = socket.gethostname()

    state = load_json(state_path, {})
    for service_name, service_config in services.items():
        service_state = state.get(service_name, {})
        updated_state = update_service_state(
            service_name,
            service_config or {},
            service_state,
            provider,
            env,
            host,
        )
        state[service_name] = updated_state

    save_json(state_path, state)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
