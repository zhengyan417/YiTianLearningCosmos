"""
流式/非流式接口约定
- 统一 endpoint_type 与协议版本号
"""

STREAM_PROTOCOL_VERSION = "1.0"

ENDPOINT_REQUEST = "request"
ENDPOINT_RESPONSE = "response"
ENDPOINT_STREAM_CHUNK = "stream_chunk"
ENDPOINT_ERROR = "error"


def normalize_endpoint_type(obj) -> str:
    """根据事件对象判断端点类型（简化版）。"""
    if hasattr(obj, "status"):
        return ENDPOINT_STREAM_CHUNK
    return ENDPOINT_RESPONSE
