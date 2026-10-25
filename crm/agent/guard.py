from __future__ import annotations

import json
import os
from datetime import date, datetime
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List

from flask import abort

MAX_STEPS = 8
MAX_TOOL_CALLS = 12
MAX_TOOL_RESULT_BYTES = 4096
_SENSITIVE_KEYS = {'token', 'password', 'authorization'}


class AgentGuardError(ValueError):
    pass


@dataclass(frozen=True)
class ToolSpec:
    name: str
    requires_approval: bool
    required: tuple
    optional: tuple


TOOL_SPECS = {
    'list_matters': ToolSpec('list_matters', False, (), ('query', 'status', 'limit')),
    'get_gantt_tasks': ToolSpec('get_gantt_tasks', False, (), ('query', 'limit')),
    'get_task_docs': ToolSpec('get_task_docs', False, ('task_id',), ()),
    'get_open_flags': ToolSpec('get_open_flags', False, (), ('task_id',)),
    'get_calendar': ToolSpec('get_calendar', False, (), ('caseid', 'event_type', 'date_from', 'date_to', 'deadline_events')),
    'next_actions': ToolSpec('next_actions', False, (), ('case_id', 'matter_id', 'query')),
    'flag_lawyer': ToolSpec('flag_lawyer', True, ('task_id', 'reason'), ()),
    'update_task_status': ToolSpec('update_task_status', True, ('task_id', 'status'), ()),
    'list_tasks': ToolSpec('list_tasks', False, (), ('query', 'status', 'limit')),
    'create_task': ToolSpec('create_task', True, ('title', 'caseid'), ('description', 'duedate', 'startdate', 'priority', 'userid')),
    'create_calendar_event': ToolSpec('create_calendar_event', True, ('title', 'start_datetime'), ('end_datetime', 'caseid', 'event_type', 'location', 'description')),
    'draft_notification': ToolSpec('draft_notification', True, ('subject', 'body'), ('recipient', 'token', 'authorization')),
}


def is_agent_enabled() -> bool:
    return os.environ.get('AGENT_ENABLED', 'false').strip().lower() in ('1', 'true', 'yes', 'on')


def ensure_agent_enabled() -> None:
    if not is_agent_enabled():
        abort(404)


def redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if str(key).strip().lower() in _SENSITIVE_KEYS:
                continue
            out[key] = redact_sensitive(item)
        return out
    if isinstance(value, list):
        return [redact_sensitive(v) for v in value]
    return value


def _require_int(args: Dict[str, Any], key: str) -> int:
    try:
        value = int(args[key])
    except Exception as exc:
        raise AgentGuardError(f'{key} must be an integer') from exc
    return value


def _require_str(args: Dict[str, Any], key: str, max_len: int = 500) -> str:
    value = args.get(key)
    if value is None:
        raise AgentGuardError(f'{key} is required')
    value = str(value).strip()
    if not value:
        raise AgentGuardError(f'{key} is required')
    if len(value) > max_len:
        raise AgentGuardError(f'{key} is too long')
    return value


def validate_tool_call(tool: str, args: Dict[str, Any]) -> Dict[str, Any]:
    spec = TOOL_SPECS.get(tool)
    if not spec:
        raise AgentGuardError(f'Unknown tool: {tool}')
    if not isinstance(args, dict):
        raise AgentGuardError('tool args must be an object')
    cleaned = {}
    for key in spec.required:
        if key not in args:
            raise AgentGuardError(f'{key} is required')
    for key in spec.required + spec.optional:
        if key not in args:
            continue
        if key in spec.optional and (args[key] is None or args[key] == ''):
            continue
        if key in ('task_id', 'caseid', 'case_id', 'matter_id', 'limit', 'userid'):
            cleaned[key] = _require_int(args, key)
        elif key in ('deadline_events',):
            if isinstance(args[key], bool):
                cleaned[key] = args[key]
            else:
                cleaned[key] = str(args[key]).strip().lower() in ('1', 'true', 'yes', 'on')
        else:
            cleaned[key] = _require_str(args, key, 2000 if key == 'description' else 500 if key == 'reason' else 255)
    if tool == 'update_task_status':
        status = cleaned['status'].strip().lower()
        if status not in ('pending', 'in_progress', 'done', 'blocked', 'waiting_docs', 'review', 'closed', 'open'):
            raise AgentGuardError('status is not allowed')
        cleaned['status'] = status
    if tool == 'create_task':
        for k in ('duedate', 'startdate'):
            if k in cleaned:
                try:
                    cleaned[k] = date.fromisoformat(cleaned[k][:10]).isoformat()
                except Exception as exc:
                    raise AgentGuardError(f'{k} must be YYYY-MM-DD') from exc
        if 'priority' in cleaned:
            pr = cleaned['priority'].strip().capitalize()
            if pr not in ('Low', 'Medium', 'High', 'Urgent'):
                raise AgentGuardError('priority is not allowed')
            cleaned['priority'] = pr
    if tool == 'create_calendar_event':
        for k in ('start_datetime', 'end_datetime'):
            if k in cleaned:
                try:
                    datetime.fromisoformat(cleaned[k])
                except Exception as exc:
                    raise AgentGuardError(f'{k} must be ISO 8601') from exc
        if 'event_type' in cleaned and cleaned['event_type'] not in ('hearing', 'meeting', 'deadline', 'call', 'appointment', 'other'):
            cleaned['event_type'] = 'meeting'
    if tool == 'draft_notification':
        cleaned.setdefault('recipient', None)
    return cleaned


def serialize_args(args: Dict[str, Any]) -> str:
    return json.dumps(redact_sensitive(args), ensure_ascii=False, sort_keys=True)


def summarize_data(value: Any, limit: int = 500) -> str:
    try:
        text = json.dumps(redact_sensitive(value), ensure_ascii=False, default=str, sort_keys=True)
    except Exception:
        text = str(value)
    if len(text) > limit:
        return text[:limit - 1] + '…'
    return text


def wrap_untrusted_data(value: Any) -> Dict[str, Any]:
    try:
        text = json.dumps(redact_sensitive(value), ensure_ascii=False, default=str, sort_keys=True)
    except Exception:
        text = str(value)
    if len(text) <= MAX_TOOL_RESULT_BYTES:
        return {'untrusted_data': redact_sensitive(value)}
    return {
        'untrusted_data': {
            'truncated': True,
            'bytes': len(text),
            'preview': text[:MAX_TOOL_RESULT_BYTES],
        }
    }


def tool_requires_approval(tool: str) -> bool:
    spec = TOOL_SPECS.get(tool)
    if not spec:
        raise AgentGuardError(f'Unknown tool: {tool}')
    return spec.requires_approval


def tool_names() -> List[str]:
    return list(TOOL_SPECS.keys())
