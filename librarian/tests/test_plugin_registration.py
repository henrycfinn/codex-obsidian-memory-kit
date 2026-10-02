import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]


def load_plugin():
    package_name = "agentic_librarian_test_plugin"
    for key in list(sys.modules):
        if key == package_name or key.startswith(package_name + "."):
            del sys.modules[key]
    spec = importlib.util.spec_from_file_location(
        package_name, ROOT / "__init__.py", submodule_search_locations=[str(ROOT)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package_name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class FakeCtx:
    def __init__(self, settings):
        self.settings = dict(settings)
        self.tools = {}
        self.hooks = {}
        self.commands = {}
        self.skills = {}
        self.prompt_sections = {}

    def get_config(self, key, default=None):
        return self.settings.get(key, default)

    def set_config(self, key, value):
        self.settings[key] = value

    def register_tool(self, *, name, toolset, schema, handler, **kwargs):
        self.tools[name] = {"toolset": toolset, "schema": schema, "handler": handler, **kwargs}

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_command(self, name, handler, description, **kwargs):
        self.commands[name] = {"handler": handler, "description": description, **kwargs}

    def register_skill(self, name, path):
        self.skills[name] = Path(path)

    def register_system_prompt_section(self, name, provider, **kwargs):
        self.prompt_sections[name] = {"provider": provider, **kwargs}


class LegacyCtx(FakeCtx):
    """Older Hermes host: registration APIs, but no settings bridge."""

    get_config = None
    set_config = None


class PluginRegistrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.root = self.base / "knowledge"
        self.root.mkdir()
        self.env = mock.patch.dict(os.environ, {"HERMES_HOME": str(self.base / "hermes")}, clear=False)
        self.env.start()
        self.plugin = load_plugin()
        self.ctx = FakeCtx({"knowledge_root": str(self.root), "qmd_duplicate_check": False})
        self.plugin.register(self.ctx)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_registration_surface(self):
        self.assertEqual(len(self.ctx.tools), 9)
        self.assertIn("pre_tool_call", self.ctx.hooks)
        self.assertIn("librarian", self.ctx.commands)
        self.assertIn("librarian", self.ctx.skills)
        self.assertTrue(self.ctx.skills["librarian"].exists())
        self.assertIn("agentic-librarian.workflow", self.ctx.prompt_sections)

    def test_direct_file_write_inside_root_is_blocked(self):
        hook = self.ctx.hooks["pre_tool_call"]
        result = hook(tool_name="write_file", args={"path": str(self.root / "note.md"), "content": "x"})
        self.assertEqual(result["action"], "block")

    def test_direct_file_write_outside_root_is_not_blocked(self):
        hook = self.ctx.hooks["pre_tool_call"]
        result = hook(tool_name="write_file", args={"path": str(self.base / "outside.md"), "content": "x"})
        self.assertIsNone(result)

    def test_apply_uses_native_approval(self):
        hook = self.ctx.hooks["pre_tool_call"]
        result = hook(tool_name="librarian_apply_proposal", args={"proposal_id": "proposal-test"})
        self.assertEqual(result["action"], "approve")

    def test_configure_uses_native_approval(self):
        hook = self.ctx.hooks["pre_tool_call"]
        result = hook(tool_name="librarian_configure", args={"policy_mode": "strict"})
        self.assertEqual(result["action"], "approve")

    def test_registration_survives_legacy_context_without_config_bridge(self):
        ctx = LegacyCtx({})
        self.plugin.register(ctx)
        self.assertEqual(len(ctx.tools), 9)
        self.assertIn("pre_tool_call", ctx.hooks)

    def test_legacy_context_reports_configuration_limit(self):
        ctx = LegacyCtx({})
        self.plugin.register(ctx)
        result = ctx.tools["librarian_configure"]["handler"]({"policy_mode": "strict"})
        self.assertIn("does not expose", result)


if __name__ == "__main__":
    unittest.main()
