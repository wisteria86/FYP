import unittest
from types import SimpleNamespace
from unittest.mock import patch

import run_hikari


class LauncherTests(unittest.TestCase):
    def test_windows_interpreter_layout(self):
        self.assertEqual(run_hikari.venv_python('nt'), run_hikari.ROOT / '.venv' / 'Scripts' / 'python.exe')

    def test_linux_interpreter_layout(self):
        self.assertEqual(run_hikari.venv_python('posix'), run_hikari.ROOT / '.venv' / 'bin' / 'python')

    def test_preflight_checks_selected_venv_interpreter(self):
        interpreter=run_hikari.venv_python('posix')
        with patch.object(run_hikari,'VENV_PYTHON',interpreter), \
             patch('pathlib.Path.exists',return_value=True), \
             patch.object(run_hikari.subprocess,'run',return_value=SimpleNamespace(returncode=0)) as probe:
            selected,_=run_hikari.preflight()
        self.assertEqual(selected,interpreter)
        self.assertEqual(probe.call_args.args[0][0],str(interpreter))
        self.assertNotIn('ChatTTS',probe.call_args.args[0][2])

    def test_missing_packages_report_selected_platform_command(self):
        interpreter=run_hikari.venv_python('posix')
        with patch.object(run_hikari,'VENV_PYTHON',interpreter), \
             patch('pathlib.Path.exists',return_value=True), \
             patch.object(run_hikari.subprocess,'run',return_value=SimpleNamespace(returncode=1)):
            with self.assertRaisesRegex(RuntimeError,'pip install -r requirements.txt') as error:
                run_hikari.preflight()
        self.assertIn(str(interpreter),str(error.exception))
