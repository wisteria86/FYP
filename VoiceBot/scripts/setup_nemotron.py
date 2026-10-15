"""Download the documented English Nemotron ONNX export into this project."""
from pathlib import Path
import argparse
import tarfile
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
NAME='sherpa-onnx-nemotron-speech-streaming-en-0.6b-560ms-int8-2026-04-25'
URL=f'https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/{NAME}.tar.bz2'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache-dir',type=Path,default=ROOT/'models'/'nemotron')
    options=parser.parse_args()
    destination=options.cache_dir.resolve()
    destination.mkdir(parents=True,exist_ok=True)
    if all((destination/NAME/name).is_file() for name in ('tokens.txt','encoder.int8.onnx','decoder.int8.onnx','joiner.int8.onnx')):
        print('Nemotron model already downloaded:',destination/NAME)
        return
    archive=destination/(NAME+'.tar.bz2')
    print('Downloading NVIDIA Nemotron English streaming export...',flush=True)
    if not archive.exists():
        urllib.request.urlretrieve(URL,archive)
    # Reject traversals, links, and existing files; never overwrite model caches.
    with tarfile.open(archive,'r:bz2') as package:
        for member in package.getmembers():
            target=(destination/member.name).resolve()
            if not target.is_relative_to(destination.resolve()) or not (member.isfile() or member.isdir()):
                raise RuntimeError('Unsafe model archive member')
            if member.isfile() and target.exists():
                raise RuntimeError(f'Refusing to overwrite {target}')
        package.extractall(destination,filter='data')
    print('Model ready:',destination/NAME,flush=True)

if __name__=='__main__':
    main()
