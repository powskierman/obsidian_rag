"""
Compatibility shim for moved module.
"""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

_module_path = Path(__file__).parent / "src" / "services" / "claude_graph_builder.py"
_spec = spec_from_file_location("claude_graph_builder_impl", _module_path)
_module = module_from_spec(_spec)
assert _spec and _spec.loader
_spec.loader.exec_module(_module)

GraphBuilder = _module.GraphBuilder
ClaudeGraphQuerier = _module.ClaudeGraphQuerier
ClaudeGraphBuilder = GraphBuilder
Anthropic = _module.Anthropic

__all__ = ["GraphBuilder", "ClaudeGraphQuerier", "ClaudeGraphBuilder", "Anthropic"]
