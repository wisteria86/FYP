"""Lazily consume a shared stream; unused replies never enter session state."""
import threading


class GroupDraft:
    def __init__(self, provider, prompt):
        self.ids=prompt['speaker_ids']
        self.iterator=iter(provider.generate_group_response(prompt))
        self.lock=threading.Lock()
        self.stopped=threading.Event()
        self.cache={}
        self.taken={}

    def tokens(self, participant_id):
        with self.lock:
            try:
                while participant_id not in self.cache and not self.stopped.is_set():
                    item=next(self.iterator)
                    self.cache[item['participant_id']]=item['text']
                if not self.stopped.is_set():
                    self.taken[participant_id]=self.cache.pop(participant_id)
                    yield self.taken[participant_id]
            finally:
                if self.stopped.is_set():self.iterator.close()

    def close(self):
        self.stopped.set()
        if self.lock.acquire(blocking=False):
            try:self.iterator.close()
            finally:self.lock.release()
