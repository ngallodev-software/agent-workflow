"""Lazy boundary to the dependency-neutral comparative-evaluation library.

Agent-Workflow owns when evidence is captured and how application lifecycle
outcomes are joined. ``agent-workflow-comparative-eval`` owns the record and
metric semantics. This module is imported only when a plugin-advertised mode
requests comparative capture or an operator asks for a comparative report.
"""
from __future__ import annotations
import importlib
from importlib import metadata
from typing import Any
from .errors import WorkflowError

DISTRIBUTION="agent-workflow-comparative-eval"
IMPORT_NAME="agent_workflow_comparative_eval"
REQUIRED_VERSION="0.2.0"

def _version(module: Any)->str|None:
    value=getattr(module,"__version__",None)
    if isinstance(value,str) and value:return value
    try:return metadata.version(DISTRIBUTION)
    except metadata.PackageNotFoundError:return None

def shared_library_status()->dict[str,object]:
    try:
        module=importlib.import_module(IMPORT_NAME)
    except ImportError as exc:
        if exc.name!=IMPORT_NAME: raise
        return {"installed":False,"compatible":False,"version":None,"distribution":DISTRIBUTION}
    version=_version(module)
    return {"installed":True,"compatible":version==REQUIRED_VERSION,"version":version,"distribution":DISTRIBUTION}

def require_shared_library()->Any:
    try: module=importlib.import_module(IMPORT_NAME)
    except ImportError as exc:
        if exc.name==IMPORT_NAME:
            raise WorkflowError("comparative decision mode requires agent-workflow-comparative-eval==0.2.0; install agent-workflow[comparative-eval]") from exc
        raise
    version=_version(module)
    if version!=REQUIRED_VERSION:
        raise WorkflowError(f"unsupported {DISTRIBUTION} version {version!r}; expected {REQUIRED_VERSION}")
    return module
