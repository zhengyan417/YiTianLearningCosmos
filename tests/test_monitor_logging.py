import json
from core.a2a_monitor import get_monitor


def test_monitor_log_entry_serialization(tmp_path, monkeypatch):
    # 使用临时日志目录
    monkeypatch.setenv("ENABLE_A2A_MONITORING", "False")
    m = get_monitor()
    m.log_dir = tmp_path
    m.log_file = tmp_path / "a2a_comm.log"

    entry = m.log_communication(
        direction="client_to_server",
        endpoint_type="request",
        data={"hello": "world"},
        context_id="ctx",
        task_id="task",
        message_id="msg",
        agent_name="agent",
    )
    # 断言关键字段
    assert entry["direction"] == "client_to_server"
    assert entry["data_size_bytes"] > 0

    # 文件内容可解析 JSON
    content = m.log_file.read_text(encoding="utf-8").splitlines()[-1]
    json_part = content.split(" - ", 1)[1] if " - " in content else content
    parsed = json.loads(json_part)
    assert parsed["agent_name"] == "agent"
