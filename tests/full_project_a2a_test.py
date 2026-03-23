import json
import os
import shutil
import socket
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_TS = datetime.now().strftime("%Y%m%d_%H%M%S")
RUN_DIR = PROJECT_ROOT / "logs" / "full_project_test" / RUN_TS
SERVERS_DIR = RUN_DIR / "servers"
CLIENT_DIR = RUN_DIR / "clients"
ARTIFACTS_DIR = RUN_DIR / "artifacts"
RUNNER_LOG = RUN_DIR / "runner.log"

AGENTS = [
    {"name": "file_parse", "module": "file_parse_agent", "port": 10001},
    {"name": "code", "module": "code_agent", "port": 10002},
    {"name": "rag", "module": "rag_agent", "port": 10003},
    {"name": "search", "module": "search_agent", "port": 10004},
    {"name": "research", "module": "research_agent", "port": 10005},
]

ROUND_PROMPTS: dict[str, list[dict[str, str]]] = {
    "file_parse": [
        {
            "prompt": "请先总结这个附件文档讲了什么，再给出3个关键词。",
            "file": str(PROJECT_ROOT / "file_parse_agent" / "attention.pdf"),
        },
        {"prompt": "请再用三句话总结上面的内容。", "file": ""},
    ],
    "code": [
        {"prompt": "请用Python写一个二分查找函数，并说明时间复杂度。", "file": ""},
        {"prompt": "请再补一个最小可运行测试用例。", "file": ""},
    ],
    "rag": [
        {"prompt": "高血压常见症状有哪些？", "file": ""},
        {"prompt": "哪些情况需要尽快去医院？", "file": ""},
    ],
    "search": [
        {"prompt": "帮我查询北京今天的天气。", "file": ""},
        {"prompt": "再查询上海今天的天气。", "file": ""},
    ],
    "research": [
        {"prompt": "请研究A2A与MCP的关系，输出结构化结论。", "file": ""},
        {"prompt": "再给出3条后续可验证的研究问题。", "file": ""},
    ],
}


@dataclass
class ProcessRecord:
    name: str
    module: str
    port: int
    pid: int
    log_file: str
    err_file: str
    started: bool
    healthy: bool
    health_status: str


def log(msg: str) -> None:
    line = f"[{datetime.now().isoformat(timespec='seconds')}] {msg}"
    print(line)
    RUNNER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUNNER_LOG.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def discover_venv_pythons() -> list[Path]:
    pythons: list[Path] = []
    for cfg in PROJECT_ROOT.rglob("pyvenv.cfg"):
        if any(part.startswith(".git") for part in cfg.parts):
            continue
        root = cfg.parent
        py = root / "Scripts" / "python.exe"
        if not py.exists():
            py = root / "bin" / "python"
        if py.exists():
            pythons.append(py.resolve())
    dedup = sorted(set(pythons))
    return dedup


def port_open(port: int, host: str = "127.0.0.1", timeout_s: float = 0.5) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        return sock.connect_ex((host, port)) == 0


def wait_port(port: int, timeout_s: int = 90) -> bool:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if port_open(port):
            return True
        time.sleep(0.8)
    return False


def http_health(url: str, timeout_s: int = 8) -> tuple[bool, str]:
    try:
        with urlopen(url, timeout=timeout_s) as resp:
            code = getattr(resp, "status", None)
            body = resp.read(300).decode("utf-8", errors="ignore")
            return True, f"HTTP {code}; body={body}"
    except HTTPError as e:
        if e.code in (200, 204, 405):
            return True, f"HTTP {e.code}"
        return False, f"HTTPError: {e}"
    except URLError as e:
        return False, f"URLError: {e}"
    except Exception as e:
        return False, f"Error: {e}"


def ensure_dirs() -> None:
    for d in [RUN_DIR, SERVERS_DIR, CLIENT_DIR, ARTIFACTS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def start_servers(py_exec: Path, env: dict[str, str]) -> tuple[list[subprocess.Popen], list[ProcessRecord]]:
    procs: list[subprocess.Popen] = []
    records: list[ProcessRecord] = []
    for spec in AGENTS:
        out_f = (SERVERS_DIR / f"{spec['name']}.out.log").open("w", encoding="utf-8")
        err_f = (SERVERS_DIR / f"{spec['name']}.err.log").open("w", encoding="utf-8")
        cmd = [
            str(py_exec),
            "-m",
            str(spec["module"]),
            "--host",
            "127.0.0.1",
            "--port",
            str(spec["port"]),
        ]
        log(f"启动服务端: {' '.join(cmd)}")
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=out_f,
            stderr=err_f,
            env=env,
            text=True,
        )
        procs.append(proc)

    for proc, spec in zip(procs, AGENTS):
        started = wait_port(int(spec["port"]), timeout_s=120)
        healthy, detail = http_health(f"http://127.0.0.1:{spec['port']}/")
        records.append(
            ProcessRecord(
                name=str(spec["name"]),
                module=str(spec["module"]),
                port=int(spec["port"]),
                pid=proc.pid,
                log_file=str((SERVERS_DIR / f"{spec['name']}.out.log").resolve()),
                err_file=str((SERVERS_DIR / f"{spec['name']}.err.log").resolve()),
                started=started,
                healthy=healthy,
                health_status=detail,
            )
        )
        log(
            f"服务端状态 {spec['name']}: started={started}, healthy={healthy}, detail={detail}"
        )
    return procs, records


def run_cli_dialog(py_exec: Path, agent_name: str, port: int, env: dict[str, str]) -> dict[str, Any]:
    rounds = ROUND_PROMPTS[agent_name]
    lines: list[str] = []
    for item in rounds:
        lines.append(item["prompt"])
        lines.append(item["file"])
    lines.append(":q")
    user_input = "\n".join(lines) + "\n"

    out_path = CLIENT_DIR / f"{agent_name}.cli.out.log"
    err_path = CLIENT_DIR / f"{agent_name}.cli.err.log"
    cmd = [
        str(py_exec),
        "-m",
        "cli_client",
        "--agent",
        f"http://127.0.0.1:{port}",
        "--session",
        "20260321",
        "--history",
        "True",
    ]
    log(f"运行CLI多轮对话: {' '.join(cmd)}")
    start_t = time.time()
    cp = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        input=user_input,
        text=True,
        capture_output=True,
        env=env,
        timeout=900,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = round(time.time() - start_t, 2)
    stdout = cp.stdout or ""
    stderr = cp.stderr or ""
    out_path.write_text(stdout, encoding="utf-8", errors="ignore")
    err_path.write_text(stderr, encoding="utf-8", errors="ignore")

    ok = (
        cp.returncode == 0
        and "Traceback" not in stdout
        and "Traceback" not in stderr
        and "JSONRPCErrorResponse" not in stdout
        and "error" not in stderr.lower()
    )
    return {
        "agent": agent_name,
        "url": f"http://127.0.0.1:{port}",
        "returncode": cp.returncode,
        "elapsed_sec": elapsed,
        "ok": ok,
        "stdout_log": str(out_path.resolve()),
        "stderr_log": str(err_path.resolve()),
        "stdout_preview": stdout[:800],
        "stderr_preview": stderr[:600],
    }


def run_host_chain(py_exec: Path, env: dict[str, str]) -> dict[str, Any]:
    out_path = CLIENT_DIR / "host_chain.out.log"
    err_path = CLIENT_DIR / "host_chain.err.log"
    cmd = [str(py_exec), "tests/e2e_host_chains.py"]
    host_env = env.copy()
    host_env["E2E_BOOTSTRAP_AGENTS"] = "false"
    log(f"运行Host链路测试: {' '.join(cmd)}")
    start_t = time.time()
    cp = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=host_env,
        timeout=1200,
        encoding="utf-8",
        errors="replace",
    )
    elapsed = round(time.time() - start_t, 2)
    out_path.write_text(cp.stdout, encoding="utf-8", errors="ignore")
    err_path.write_text(cp.stderr, encoding="utf-8", errors="ignore")
    return {
        "returncode": cp.returncode,
        "elapsed_sec": elapsed,
        "ok": cp.returncode == 0,
        "stdout_log": str(out_path.resolve()),
        "stderr_log": str(err_path.resolve()),
        "stdout_preview": (cp.stdout or "")[:1000],
        "stderr_preview": (cp.stderr or "")[:800],
    }


def copy_monitor_logs() -> list[str]:
    copied: list[str] = []
    src = PROJECT_ROOT / "logs" / "a2a_communication"
    if not src.exists():
        return copied
    dst = ARTIFACTS_DIR / "a2a_communication_snapshot"
    dst.mkdir(parents=True, exist_ok=True)
    for p in src.glob("*"):
        if p.is_file():
            target = dst / p.name
            shutil.copy2(p, target)
            copied.append(str(target.resolve()))
    return copied


def run_pytest(py_exec: Path, env: dict[str, str]) -> dict[str, Any]:
    out_path = ARTIFACTS_DIR / "pytest.out.log"
    err_path = ARTIFACTS_DIR / "pytest.err.log"
    cmd = [str(py_exec), "-m", "pytest", "-q"]
    log(f"运行pytest: {' '.join(cmd)}")
    cp = subprocess.run(
        cmd,
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
        env=env,
        timeout=900,
        encoding="utf-8",
        errors="replace",
    )
    out_path.write_text(cp.stdout, encoding="utf-8", errors="ignore")
    err_path.write_text(cp.stderr, encoding="utf-8", errors="ignore")
    return {
        "returncode": cp.returncode,
        "ok": cp.returncode == 0,
        "stdout_log": str(out_path.resolve()),
        "stderr_log": str(err_path.resolve()),
        "stdout_preview": (cp.stdout or "")[:1200],
        "stderr_preview": (cp.stderr or "")[:800],
    }


def terminate_all(procs: list[subprocess.Popen]) -> None:
    for p in procs:
        if p.poll() is None:
            p.terminate()
    time.sleep(2)
    for p in procs:
        if p.poll() is None:
            p.kill()


def main() -> int:
    ensure_dirs()
    venv_pythons = discover_venv_pythons()
    log(f"发现虚拟环境数量: {len(venv_pythons)}")
    for py in venv_pythons:
        log(f"虚拟环境Python: {py}")

    root_venv_py = PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
    if root_venv_py.exists():
        py_exec = root_venv_py.resolve()
    elif venv_pythons:
        py_exec = venv_pythons[0]
    else:
        py_exec = Path(sys.executable).resolve()
    log(f"测试使用Python解释器: {py_exec}")

    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["ENABLE_A2A_MONITORING"] = "true"
    env["A2A_MONITOR_CONSOLE"] = "false"
    env["DEBUG"] = "false"
    env["NO_PROXY"] = "localhost,127.0.0.1"
    env["no_proxy"] = "localhost,127.0.0.1"
    env.pop("HTTP_PROXY", None)
    env.pop("HTTPS_PROXY", None)
    env.pop("ALL_PROXY", None)
    env.pop("http_proxy", None)
    env.pop("https_proxy", None)
    env.pop("all_proxy", None)
    env["FILE_PARSE_AGENT_URL"] = "http://127.0.0.1:10001"
    env["CODE_AGENT_URL"] = "http://127.0.0.1:10002"
    env["RAG_AGENT_URL"] = "http://127.0.0.1:10003"
    env["SEARCH_AGENT_URL"] = "http://127.0.0.1:10004"
    env["RESEARCH_AGENT_URL"] = "http://127.0.0.1:10005"

    procs: list[subprocess.Popen] = []
    server_records: list[ProcessRecord] = []
    cli_results: list[dict[str, Any]] = []

    try:
        procs, server_records = start_servers(py_exec, env)
        for rec in server_records:
            if not rec.started:
                log(f"服务未正常启动: {rec.name}")

        for spec in AGENTS:
            cli_results.append(
                run_cli_dialog(
                    py_exec=py_exec,
                    agent_name=str(spec["name"]),
                    port=int(spec["port"]),
                    env=env,
                )
            )

        host_result = run_host_chain(py_exec, env)
        pytest_result = run_pytest(py_exec, env)
        copied_logs = copy_monitor_logs()

        summary = {
            "run_timestamp": RUN_TS,
            "run_dir": str(RUN_DIR.resolve()),
            "python": str(py_exec),
            "venv_pythons": [str(p) for p in venv_pythons],
            "servers": [asdict(r) for r in server_records],
            "cli_multi_round": cli_results,
            "host_chain": host_result,
            "pytest": pytest_result,
            "copied_a2a_monitor_logs": copied_logs,
        }
        summary_path = RUN_DIR / "summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        log(f"测试汇总已写入: {summary_path.resolve()}")

        all_server_started = all(r.started and r.healthy for r in server_records)
        all_cli_ok = all(item.get("ok") for item in cli_results)
        all_ok = all_server_started and all_cli_ok and host_result["ok"] and pytest_result["ok"]
        log(
            f"总结果: all_server_started={all_server_started}, "
            f"all_cli_ok={all_cli_ok}, host_ok={host_result['ok']}, pytest_ok={pytest_result['ok']}"
        )
        return 0 if all_ok else 1
    finally:
        terminate_all(procs)


if __name__ == "__main__":
    raise SystemExit(main())
