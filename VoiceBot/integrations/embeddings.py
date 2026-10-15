"""Lazy CPU sentence embeddings; no user text is sent to a cloud provider."""
import threading
from config import Config


class MiniLMEmbeddingAdapter:
    def __init__(self):
        self._lock = threading.Lock()
        self.model = self.tokenizer = None

    def generate_embedding(self, texts):
        import torch
        from transformers import AutoTokenizer, AutoModel
        with self._lock, torch.inference_mode():
            if self.model is None:
                self.tokenizer = AutoTokenizer.from_pretrained(Config.EMBEDDING_MODEL, cache_dir=Config.EMBEDDING_CACHE_DIR)
                self.model = AutoModel.from_pretrained(Config.EMBEDDING_MODEL, cache_dir=Config.EMBEDDING_CACHE_DIR).to('cpu').eval()
            results = []
            for start in range(0, len(texts), 16):
                inputs = self.tokenizer(texts[start:start+16], padding=True, truncation=True, max_length=256, return_tensors='pt')
                hidden = self.model(**inputs).last_hidden_state
                mask = inputs['attention_mask'].unsqueeze(-1)
                pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
                results.extend(torch.nn.functional.normalize(pooled,p=2,dim=1).tolist())
            return results


_shared = MiniLMEmbeddingAdapter()
def embedding_provider(): return _shared
