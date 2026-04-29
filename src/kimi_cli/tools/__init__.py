import json
from typing import cast

import streamingjson  # type: ignore[reportMissingTypeStubs]
from kaos.path import KaosPath
from kosong.utils.typing import JsonType

from kimi_cli.utils.string import shorten_middle


class SkipThisTool(Exception):
    """Raised when a tool decides to skip itself from the loading process."""

    pass


def extract_key_argument(json_content: str | streamingjson.Lexer, tool_name: str) -> str | None:
    if isinstance(json_content, streamingjson.Lexer):
        json_str = json_content.complete_json()
    else:
        json_str = json_content
    try:
        curr_args: JsonType = json.loads(json_str, strict=False)
    except json.JSONDecodeError:
        return None
    if not curr_args:
        return None
    key_argument: str = ""
    match tool_name:
        case "Agent":
            if not isinstance(curr_args, dict) or not curr_args.get("description"):
                return None
            key_argument = str(curr_args["description"])
        case "SendDMail":
            return None
        case "Think":
            if not isinstance(curr_args, dict) or not curr_args.get("thought"):
                return None
            key_argument = str(curr_args["thought"])
        case "SetTodoList":
            return None
        case "Shell":
            if not isinstance(curr_args, dict) or not curr_args.get("command"):
                return None
            key_argument = str(curr_args["command"])
        case "TaskOutput":
            if not isinstance(curr_args, dict) or not curr_args.get("task_id"):
                return None
            key_argument = str(curr_args["task_id"])
        case "TaskList":
            if not isinstance(curr_args, dict):
                return None
            key_argument = "active" if curr_args.get("active_only", True) else "all"
        case "TaskStop":
            if not isinstance(curr_args, dict) or not curr_args.get("task_id"):
                return None
            key_argument = str(curr_args["task_id"])
        case "ReadFile":
            if not isinstance(curr_args, dict) or not curr_args.get("path"):
                return None
            key_argument = _normalize_path(str(curr_args["path"]))
        case "ReadMediaFile":
            if not isinstance(curr_args, dict) or not curr_args.get("path"):
                return None
            key_argument = _normalize_path(str(curr_args["path"]))
        case "Glob":
            if not isinstance(curr_args, dict) or not curr_args.get("pattern"):
                return None
            key_argument = str(curr_args["pattern"])
        case "Grep":
            if not isinstance(curr_args, dict) or not curr_args.get("pattern"):
                return None
            key_argument = str(curr_args["pattern"])
        case "WriteFile":
            if not isinstance(curr_args, dict) or not curr_args.get("path"):
                return None
            key_argument = _normalize_path(str(curr_args["path"]))
        case "StrReplaceFile":
            if not isinstance(curr_args, dict) or not curr_args.get("path"):
                return None
            key_argument = _normalize_path(str(curr_args["path"]))
        case "SearchWeb":
            if not isinstance(curr_args, dict) or not curr_args.get("query"):
                return None
            key_argument = str(curr_args["query"])
        case "FetchURL":
            if not isinstance(curr_args, dict) or not curr_args.get("url"):
                return None
            key_argument = str(curr_args["url"])
        case "BrowserNavigate":
            if not isinstance(curr_args, dict) or not curr_args.get("url"):
                return None
            key_argument = str(curr_args["url"])
        case "BrowserClick":
            if not isinstance(curr_args, dict) or not curr_args.get("selector"):
                return None
            key_argument = str(curr_args["selector"])
        case "BrowserType":
            if not isinstance(curr_args, dict) or not curr_args.get("selector"):
                return None
            key_argument = str(curr_args["selector"])
        case "BrowserScroll":
            if not isinstance(curr_args, dict):
                return None
            key_argument = curr_args.get("direction", "down")
        case "BrowserScreenshot":
            return None
        case "BrowserExtract":
            return None
        case "BrowserCloseTool" | "BrowserStop":
            return None
        case "BrowserEvaluate":
            if not isinstance(curr_args, dict) or not curr_args.get("script"):
                return None
            key_argument = str(curr_args["script"])[:50]
        case "BrowserGetHTML":
            return None
        case "BrowserNetworkStart":
            if not isinstance(curr_args, dict):
                return None
            key_argument = str(curr_args.get("url_pattern", "**"))
        case "BrowserNetworkList" | "BrowserNetworkStop":
            return None
        case "BrowserGetCookies":
            return None
        case "BrowserSetCookie":
            if not isinstance(curr_args, dict) or not curr_args.get("name"):
                return None
            key_argument = str(curr_args["name"])
        case "BrowserGetStorage":
            if not isinstance(curr_args, dict):
                return None
            key_argument = str(curr_args.get("storage_type", "localStorage"))
        case "BrowserWaitForSelector":
            if not isinstance(curr_args, dict) or not curr_args.get("selector"):
                return None
            key_argument = str(curr_args["selector"])
        case "BrowserPressKey":
            if not isinstance(curr_args, dict) or not curr_args.get("key"):
                return None
            key_argument = str(curr_args["key"])
        case "BrowserHover":
            if not isinstance(curr_args, dict) or not curr_args.get("selector"):
                return None
            key_argument = str(curr_args["selector"])
        case "BrowserGetTabs" | "BrowserNewTab":
            return None
        case "BrowserSwitchTab":
            if not isinstance(curr_args, dict):
                return None
            key_argument = str(curr_args.get("index") or curr_args.get("url_contains", ""))
        case "BrowserUse":
            if not isinstance(curr_args, dict) or not curr_args.get("task"):
                return None
            key_argument = str(curr_args["task"])
        case _:
            if isinstance(json_content, streamingjson.Lexer):
                # lexer.json_content is list[str] based on streamingjson source code
                content: list[str] = cast(list[str], json_content.json_content)  # type: ignore[reportUnknownMemberType]
                key_argument = "".join(content)
            else:
                key_argument = json_content
    key_argument = shorten_middle(key_argument, width=50)
    return key_argument


def _normalize_path(path: str) -> str:
    cwd = str(KaosPath.cwd().canonical())
    if path.startswith(cwd):
        path = path[len(cwd) :].lstrip("/\\")
    return path
