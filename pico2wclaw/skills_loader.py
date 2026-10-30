"""
skills_loader.py — Load and register Pico2WClaw skills from the skills/ directory.

Skill contract (skills/<name>.py):
    Optional SKILL_INSTR (str): instruction text for the LLM system prompt.
    Optional TOOLS (dict): tool definitions to merge into TOOL_REGISTRY.

TOOLS values must match the tool registry shape:
    {"name": ..., "description": ..., "parameters": {...}, "callable": ...}

MicroPython-compatible: no YAML parser, no stdlib-only, avoids heavy deps.
"""

import os

_skill_namespaces = {}


def _skill_dir():
    """Return absolute path to skills/ directory, CWD-relative on MicroPython."""
    # MicroPython may not have os.path; fall back to CWD-relative "skills/"
    try:
        # Try __file__-relative path first (works on desktop/hosted MPY)
        base = os.path.dirname(os.path.abspath(__file__))
        return base + "/skills"
    except AttributeError:
        # Fallback: assume CWD is the project root
        return "skills"


def load_skills():
    """Scan skills/*.py and return (extra_tools, instruction_lines)."""
    extra_tools = {}
    instrs = []
    try:
        sdir = _skill_dir()
        files = sorted(os.listdir(sdir))
    except OSError:
        return extra_tools, instrs

    for f in files:
        if not f.endswith(".py") or f.startswith("_"):
            continue
        name = f[:-3]
        path = sdir + "/" + f
        try:
            with open(path) as fh:
                src = fh.read()
            ns = {}
            exec(src, ns)
            _skill_namespaces[name] = ns
            if "SKILL_INSTR" in ns:
                instrs.append("[{0}] {1}".format(name, ns["SKILL_INSTR"]))
            if "TOOLS" in ns:
                extra_tools.update(ns["TOOLS"])
        except Exception as e:
            print("[skills] load failed {0}: {1}".format(f, e))
    return extra_tools, instrs


def get_skill_namespaces():
    return dict(_skill_namespaces)


def read_skill(name):
    """Return (instr, tools_dict) for a loaded skill, or None."""
    ns = _skill_namespaces.get(name)
    if not ns:
        return None
    return ns.get("SKILL_INSTR", ""), ns.get("TOOLS", {})
