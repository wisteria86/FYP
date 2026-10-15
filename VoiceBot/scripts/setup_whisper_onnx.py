"""Download only INT8 ONNX weights and tokens, with resumable HF caching."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from config import Config
from huggingface_hub import hf_hub_download


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--size',choices=['small','medium','both'],default='both')
    args=parser.parse_args()
    for size in ('small','medium') if args.size=='both' else (args.size,):
        for suffix in ('encoder.int8.onnx','decoder.int8.onnx','tokens.txt'):
            hf_hub_download(repo_id=f'csukuangfj/sherpa-onnx-whisper-{size}',
                            filename=f'{size}-{suffix}',local_dir=ROOT/Config.WHISPER_ONNX_CACHE_DIR/size)
        print(f'Whisper {size} ONNX downloaded.',flush=True)

if __name__=='__main__':main()
