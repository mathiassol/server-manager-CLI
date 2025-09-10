import json
import os
import subprocess
import sys
import time
from datetime import datetime
import threading
from pathlib import Path
import platform
import psutil
from typing import Optional, List, Dict, Callable, Any

SCRIPT_DIR = Path(__file__).parent
SERVERS_FILE = SCRIPT_DIR / "servers.json"
SERVERS_DIR = SCRIPT_DIR / "servers"
LOGS_DIR = SCRIPT_DIR / "logs"

LOGS_DIR.mkdir(exist_ok=True)
SERVERS_DIR.mkdir(exist_ok=True)


def clear_terminal() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def safe_run(func: Callable[..., Any], *args, **kwargs) -> Optional[Any]:
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[ERROR] {func.__name__}: {e}")
        return None


class Server:
    EXT_MAP = {".py": "python", ".js": "node", ".mjs": "node"}

    def __init__(self, name: str, path: str, server_type: str, auto_restart: bool = True) -> None:
        self.name = name
        self.path = Path(path)
        self.type = server_type
        self.auto_restart = auto_restart

        self.process: Optional[subprocess.Popen] = None
        self.log_file = LOGS_DIR / f"{self.name}.log"
        self.last_usage: Dict[str, float] = {"cpu": 0.0, "mem": 0.0}

        self.monitor_enabled = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.monitor_stop = threading.Event()

        self.restart_thread: Optional[threading.Thread] = None
        self.restart_stop = threading.Event()
        self.max_retries = 3
        self.retry_count = 0

    def is_running(self) -> bool:
        return bool(self.process and self.process.poll() is None)

    def _rotate_log(self) -> None:
        if self.log_file.exists():
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            rotated = LOGS_DIR / f"{self.name}_{timestamp}.log"
            try:
                self.log_file.rename(rotated)
            except Exception:
                try:
                    rotated.write_bytes(self.log_file.read_bytes())
                    self.log_file.unlink(missing_ok=True)
                except Exception as e:
                    print(f"Failed to rotate log for {self.name}: {e}")

    def start(self) -> None:
        if self.is_running():
            print(f"{self.name} is already running.")
            return

        cmd = {
            "python": [sys.executable, str(self.path)],
            "node": ["node", str(self.path)]
        }.get(self.type)

        if not cmd:
            print(f"Unknown server type for {self.name}")
            return

        try:
            self._rotate_log()
            log_handle = open(self.log_file, "w", buffering=1)
            self.process = subprocess.Popen(
                cmd,
                stdout=log_handle,
                stderr=subprocess.STDOUT,
                stdin=subprocess.PIPE,
                text=True,
                cwd=self.path.parent
            )
            print(f"Server {self.name} started (PID: {self.process.pid}). Logs: {self.log_file}")

            if self.monitor_enabled:
                self.start_monitoring()

            if self.auto_restart:
                self.start_restart_monitor()
        except Exception as e:
            print(f"Failed to start {self.name}: {e}")

    def start_restart_monitor(self) -> None:
        if self.restart_thread and self.restart_thread.is_alive():
            return
        self.restart_stop.clear()
        self.retry_count = 0

        def restart_loop():
            while not self.restart_stop.is_set():
                if self.process and (ret := self.process.poll()) is not None:
                    print(f"{self.name} crashed with exit code {ret}.")
                    if self.retry_count < self.max_retries:
                        self.retry_count += 1
                        print(f"Restarting {self.name} (attempt {self.retry_count}/{self.max_retries})...")
                        time.sleep(1)
                        self.start()
                    else:
                        print(f"{self.name} reached max restart attempts. Not restarting.")
                        break
                time.sleep(1)

        self.restart_thread = threading.Thread(target=restart_loop, daemon=True)
        self.restart_thread.start()

    def stop_restart_monitor(self) -> None:
        self.restart_stop.set()
        if self.restart_thread:
            self.restart_thread.join(timeout=1)

    def stop(self) -> None:
        self.stop_restart_monitor()
        if self.is_running():
            self.stop_monitoring()
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            print(f"Server {self.name} stopped.")
        else:
            print(f"{self.name} is not running.")

    def restart(self) -> None:
        self.stop()
        time.sleep(1)
        self.start()

    def send_input(self, text: str) -> None:
        if self.is_running() and self.process and self.process.stdin:
            try:
                self.process.stdin.write(text + "\n")
                self.process.stdin.flush()
            except Exception as e:
                print(f"Failed to send input to {self.name}: {e}")
        else:
            print(f"{self.name} is not running.")

    def open_terminal(self) -> None:
        if not self.log_file.exists():
            print(f"No log file found for {self.name}. Start the server first.")
            return
        if not self.is_running():
            print(f"{self.name} is not running.")
            return

        stop_flag = threading.Event()
        clear_terminal()

        def log_reader():
            try:
                with open(self.log_file, "r") as f:
                    f.seek(0)
                    for line in f:
                        print(line, end="")
                    while not stop_flag.is_set():
                        line = f.readline()
                        if line:
                            print(line, end="")
                        else:
                            time.sleep(0.1)
            except Exception as e:
                print(f"Error reading logs for {self.name}: {e}")

        reader_thread = threading.Thread(target=log_reader, daemon=True)
        reader_thread.start()

        print(f"\nInteractive terminal for {self.name} (type commands and press Enter, 'exit' to quit)")
        try:
            while True:
                user_input = input()
                if user_input.strip().lower() == "exit":
                    break
                self.send_input(user_input)
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            stop_flag.set()
            reader_thread.join()
            clear_terminal()
            print(f"Exited interactive terminal for {self.name}.")

    # Monitoring
    def start_monitoring(self) -> None:
        if not self.is_running():
            return
        if self.monitor_thread and self.monitor_thread.is_alive():
            return
        self.monitor_stop.clear()

        def monitor_loop():
            try:
                proc = psutil.Process(self.process.pid)
                while not self.monitor_stop.is_set() and proc.is_running():
                    cpu = proc.cpu_percent(interval=1.0)
                    mem = proc.memory_info().rss / 1024 / 1024
                    self.last_usage = {"cpu": cpu, "mem": mem}
            except Exception:
                pass

        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()

    def stop_monitoring(self) -> None:
        self.monitor_stop.set()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=1)

    def show_usage(self) -> None:
        if not self.is_running():
            print(f"{self.name} is not running.")
            return

        stop_flag = threading.Event()

        def usage_loop():
            while not stop_flag.is_set() and self.is_running():
                clear_terminal()
                print(f"Server: {self.name}")
                print(f"PID: {self.process.pid}")
                print(f"CPU Usage: {self.last_usage['cpu']:.1f}%")
                print(f"Memory Usage: {self.last_usage['mem']:.1f} MB")
                print("\nPress Enter to exit usage view...")
                time.sleep(1)

        t = threading.Thread(target=usage_loop, daemon=True)
        t.start()

        try:
            input()
        except KeyboardInterrupt:
            pass
        finally:
            stop_flag.set()
            t.join()
            clear_terminal()
            print(f"Exited usage view for {self.name}.")


class ServerManager:
    def __init__(self) -> None:
        self.servers: List[Server] = []
        self.load_servers()

    def load_servers(self) -> None:
        if not SERVERS_FILE.exists():
            return
        try:
            with open(SERVERS_FILE, "r") as f:
                data = json.load(f)
            for s in data:
                srv = Server(
                    s['name'], s['path'], s['type'], s.get("auto_restart", True)
                )
                srv.monitor_enabled = s.get("monitor", False)
                self.servers.append(srv)
        except Exception as e:
            print(f"Failed to load servers.json: {e}")

    def save_servers(self) -> None:
        try:
            with open(SERVERS_FILE, "w") as f:
                json.dump([{
                    "name": s.name,
                    "path": str(s.path),
                    "type": s.type,
                    "auto_restart": s.auto_restart,
                    "monitor": s.monitor_enabled,
                } for s in self.servers], f, indent=4)
        except Exception as e:
            print(f"Failed to save servers.json: {e}")

    def add_server(self, file_path: str) -> None:
        p = Path(file_path)
        if not p.exists():
            print("File does not exist!")
            return
        server_type = Server.EXT_MAP.get(p.suffix.lower())
        if not server_type:
            print("Unsupported file type!")
            return
        self.servers.append(Server(p.stem, str(p), server_type))
        self.save_servers()
        print(f"Server {p.stem} added. (Not started)")

    def remove_server(self, name: str) -> None:
        s = self.get_server(name)
        if s:
            s.stop()
            self.servers.remove(s)
            self.save_servers()
            print(f"Server {name} removed.")
        else:
            print("Server not found.")

    def get_server(self, name: str) -> Optional[Server]:
        return next((s for s in self.servers if s.name == name), None)

    def list_servers(self) -> None:
        for s in self.servers:
            status = "running" if s.is_running() else "stopped"
            cpu = f"{s.last_usage['cpu']:.1f}%" if s.is_running() else "-"
            mem = f"{s.last_usage['mem']:.1f} MB" if s.is_running() else "-"
            print(f"{s.name} ({s.type}) - {status} | CPU: {cpu} | MEM: {mem}")

    def create_server(self, name: str, server_type: str) -> None:
        folder = SERVERS_DIR / name
        if folder.exists():
            print(f"Server folder '{name}' already exists!")
            return
        folder.mkdir(parents=True)

        ext = ""
        content = ""
        if server_type.lower() in ("py", "python"):
            ext = ".py"
            content = "# Default Python server\nprint('Server running')\nwhile True:\n    pass\n"
            srv_type = "python"
        elif server_type.lower() in ("node", "js"):
            ext = ".js"
            content = "// Default Node.js server\nconsole.log('Server running');\nsetInterval(()=>{},1000);\n"
            srv_type = "node"
        else:
            ext = f".{server_type}"
            content = f"// Custom server file: {ext}\nconsole.log('Server running');\n"
            srv_type = "node"

        server_file = folder / f"{name}{ext}"
        with open(server_file, "w") as f:
            f.write(content)

        self.servers.append(Server(name, str(server_file), srv_type))
        self.save_servers()
        print(f"Created server '{name}' with file '{server_file}'.")

    def open_server(self, name: str) -> None:
        s = self.get_server(name)
        if not s:
            print("Server not found.")
            return
        path = str(Path(s.path))

        if platform.system() == "Windows":
            try:
                print("Opening 'Choose another app' menu. Select an editor to open the server file.")
                subprocess.run(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", path])
            except Exception as e:
                print(f"Failed to open 'Open With' dialog: {e}")
        elif platform.system() == "Darwin":
            subprocess.run(["open", path])
        else:
            subprocess.run(["xdg-open", path])


HELP_TEXT = """
Available commands:
  create <name> <py|node|custom>  Create a default server
  open <name>                      Open server file in editor
  add <path>                       Add an existing server (not started automatically)
  remove <name>                    Remove a server
  start <name>                     Start a server (headless, logs to file)
  stop <name>                      Stop a server
  restart <name>                   Restart a server
  log <name>                       Open interactive log terminal
  send <name> <text>               Send input to a headless server
  list                             Show all servers
  usage <name>                     Show real-time CPU/memory usage
  monitor <name> on|off            Enable/disable background monitoring
  cls                              Clear the terminal
  exit                             Quit the manager
  help                             Show this help message
"""


def main() -> None:
    manager = ServerManager()
    commands: Dict[str, Callable[..., Any]] = {
        "add": manager.add_server,
        "remove": manager.remove_server,
        "start": lambda n: safe_run(manager.get_server(n).start) if manager.get_server(n) else print("Server not found."),
        "stop": lambda n: safe_run(manager.get_server(n).stop) if manager.get_server(n) else print("Server not found."),
        "restart": lambda n: safe_run(manager.get_server(n).restart) if manager.get_server(n) else print("Server not found."),
        "log": lambda n: safe_run(manager.get_server(n).open_terminal) if manager.get_server(n) else print("Server not found."),
        "send": lambda n, *msg: safe_run(manager.get_server(n).send_input, " ".join(msg)) if manager.get_server(n) else print("Server not found."),
        "list": manager.list_servers,
        "cls": clear_terminal,
        "help": lambda: print(HELP_TEXT),
        "exit": lambda: sys.exit(0),
        "create": lambda n, t: manager.create_server(n, t),
        "open": lambda n: manager.open_server(n),
        "path": lambda n: print(manager.get_server(n).path) if manager.get_server(n) else print("Server not found."),
        "usage": lambda n: safe_run(manager.get_server(n).show_usage) if manager.get_server(n) else print("Server not found."),
        "monitor": lambda n, state: (
            setattr(manager.get_server(n), "monitor_enabled", (state.lower() == "on")) or
            (manager.get_server(n).start_monitoring() if state.lower() == "on" else manager.get_server(n).stop_monitoring()) or
            manager.save_servers()
        ) if manager.get_server(n) else print("Server not found."),
    }

    print("Server Manager CLI. Type 'help' for commands.")
    while True:
        try:
            user_input = input("ServerManager> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nExiting.")
            break

        if not user_input:
            continue

        parts = user_input.split()
        cmd, *args = parts
        action = cmd.lower()

        func = commands.get(action)
        if func:
            try:
                func(*args)
            except TypeError:
                print("Incorrect usage. Type 'help' for commands.")
        else:
            print("Unknown command. Type 'help' for commands.")


if __name__ == "__main__":
    main()
