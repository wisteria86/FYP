import unittest
from types import SimpleNamespace
from unittest.mock import patch
from modules import onnx_runtime


class OnnxRuntimeTests(unittest.TestCase):
    def test_windows_cuda_shared_provider_is_loaded_once_and_retained(self):
        runtime=SimpleNamespace(__version__='1.13.8+cuda12.cudnn9',__file__='/packages/sherpa_onnx/__init__.py')
        with patch.object(onnx_runtime,'os',SimpleNamespace(name='nt')), \
             patch.object(onnx_runtime,'_provider_handles',[]), \
             patch.dict('sys.modules',{'sherpa_onnx':runtime}), \
             patch('pathlib.Path.is_file',return_value=True), \
             patch.object(onnx_runtime.ctypes,'WinDLL',create=True) as loader:
            onnx_runtime.pin_sherpa_shared_provider()
            onnx_runtime.pin_sherpa_shared_provider()
            loader.assert_called_once()
            self.assertTrue(loader.call_args.args[0].endswith('onnxruntime_providers_shared.dll'))
            self.assertEqual(onnx_runtime._provider_handles,[loader.return_value])

    def test_cpu_distribution_does_not_load_cuda_bridge(self):
        runtime=SimpleNamespace(__version__='1.13.8')
        with patch.object(onnx_runtime,'os',SimpleNamespace(name='nt')), \
             patch.object(onnx_runtime,'_provider_handles',[]), \
             patch.dict('sys.modules',{'sherpa_onnx':runtime}), \
             patch.object(onnx_runtime.ctypes,'WinDLL',create=True) as loader:
            onnx_runtime.pin_sherpa_shared_provider()
            loader.assert_not_called()

    def test_non_windows_is_unchanged(self):
        with patch.object(onnx_runtime,'os',SimpleNamespace(name='posix')), \
             patch.object(onnx_runtime.ctypes,'WinDLL',create=True) as loader:
            onnx_runtime.pin_sherpa_shared_provider()
            loader.assert_not_called()
