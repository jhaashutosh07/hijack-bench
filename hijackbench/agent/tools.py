"""Tool schemas + sandboxed executors.

SINK tools (send_email, http_post) are the exfiltration channel the attacker aims
for. They are FULLY SIMULATED: they record the call into AgentState and return a
benign confirmation. No network, no email, no file writes ever happen.

Content tools (read_url, read_file, list_records) return scenario-provided,
pre-rendered content — which is where injected payloads live.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .state import AgentState

SINK_TOOLS = {"send_email", "http_post"}


@dataclass
class ToolContext:
    state: AgentState
    # Pre-rendered untrusted content: url/path/key -> text (payload already injected).
    resources: dict = field(default_factory=dict)


# ---- schemas (OpenAI function-calling format) ------------------------------
TOOL_SCHEMAS: dict[str, dict] = {
    "read_url": {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Fetch the text content of a web page.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    "read_file": {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a local file's text content.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    "list_records": {
        "type": "function",
        "function": {
            "name": "list_records",
            "description": "Query the internal records system and return matching rows.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
    "send_email": {
        "type": "function",
        "function": {
            "name": "send_email",
            "description": "Send an email.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to": {"type": "string"},
                    "subject": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["to", "body"],
            },
        },
    },
    "http_post": {
        "type": "function",
        "function": {
            "name": "http_post",
            "description": "Send an HTTP POST request with a data payload.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}, "data": {"type": "string"}},
                "required": ["url", "data"],
            },
        },
    },
}


# ---- executors -------------------------------------------------------------
def _read_url(args: dict, ctx: ToolContext) -> str:
    url = args.get("url", "")
    return ctx.resources.get(url, f"HTTP 404: no page found at {url!r}")


def _read_file(args: dict, ctx: ToolContext) -> str:
    path = args.get("path", "")
    return ctx.resources.get(path, f"Error: file not found: {path!r}")


def _list_records(args: dict, ctx: ToolContext) -> str:
    # The scenario provides poisoned tool output under the "records" resource key.
    return ctx.resources.get("records", "No records found.")


def _send_email(args: dict, ctx: ToolContext) -> str:
    ctx.state.record_sink("send_email", args)
    return f"Email sent to {args.get('to', '?')}."


def _http_post(args: dict, ctx: ToolContext) -> str:
    ctx.state.record_sink("http_post", args)
    return f"POST to {args.get('url', '?')} returned 200 OK."


EXECUTORS = {
    "read_url": _read_url,
    "read_file": _read_file,
    "list_records": _list_records,
    "send_email": _send_email,
    "http_post": _http_post,
}


def schemas_for(tool_names: list[str]) -> list[dict]:
    return [TOOL_SCHEMAS[n] for n in tool_names if n in TOOL_SCHEMAS]


def execute(name: str, args: dict, ctx: ToolContext) -> str:
    if name not in EXECUTORS:
        return f"Error: unknown tool {name!r}"
    ctx.state.record_tool_call(name, args)
    return EXECUTORS[name](args, ctx)
