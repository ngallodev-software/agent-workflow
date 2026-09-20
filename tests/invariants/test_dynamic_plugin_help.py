from agent_workflow.cli_contract import BUILTIN_TOP_LEVEL_COMMANDS
from agent_workflow.cli_runtime import plugins_required_for_command


def test_top_level_help_loads_enabled_plugins_for_discovery() -> None:
    assert plugins_required_for_command(["--help"], set(BUILTIN_TOP_LEVEL_COMMANDS)) is True
    assert plugins_required_for_command(["-h"], set(BUILTIN_TOP_LEVEL_COMMANDS)) is True


def test_top_level_recovery_help_suppresses_plugins() -> None:
    assert plugins_required_for_command(["--no-plugins", "--help"], set(BUILTIN_TOP_LEVEL_COMMANDS)) is False


def test_command_catalog_schema_allows_decision_capability_inventory() -> None:
    from agent_workflow.cli_parser import build_parser
    from agent_workflow.command_catalog import build_command_catalog
    from agent_workflow.plugin_api import PluginCommand, PluginDecisionMode, PluginDecisionProvider, PluginDescriptor
    from agent_workflow.plugins import LoadedPlugin, PluginRegistry

    def configure(parser):
        parser.add_parser = getattr(parser, "add_parser", None)

    def execute(args, context):
        return {}

    def evaluate(request, context):
        return {}

    class Candidate:
        name = "example-plugin"
        value = "example:plugin"
        distribution = "example-plugin"
        distribution_version = "1.0"
        def as_dict(self):
            return {"name": self.name, "entry_point": self.value, "distribution": self.distribution, "distribution_version": self.distribution_version}

    descriptor = PluginDescriptor(
        name="example-plugin",
        version="1.0",
        commands=(PluginCommand("example", "example plugin command", lambda parser: None, execute),),
        decision_providers=(PluginDecisionProvider("example-provider", ("routing.task_class",), evaluate),),
        decision_modes=(PluginDecisionMode("example-mode", "example mode", "example-provider", "shadow"),),
    )
    registry = PluginRegistry(
        loaded=(LoadedPlugin(descriptor, Candidate()),),
        candidates=(),
        configured_enabled=("example-plugin",),
    )
    catalog = build_command_catalog(build_parser(registry), plugin_inventory=registry.catalog_inventory())
    plugin = catalog["plugins"][0]
    assert plugin["decision_providers"] == ["example-provider"]
    assert plugin["decision_modes"] == ["example-mode"]


def test_doctor_does_not_require_plugin_activation_before_diagnostics() -> None:
    assert plugins_required_for_command(["doctor"], set(BUILTIN_TOP_LEVEL_COMMANDS)) is False
