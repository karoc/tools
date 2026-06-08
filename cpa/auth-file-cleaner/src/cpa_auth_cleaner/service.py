"""systemd service and timer registration for the CPA auth cleaner."""

import json
import re
import subprocess
import sys
from pathlib import Path


DEFAULT_SERVICE_NAME = "cpa-auth-file-cleaner"
DEFAULT_INTERVAL = "1min"
DEFAULT_ENV_FILE = "/etc/cpa-auth-file-cleaner.env"
SYSTEM_UNIT_DIR = "/etc/systemd/system"
USER_UNIT_DIR = "~/.config/systemd/user"


def service_action_requested(args):
    return bool(args.install_service or args.uninstall_service or args.print_service_units)


def handle_service_action(args):
    actions = [
        name
        for name, enabled in (
            ("install", args.install_service),
            ("uninstall", args.uninstall_service),
            ("print", args.print_service_units),
        )
        if enabled
    ]
    if len(actions) != 1:
        raise ValueError("choose exactly one service action")

    config = build_service_config(args)
    if args.print_service_units:
        return service_report("print", config)
    if args.install_service:
        return install_service(config)
    return uninstall_service(config)


def build_service_config(args):
    service_name = normalize_service_name(args.service_name)
    interval = clean_unit_value(args.service_interval, "service interval")
    env_file = clean_unit_value(args.service_env_file, "service env file")
    unit_dir = service_unit_dir(args)
    repo_root = (
        Path(args.service_working_dir).expanduser()
        if args.service_working_dir
        else discover_repo_root()
    )
    tools_entry = repo_root / "tools.py"
    if not tools_entry.exists():
        raise ValueError("tools.py not found for service working directory: %s" % repo_root)

    service_user = clean_unit_value(args.service_user, "service user")
    if args.user_service and service_user:
        raise ValueError("--service-user is only valid for system services")

    run_args = build_service_run_args(args)
    return {
        "name": service_name,
        "service_file": "%s.service" % service_name,
        "timer_file": "%s.timer" % service_name,
        "service_path": str(unit_dir / ("%s.service" % service_name)),
        "timer_path": str(unit_dir / ("%s.timer" % service_name)),
        "unit_dir": str(unit_dir),
        "interval": interval,
        "env_file": env_file,
        "python": clean_unit_value(args.service_python, "service python"),
        "repo_root": str(repo_root),
        "tools_entry": str(tools_entry),
        "service_user": service_user,
        "user_service": bool(args.user_service),
        "run_args": run_args,
    }


def build_service_run_args(args):
    if args.management_key:
        raise ValueError(
            "do not store --management-key in a service; use --management-key-env "
            "and --service-env-file"
        )
    run_args = ["--source", args.source, "--auth-dir", args.auth_dir]
    if args.move_dir.strip():
        run_args.extend(["--move-dir", args.move_dir])
    if args.source == "management":
        if not args.management_url.strip():
            raise ValueError("--management-url is required for management service registration")
        run_args.extend(["--management-url", args.management_url])
        run_args.extend(["--management-key-env", args.management_key_env])
        run_args.extend(["--match", args.match])
    if args.execute:
        run_args.append("--execute")
    if args.no_recursive:
        run_args.append("--no-recursive")
    run_args.append("--json")
    return run_args


def service_unit_dir(args):
    if args.service_unit_dir.strip():
        return Path(args.service_unit_dir).expanduser()
    if args.user_service:
        return Path(USER_UNIT_DIR).expanduser()
    return Path(SYSTEM_UNIT_DIR)


def service_report(action, config, commands=None):
    service_unit = render_service_unit(config)
    timer_unit = render_timer_unit(config)
    return {
        "action": action,
        "service_name": config["name"],
        "service_file": config["service_file"],
        "timer_file": config["timer_file"],
        "service_path": config["service_path"],
        "timer_path": config["timer_path"],
        "interval": config["interval"],
        "env_file": config["env_file"],
        "user_service": config["user_service"],
        "run_args": config["run_args"],
        "commands": commands or [],
        "service_unit": service_unit,
        "timer_unit": timer_unit,
    }


def install_service(config):
    unit_dir = Path(config["unit_dir"])
    unit_dir.mkdir(parents=True, exist_ok=True)
    Path(config["service_path"]).write_text(render_service_unit(config), encoding="utf-8")
    Path(config["timer_path"]).write_text(render_timer_unit(config), encoding="utf-8")

    commands = [
        systemctl(config, ["daemon-reload"]),
        systemctl(config, ["enable", "--now", config["timer_file"]]),
    ]
    return service_report("install", config, commands=commands)


def uninstall_service(config):
    commands = [
        systemctl(config, ["disable", "--now", config["timer_file"]], check=False),
    ]
    for path in (Path(config["timer_path"]), Path(config["service_path"])):
        if path.exists():
            path.unlink()
    commands.append(systemctl(config, ["daemon-reload"]))
    return service_report("uninstall", config, commands=commands)


def systemctl(config, args, check=True):
    command = ["systemctl"]
    if config["user_service"]:
        command.append("--user")
    command.extend(args)
    completed = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    result = {
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }
    if check and completed.returncode != 0:
        raise RuntimeError("systemctl failed: %s" % completed.stderr.strip())
    return result


def render_service_unit(config):
    lines = [
        "[Unit]",
        "Description=CPA auth file cleaner run",
        "Wants=network-online.target",
        "After=network-online.target",
        "",
        "[Service]",
        "Type=oneshot",
        "WorkingDirectory=%s" % quote_systemd_arg(config["repo_root"]),
    ]
    if config["env_file"]:
        lines.append("EnvironmentFile=-%s" % quote_systemd_arg(config["env_file"]))
    if config["service_user"]:
        lines.append("User=%s" % clean_unit_value(config["service_user"], "service user"))
    lines.extend(
        [
            "ExecStart=%s" % " ".join(exec_start_args(config)),
            "SyslogIdentifier=%s" % config["name"],
            "",
        ]
    )
    return "\n".join(lines)


def render_timer_unit(config):
    return "\n".join(
        [
            "[Unit]",
            "Description=Run CPA auth file cleaner every %s" % config["interval"],
            "",
            "[Timer]",
            "OnBootSec=%s" % config["interval"],
            "OnUnitActiveSec=%s" % config["interval"],
            "AccuracySec=10s",
            "Persistent=true",
            "Unit=%s" % config["service_file"],
            "",
            "[Install]",
            "WantedBy=timers.target",
            "",
        ]
    )


def exec_start_args(config):
    values = [
        config["python"],
        config["tools_entry"],
        "cpa-auth-file-cleaner",
    ]
    values.extend(config["run_args"])
    return [quote_systemd_arg(value) for value in values]


def render_service_result(result, as_json=False):
    if as_json:
        return json.dumps(result, ensure_ascii=False, indent=2)
    lines = [
        "Action: %s" % result["action"],
        "Service: %s" % result["service_name"],
        "Timer interval: %s" % result["interval"],
        "Service unit: %s" % result["service_path"],
        "Timer unit: %s" % result["timer_path"],
        "Environment file: %s" % (result["env_file"] or "-"),
        "User service: %s" % result["user_service"],
    ]
    if result["commands"]:
        lines.append("")
        lines.append("Commands:")
        for item in result["commands"]:
            lines.append("  - %s -> %s" % (" ".join(item["command"]), item["returncode"]))
    if result["action"] == "print":
        lines.append("")
        lines.append("Service unit:")
        lines.append(result["service_unit"])
        lines.append("")
        lines.append("Timer unit:")
        lines.append(result["timer_unit"])
    return "\n".join(lines)


def discover_repo_root():
    current = Path(__file__).resolve()
    for candidate in [current] + list(current.parents):
        if (candidate / "tools.py").exists():
            return candidate
    return Path.cwd()


def normalize_service_name(value):
    name = value.strip()
    if name.endswith(".service"):
        name = name[:-8]
    if name.endswith(".timer"):
        name = name[:-6]
    if not re.match(r"^[A-Za-z0-9_.@-]+$", name or ""):
        raise ValueError("invalid service name: %s" % value)
    return name


def clean_unit_value(value, label):
    text = str(value or "").strip()
    if "\n" in text or "\r" in text:
        raise ValueError("%s must not contain line breaks" % label)
    return text


def quote_systemd_arg(value):
    text = clean_unit_value(value, "systemd argument").replace("%", "%%")
    if text and re.match(r"^[A-Za-z0-9_@+=:,.%/-]+$", text):
        return text
    return '"%s"' % text.replace("\\", "\\\\").replace('"', '\\"')


def default_service_python():
    return sys.executable or "/usr/bin/python3"
