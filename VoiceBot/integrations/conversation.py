"""Adapter for the current replaceable LLM provider."""
class ConversationAdapter:
    def __init__(self, provider): self.provider = provider
    def generate_response(self, context): return self.provider.generate_contextual_response(context)
    def generate_contextual_response(self, context): return self.generate_response(context)
    @property
    def supports_group_response(self): return getattr(self.provider,'supports_group_response',False) is True
    def generate_group_response(self, context): return self.provider.generate_group_response(context)
    @property
    def supports_quota_priority(self): return getattr(self.provider,'supports_quota_priority',False) is True
    def evaluate_runtime(self, context, **kwargs): return self.provider.evaluate_runtime(context,**kwargs)
    def plan_turn(self, context): return self.provider.plan_turn(context)
    @property
    def router_enabled(self): return getattr(self.provider, 'router_enabled', False) is True
    def read_turn(self, context): return self.provider.read_turn(context)
    def generate_debrief(self, context): return self.provider.generate_debrief(context)
    def check_runtime_reply(self, context): return self.provider.check_runtime_reply(context)
    def generate_scenario(self, context):
        return {'context': ''.join(self.generate_response(context))}
    def evaluate_conversation(self, context): return self.provider.evaluate_english(context)
    def evaluate_english(self, context): return self.evaluate_conversation(context)
    def evaluate_objectives(self, context):
        if not hasattr(self.provider,'evaluate_objectives'):return None
        return self.provider.evaluate_objectives(context)
    def translate_caption(self, text, language): return self.provider.translate_caption(text, language)
