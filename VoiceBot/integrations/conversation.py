"""Adapter for the current replaceable LLM provider."""
class ConversationAdapter:
    def __init__(self, provider): self.provider = provider
    def generate_response(self, context): return self.provider.generate_contextual_response(context)
    def generate_contextual_response(self, context): return self.generate_response(context)
    def generate_scenario(self, context):
        return {'context': ''.join(self.generate_response(context))}
    def evaluate_conversation(self, context): return self.provider.evaluate_english(context)
    def evaluate_english(self, context): return self.evaluate_conversation(context)
    def translate_caption(self, text, language): return self.provider.translate_caption(text, language)
