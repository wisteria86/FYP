"""Shared Windows CUDA library registration for Sherpa model adapters."""
import os
import site
from pathlib import Path


def prepare_sherpa(device):
    handles=[]
    if device=='cuda':
        import modules.stt_whisper  # Registers matching Torch/cuDNN and cuBLAS.
        if os.name=='nt':
            for root in site.getsitepackages():
                for library in ('cufft','curand','cuda_runtime','nvjitlink'):
                    folder=Path(root)/'nvidia'/library/'bin'
                    if folder.is_dir():
                        handles.append(os.add_dll_directory(str(folder)))
                        os.environ['PATH']=str(folder)+os.pathsep+os.environ.get('PATH','')
    import sherpa_onnx
    if device=='cuda' and 'cuda' not in sherpa_onnx.__version__:
        raise RuntimeError('Sherpa-ONNX CUDA runtime is not installed')
    return sherpa_onnx,handles
