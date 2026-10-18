"""Probe native decoder support outside the API process."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
if __name__=='__main__':
    try:
        import resource
        resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    except ImportError:
        pass
    from modules.stt_nemotron import NemotronSTT
    model=NemotronSTT(sys.argv[1],sys.argv[2],int(sys.argv[3]),decoding_method=sys.argv[4])
    model.close()
