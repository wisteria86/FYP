"""Keep compatibility coverage for pre-v2 session snapshots.

These fixtures deliberately omit the new definition, as historical databases do.
The v2 runtime and API have separate tests; old keyword-rubric expectations must
never be used as acceptance criteria for newly prepared lessons.
"""
from unittest.mock import patch


def legacy_snapshots(test):
    compiler = patch('services.scenario_service.compile_definition', return_value=None)
    compiler.start()
    test.addCleanup(compiler.stop)
