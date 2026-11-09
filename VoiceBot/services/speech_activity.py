"""Prevent a recognition engine switch from invalidating in-flight audio."""
import threading
from contextlib import contextmanager


class SpeechBusyError(RuntimeError):
    """An active capture/switch blocks changing engines, not a model failure."""


class SpeechActivity:
    def __init__(self):
        self.lock=threading.Lock();self.users=0;self.switching=False

    @contextmanager
    def use(self):
        with self.lock:
            if self.switching:raise SpeechBusyError('Speech engine is loading. Please retry shortly.')
            self.users+=1
        try:yield
        finally:
            with self.lock:self.users-=1

    @contextmanager
    def switch(self):
        with self.lock:
            if self.users or self.switching:raise SpeechBusyError('Pause microphone capture before switching recognition engines.')
            self.switching=True
        try:yield
        finally:
            with self.lock:self.switching=False
