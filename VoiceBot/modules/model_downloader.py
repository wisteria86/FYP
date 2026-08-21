"""
Model Downloader — HuggingFace Download & Cache Bootstrap.

Downloads VITS TTS model files (Japanese and Arabic) from HuggingFace Hub into
local cache directories. Performs a minimum-size sanity check on cached files and,
optionally, quantizes the downloaded model to int8 via ONNX Runtime dynamic
quantization for fast CPU inference.

Called from main.py only when TTS_ENGINE=vits_ja or TTS_ENGINE=vits_ar.
The Kokoro path is unaffected.
"""
# Path: modules/model_downloader.py
import os
import logging
from typing import Tuple

from utils.logger import get_logger
from utils.ui import CLI

logger = get_logger(__name__)

# Minimum expected byte sizes for a sanity check after download.
# The tsukuyomi-chan fp16 ONNX is ~170 MB; config.json is tiny.
_MIN_ONNX_BYTES   = 10_000_000  # 10 MB  (conservative floor for any VITS ONNX)
_MIN_CONFIG_BYTES = 1_000       # 1 KB


def _assert_file_healthy(path: str, min_bytes: int, label: str) -> None:
    """Raise RuntimeError if *path* is missing or suspiciously small."""
    if not os.path.exists(path):
        raise RuntimeError(
            f"[model_downloader] Expected {label} at '{path}' but the file does not exist. "
            "Download may have failed silently. Check your internet connection and HuggingFace "
            "token (if the repo is gated)."
        )
    actual = os.path.getsize(path)
    if actual < min_bytes:
        raise RuntimeError(
            f"[model_downloader] {label} at '{path}' is only {actual:,} bytes "
            f"(expected ≥ {min_bytes:,}). The file is likely a partial or corrupt download. "
            "Delete it and re-run to trigger a fresh download."
        )


def _quantize_to_int8(fp_model_path: str) -> str:
    """
    Runs ONNX Runtime dynamic quantization on *fp_model_path* and saves the result
    as <stem>-int8.onnx in the same directory.  Returns the path to the int8 model.

    Dynamic quantization converts weights to int8 offline; activations remain float
    at runtime.  This gives 3–4× speed-up vs fp16 on a typical multi-core CPU with
    no quality loss perceptible in TTS output.
    """
    stem, _ = os.path.splitext(fp_model_path)
    int8_path = f"{stem}-int8.onnx"

    if os.path.exists(int8_path) and os.path.getsize(int8_path) > _MIN_ONNX_BYTES:
        logger.info(f"✅ Found cached int8 model: {int8_path}")
        return int8_path

    logger.info(f"⚙️  Quantizing model to int8 (this runs once, saves to {int8_path})…")
    try:
        from onnxruntime.quantization import quantize_dynamic, QuantType  # type: ignore
        quantize_dynamic(fp_model_path, int8_path, weight_type=QuantType.QInt8)
        _assert_file_healthy(int8_path, _MIN_ONNX_BYTES, "quantized int8 ONNX model")
        logger.info(f"✅ Quantization complete → {int8_path}")
    except Exception as exc:
        # If quantization fails, log a warning and fall back to the original model.
        logger.warning(
            f"[model_downloader] int8 quantization failed ({exc}). "
            "Falling back to the original (fp16/fp32) model. "
            "Inference may be slower on CPU."
        )
        # Clean up a potentially partial file so we retry next time.
        if os.path.exists(int8_path):
            os.remove(int8_path)
        return fp_model_path

    return int8_path


def download_vits_ja_model(
    repo_id: str,
    onnx_filename: str,
    config_filename: str,
    cache_dir: str,
    revision: str = "main",
    quantize: bool = True,
) -> Tuple[str, str]:
    """
    Ensures the VITS Japanese ONNX model and its config are present in *cache_dir*.

    Steps:
    1. Resolves *cache_dir* relative to the project root (VoiceBot/).
    2. Creates the directory if it does not exist.
    3. Checks whether required files are already cached (by existence + min-size).
    4. Downloads missing files using ``huggingface_hub.hf_hub_download``.
    5. If *quantize* is True, generates an int8 copy via dynamic quantization
       and returns the path to the int8 model instead of the original.
    6. Fails loudly with a descriptive RuntimeError if anything goes wrong —
       never falls back silently to a broken model.

    Returns
    -------
    (onnx_path, config_path) — absolute paths, ready for InferenceSession.
    """
    # Resolve cache directory relative to project root (two levels up from modules/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_cache_dir = os.path.join(project_root, cache_dir)
    os.makedirs(abs_cache_dir, exist_ok=True)

    onnx_local   = os.path.join(abs_cache_dir, onnx_filename)
    config_local = os.path.join(abs_cache_dir, config_filename)

    # ------------------------------------------------------------------ #
    # Import huggingface_hub lazily so missing package gives a clear error
    # ------------------------------------------------------------------ #
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        raise RuntimeError(
            "[model_downloader] 'huggingface_hub' is not installed. "
            "Run: pip install huggingface_hub"
        )

    def _download_file(filename: str, dest: str, min_bytes: int, label: str) -> None:
        """Download *filename* from the HF repo into *dest* unless already healthy."""
        if os.path.exists(dest) and os.path.getsize(dest) >= min_bytes:
            logger.info(f"✅ Using cached {label}: {dest}")
            return

        logger.info(f"⬇️  Downloading {label} from {repo_id}/{filename} …")
        try:
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=filename,
                local_dir=abs_cache_dir,
                revision=revision,
            )
            # hf_hub_download returns the actual path; symlink or copy to dest if different
            if os.path.abspath(downloaded) != os.path.abspath(dest):
                import shutil
                shutil.copy2(downloaded, dest)
        except Exception as exc:
            raise RuntimeError(
                f"[model_downloader] Failed to download '{filename}' from "
                f"'{repo_id}' (revision='{revision}'). Error: {exc}\n"
                "Possible causes: no internet, private/gated repo without HF token, "
                "or the file was renamed/deleted upstream. "
                "Set HUGGING_FACE_HUB_TOKEN in .env if the repo requires authentication."
            ) from exc

        _assert_file_healthy(dest, min_bytes, label)
        logger.info(f"✅ {label} downloaded → {dest}")

    # Download ONNX model
    with CLI.status(f"Checking/downloading VITS ONNX model ({onnx_filename})…", spinner="arrow3"):
        _download_file(onnx_filename, onnx_local, _MIN_ONNX_BYTES, "VITS ONNX model")

    # Download config.json
    with CLI.status(f"Checking/downloading VITS config ({config_filename})…", spinner="arrow3"):
        _download_file(config_filename, config_local, _MIN_CONFIG_BYTES, "VITS config JSON")

    # Final health checks
    _assert_file_healthy(onnx_local,   _MIN_ONNX_BYTES,   "VITS ONNX model (post-download)")
    _assert_file_healthy(config_local, _MIN_CONFIG_BYTES,  "VITS config JSON (post-download)")

    # Quantize if requested
    if quantize:
        with CLI.status("Running int8 dynamic quantization (first-run only)…", spinner="dots"):
            onnx_local = _quantize_to_int8(onnx_local)

    return onnx_local, config_local


def download_vits_ar_model(
    repo_id: str,
    onnx_filename: str,
    config_filename: str,
    cache_dir: str,
    revision: str = "main",
    quantize: bool = True,
) -> Tuple[str, str]:
    """
    Ensures the VITS Arabic ONNX model and its piper config are present in *cache_dir*.

    Mirrors download_vits_ja_model() exactly — same cache-check → download-if-missing
    → verify pattern, just parameterized for the Arabic HF repo and file paths.

    The rhasspy/piper-voices repo stores files in nested subdirectories
    (e.g. ``ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx``). HuggingFace Hub
    resolves the full path transparently; we copy the result into a flat local
    cache directory (e.g. ``models/vits_ar/``) so the layout mirrors vits_ja.

    Steps:
    1. Resolves *cache_dir* relative to the project root (VoiceBot/).
    2. Creates the directory if it does not exist.
    3. Checks whether required files are already cached (by existence + min-size).
    4. Downloads missing files using ``huggingface_hub.hf_hub_download``.
    5. If *quantize* is True, generates an int8 copy via dynamic quantization
       and returns the path to the int8 model instead of the original fp32 model.
    6. Fails loudly with a descriptive RuntimeError if anything goes wrong —
       never falls back silently to a broken model.

    Parameters
    ----------
    repo_id        : HuggingFace repository id (e.g. "rhasspy/piper-voices").
    onnx_filename  : Filename or subpath within the repo for the .onnx file.
                     Example: ``"ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx"``
    config_filename: Filename or subpath within the repo for the config JSON.
                     Example: ``"ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json"``
    cache_dir      : Local directory path (relative to project root) for caching.
    revision       : Git revision / branch / tag to pin the download (default: "main").
    quantize       : If True, generate an int8 ONNX copy on first run via dynamic
                     quantization (3–4x faster on CPU). Default: True.

    Returns
    -------
    (onnx_path, config_path) — absolute paths, ready for InferenceSession.
    """
    # Resolve cache directory relative to project root (two levels up from modules/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    abs_cache_dir = os.path.join(project_root, cache_dir)
    os.makedirs(abs_cache_dir, exist_ok=True)

    # Local flat filenames (basename only — strip the HF subpath prefix)
    onnx_basename   = os.path.basename(onnx_filename)
    config_basename = os.path.basename(config_filename)
    onnx_local      = os.path.join(abs_cache_dir, onnx_basename)
    config_local    = os.path.join(abs_cache_dir, config_basename)

    # ------------------------------------------------------------------ #
    # Import huggingface_hub lazily so missing package gives a clear error
    # ------------------------------------------------------------------ #
    try:
        from huggingface_hub import hf_hub_download  # type: ignore
    except ImportError:
        raise RuntimeError(
            "[model_downloader] 'huggingface_hub' is not installed. "
            "Run: pip install huggingface_hub"
        )

    def _download_file(hf_path: str, dest: str, min_bytes: int, label: str) -> None:
        """Download *hf_path* from the HF repo into *dest* unless already healthy."""
        if os.path.exists(dest) and os.path.getsize(dest) >= min_bytes:
            logger.info(f"✅ Using cached {label}: {dest}")
            return

        logger.info(f"⬇️  Downloading {label} from {repo_id}/{hf_path} …")
        try:
            downloaded = hf_hub_download(
                repo_id=repo_id,
                filename=hf_path,
                local_dir=abs_cache_dir,
                revision=revision,
            )
            # hf_hub_download may place the file in a nested subdir; copy flat
            if os.path.abspath(downloaded) != os.path.abspath(dest):
                import shutil
                shutil.copy2(downloaded, dest)
        except Exception as exc:
            raise RuntimeError(
                f"[model_downloader] Failed to download '{hf_path}' from "
                f"'{repo_id}' (revision='{revision}'). Error: {exc}\n"
                "Possible causes: no internet, private/gated repo without HF token, "
                "or the file was renamed/deleted upstream. "
                "Set HUGGING_FACE_HUB_TOKEN in .env if the repo requires authentication."
            ) from exc

        _assert_file_healthy(dest, min_bytes, label)
        logger.info(f"✅ {label} downloaded → {dest}")

    # Download ONNX model
    with CLI.status(f"Checking/downloading Arabic VITS ONNX model ({onnx_basename})…", spinner="arrow3"):
        _download_file(onnx_filename, onnx_local, _MIN_ONNX_BYTES, "Arabic VITS ONNX model")

    # Download config JSON
    with CLI.status(f"Checking/downloading Arabic VITS config ({config_basename})…", spinner="arrow3"):
        _download_file(config_filename, config_local, _MIN_CONFIG_BYTES, "Arabic VITS config JSON")

    # Final health checks
    _assert_file_healthy(onnx_local,   _MIN_ONNX_BYTES,   "Arabic VITS ONNX model (post-download)")
    _assert_file_healthy(config_local, _MIN_CONFIG_BYTES,  "Arabic VITS config JSON (post-download)")

    # Quantize if requested (fp32 → int8; fast, runs once offline)
    if quantize:
        with CLI.status("Running int8 dynamic quantization on Arabic model (first-run only)…", spinner="dots"):
            onnx_local = _quantize_to_int8(onnx_local)

    return onnx_local, config_local
