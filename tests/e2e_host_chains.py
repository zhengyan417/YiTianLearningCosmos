import asyncio
import json
import os
import socket
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from urllib.parse import urlparse

from dotenv import load_dotenv
from google.genai import types

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT_UP = PROJECT_ROOT.parent
for candidate in (PROJECT_ROOT, PROJECT_ROOT_UP):
    c = str(candidate)
    if c not in sys.path:
        sys.path.insert(0, c)

from a2a_client.client_host_agent.host_agent import HostAgent
from core.async_utils import create_http_client


AGENT_SPECS = [
    {"name": "file_parse", "module": "file_parse_agent", "port": 10001},
    {"name": "code", "module": "code_agent", "port": 10002},
    {"name": "rag", "module": "rag_agent", "port": 10003},
    {"name": "search", "module": "search_agent", "port": 10004},
    {"name": "research", "module": "research_agent", "port": 10005},
]


class DummyToolContext:
    def __init__(self) -> None:
        self.state: dict[str, Any] = {}
        self.actions = SimpleNamespace(
            skip_summarization=False,
            escalate=False,
        )
        self._artifacts: dict[str, types.Part] = {}

    async def list_artifacts(self) -> list[str]:
        return list(self._artifacts.keys())

    async def load_artifact(self, artifact_name: str) -> types.Part | None:
        return self._artifacts.get(artifact_name)

    async def save_artifact(self, artifact_name: str, artifact: types.Part) -> None:
        self._artifacts[artifact_name] = artifact


def _is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def _flatten_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    if isinstance(result, list):
        chunks: list[str] = []
        for item in result:
            if isinstance(item, str):
                chunks.append(item)
            elif isinstance(item, dict):
                chunks.append(json.dumps(item, ensure_ascii=False))
            else:
                chunks.append(str(item))
        return "\n".join(chunks)
    if isinstance(result, dict):
        return json.dumps(result, ensure_ascii=False)
    return str(result)


def _normalize_netloc(url: str) -> str:
    parsed = urlparse(url if "://" in url else f"http://{url}")
    return parsed.netloc.lower().rstrip("/")


def _find_agent_name_by_url(host: HostAgent, target_url: str) -> str:
    target_netloc = _normalize_netloc(target_url)
    for name, card in host.cards.items():
        card_url = str(getattr(card, "url", ""))
        if _normalize_netloc(card_url) == target_netloc:
            return name
    raise RuntimeError(
        f"cannot map url {target_url} to card name, cards={list(host.cards.keys())}"
    )


async def _wait_agents_registered(host: HostAgent, expect: int = 5, timeout_s: int = 60) -> None:
    deadline = asyncio.get_event_loop().time() + timeout_s
    while asyncio.get_event_loop().time() < deadline:
        if len(host.cards) >= expect:
            return
        await asyncio.sleep(0.5)
    raise TimeoutError(f"agent cards not ready in {timeout_s}s, current={list(host.cards.keys())}")


def _start_agents_if_needed() -> tuple[list[subprocess.Popen], list[Any]]:
    logs_dir = PROJECT_ROOT / "logs" / "e2e_chain_run"
    logs_dir.mkdir(parents=True, exist_ok=True)
    started: list[subprocess.Popen] = []
    opened_files: list[Any] = []

    for spec in AGENT_SPECS:
        if _is_port_open(spec["port"]):
            continue

        out_path = logs_dir / f"{spec['name']}.log"
        err_path = logs_dir / f"{spec['name']}.err.log"
        out_f = open(out_path, "ab")
        err_f = open(err_path, "ab")
        opened_files.extend([out_f, err_f])

        cmd = [
            sys.executable,
            "-m",
            spec["module"],
            "--host",
            "localhost",
            "--port",
            str(spec["port"]),
        ]
        proc = subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            stdout=out_f,
            stderr=err_f,
        )
        started.append(proc)

    return started, opened_files


async def _wait_ports_ready(timeout_s: int = 90) -> None:
    deadline = asyncio.get_event_loop().time() + timeout_s
    required_ports = [spec["port"] for spec in AGENT_SPECS]
    while asyncio.get_event_loop().time() < deadline:
        if all(_is_port_open(port) for port in required_ports):
            return
        await asyncio.sleep(0.8)
    not_ready = [port for port in required_ports if not _is_port_open(port)]
    raise TimeoutError(f"ports not ready in {timeout_s}s, missing={not_ready}")


def _stop_processes(processes: list[subprocess.Popen], opened_files: list[Any]) -> None:
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=8)
        except Exception:
            if proc.poll() is None:
                proc.kill()
    for f in opened_files:
        try:
            f.close()
        except Exception:
            pass


async def main() -> int:
    load_dotenv()
    bootstrap_agents = os.getenv("E2E_BOOTSTRAP_AGENTS", "true").lower() == "true"

    started_processes: list[subprocess.Popen] = []
    opened_files: list[Any] = []
    if bootstrap_agents:
        started_processes, opened_files = _start_agents_if_needed()
        await _wait_ports_ready(timeout_s=90)

    http_client = create_http_client()
    try:
        file_parse_url = os.getenv("FILE_PARSE_AGENT_URL", "http://localhost:10001")
        code_url = os.getenv("CODE_AGENT_URL", "http://localhost:10002")
        rag_url = os.getenv("RAG_AGENT_URL", "http://localhost:10003")
        search_url = os.getenv("SEARCH_AGENT_URL", "http://localhost:10004")
        research_url = os.getenv("RESEARCH_AGENT_URL", "http://localhost:10005")

        host = HostAgent(
            remote_agent_addresses=[
                file_parse_url,
                code_url,
                rag_url,
                search_url,
                research_url,
            ],
            http_client=http_client,
        )
        await _wait_agents_registered(host, expect=5, timeout_s=60)

        search_agent = _find_agent_name_by_url(host, search_url)
        research_agent = _find_agent_name_by_url(host, research_url)
        file_agent = _find_agent_name_by_url(host, file_parse_url)

        ctx = DummyToolContext()
        results: dict[str, dict[str, Any]] = {}

        weather_raw = await host.send_message(
            agent_name=search_agent,
            message="帮我查询一下北京的天气",
            tool_context=ctx,
        )
        weather_text = _flatten_result(weather_raw)
        weather_ok = (
            bool(weather_text.strip())
            and "通信出现故障" not in weather_text
            and any(k in weather_text for k in ["天气", "温度", "气温", "°C", "C"])
        )
        results["weather"] = {
            "ok": weather_ok,
            "agent": search_agent,
            "preview": weather_text[:800],
        }

        research_raw = await host.send_message(
            agent_name=research_agent,
            message="帮我研究一下A2A与MCP的关系",
            tool_context=ctx,
        )
        research_text = _flatten_result(research_raw)
        research_ok = (
            bool(research_text.strip())
            and "通信出现故障" not in research_text
            and len(research_text.strip()) > 80
        )
        results["research"] = {
            "ok": research_ok,
            "agent": research_agent,
            "preview": research_text[:1400],
        }

        sample_pdf = PROJECT_ROOT / "file_parse_agent" / "attention.pdf"
        if not sample_pdf.exists():
            raise FileNotFoundError(f"sample file not found: {sample_pdf}")
        file_bytes = sample_pdf.read_bytes()
        await ctx.save_artifact(
            sample_pdf.name,
            types.Part(
                inline_data=types.Blob(
                    mime_type="application/pdf",
                    data=file_bytes,
                )
            ),
        )
        file_raw = await host.send_message(
            agent_name=file_agent,
            message="这个文件讲了什么?",
            tool_context=ctx,
            file_path=None,
        )
        file_text = _flatten_result(file_raw)
        file_ok = (
            bool(file_text.strip())
            and "通信出现故障" not in file_text
            and "请上传" not in file_text
            and len(file_text.strip()) > 40
        )
        results["file_parse"] = {
            "ok": file_ok,
            "agent": file_agent,
            "preview": file_text[:1400],
        }

        print(
            json.dumps(
                {
                    "registered_agents": list(host.cards.keys()),
                    "results": results,
                },
                ensure_ascii=False,
                indent=2,
            )
        )

        return 0 if all(item["ok"] for item in results.values()) else 1
    finally:
        # Let process teardown close sockets to avoid noisy async-generator warnings
        # from the underlying SSE stream stack on Windows.
        if bootstrap_agents:
            _stop_processes(started_processes, opened_files)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
