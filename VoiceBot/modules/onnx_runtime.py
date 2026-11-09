"""Shared Windows CUDA library registration for Sherpa model adapters."""
import os
import site
import ctypes
import logging
import threading
from functools import lru_cache
from pathlib import Path

_provider_handles=[]
_provider_lock=threading.Lock()


@lru_cache(maxsize=1)
def cuda_capability():
    """Eligibility only; applying a mode still validates real model loading."""
    try:
        import torch
        if not torch.cuda.is_available():
            return {'available':False,'reason':'No compatible NVIDIA CUDA GPU detected.'}
        import sherpa_onnx
        if 'cuda' not in sherpa_onnx.__version__:
            return {'available':False,'reason':'Install the CUDA-enabled Sherpa runtime to use GPU recognition.'}
        return {'available':True,'device_name':torch.cuda.get_device_name(0),'reason':None}
    except Exception:
        return {'available':False,'reason':'CUDA hardware or the speech runtime is unavailable.'}


def pin_sherpa_shared_provider():
    """Keep Sherpa's CUDA bridge paired with its bundled ORT on Windows.

    Kokoro's Python ORT may use a newer same-named shared-provider DLL. If
    that DLL loads first, Sherpa's CUDA provider can fail with WinError 1114.
    Pin only the small shared bridge: no GPU initialization or model allocation.
    Must run before creating any Kokoro/ORT session; an already loaded conflicting
    DLL cannot safely be replaced inside a running process.
    """
    if os.name!='nt':return
    with _provider_lock:
        if _provider_handles:return
        try:
            import sherpa_onnx
            if 'cuda' not in sherpa_onnx.__version__:return
            shared=Path(sherpa_onnx.__file__).parent/'lib'/'onnxruntime_providers_shared.dll'
            if shared.is_file():_provider_handles.append(ctypes.WinDLL(str(shared)))
        except (ImportError,OSError) as exc:
            # Optional CUDA support must not prevent CPU-only TTS from loading.
            logging.getLogger(__name__).warning('Could not prepare Sherpa shared provider: %s',exc)


def prepare_sherpa(device):
    pin_sherpa_shared_provider()
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
