"""
Large Language Model Module.

This module implements the ILLMModel interface, serving as the central
"brain" of the voice assistant. It connects to an OpenAI-compatible API
endpoint (like GroqCloud, xAI, or OpenAI itself) and manages conversation
history, persona, and streaming text generation.
"""
# Path: modules/llm_brain.py
from typing import Iterator
from openai import OpenAI
from core.interfaces import ILLMModel
from utils.logger import get_logger

logger = get_logger(__name__)

class LLMBrain(ILLMModel):
    """
    Concrete implementation of the LLM interface using the OpenAI SDK.

    Configured to connect to GroqCloud, xAI, or any OpenAI-compatible endpoint.
    Maintains a rolling conversation history and injects user profiles into the system prompt.
    """
    def __init__(self, api_key: str, model_name: str, base_url: str) -> None:
        """
        Initializes the LLM client and loads the user profile.

        Args:
            api_key (str): The API key for the chosen LLM provider.
            model_name (str): The specific model identifier (e.g., 'llama3-70b-8192').
            base_url (str): The base URL of the OpenAI-compatible API.
        """
        self.api_key = api_key
        self.model_name = model_name
        self.base_url = base_url
        self.max_history_turns = 10  # Prevents context window overflow
        
        import os
        self.profile_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "user_profile.json")
        self._load_profile()
        
        try:
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            logger.info(f"Initialized LLM client (Model: {self.model_name}, URL: {self.base_url})")
        except Exception as e:
            logger.error(f"Failed to initialize LLM client: {e}")
            raise

        self.conversation_history = []
        self._update_system_prompt()

    def _load_profile(self):
        import json
        import os
        if os.path.exists(self.profile_path):
            with open(self.profile_path, 'r') as f:
                self.user_profile = json.load(f)
            # Back-fill any fields added since the profile was created
            self.user_profile.setdefault("language", "English")
        else:
            self.user_profile = {
                "name": "User",
                "subject": "General Programming",
                "weak_areas": "None identified",
                "last_session_summary": "No previous sessions.",
                "goals": "Unknown",
                "language": "English",
            }

    def save_profile(self, new_summary: str, new_goal: str = None, language: str = None):
        import json
        if new_summary:
            self.user_profile["last_session_summary"] = new_summary
        if new_goal:
            self.user_profile["goals"] = new_goal
        if language:
            self.user_profile["language"] = language
        with open(self.profile_path, 'w') as f:
            json.dump(self.user_profile, f, indent=4)
        self._update_system_prompt()

    def _update_system_prompt(self):
        language = self.user_profile.get("language", "English")

        persona = (
            "You are a very blunt, strict, no-nonsense coach and teacher. "
            "Because your responses will be spoken out loud via Text-to-Speech, "
            "you MUST keep your answers concise, natural, and conversational. "
            "Do not use filler words to soften your tone. Be direct, challenging, and hold the user accountable. "
            "Avoid long lists, markdown formatting, or overly complex sentences."
        )

        # Inject language instruction when the user has selected a non-English engine
        if language and language.lower() != "english":
            persona += (
                f" The user is practicing {language}. "
                f"You MUST respond entirely in {language} at all times, "
                "even when the user writes to you in English. Never switch back to English."
            )

        context = (
            f"\n\n[Session Context]\n"
            f"User: {self.user_profile.get('name', 'Unknown')}\n"
            f"Subject: {self.user_profile.get('subject', 'General Coaching')}\n"
            f"Weak Areas: {self.user_profile.get('weak_areas', 'None identified')}\n"
            f"Last Session: {self.user_profile.get('last_session_summary', 'Unknown')}\n"
            f"Today's Goal: {self.user_profile.get('goals', 'Unknown')}\n"
            f"Language: {language}\n"
        )
        self.system_prompt = {
            "role": "system",
            "content": persona + context
        }
        if len(self.conversation_history) > 0 and self.conversation_history[0]["role"] == "system":
            self.conversation_history[0] = self.system_prompt
        else:
            self.conversation_history = [self.system_prompt] + self.conversation_history

    def _trim_history(self):
        """Keeps the conversation history from growing infinitely."""
        # History contains system prompt (1) + user/assistant pairs
        if len(self.conversation_history) > (self.max_history_turns * 2) + 1:
            logger.debug("Trimming conversation history to save tokens.")
            # Keep the system prompt, drop the oldest user/assistant pair, keep the rest
            self.conversation_history = [self.system_prompt] + self.conversation_history[3:]

    def generate_response(self, text: str) -> Iterator[str]:
        """
        Generates a streaming text response based on user input and conversation history.

        Args:
            text (str): The transcribed text from the user.

        Yields:
            str: The generated tokens streamed from the LLM.
        """
        self.conversation_history.append({"role": "user", "content": text})
        
        try:
            logger.debug(f"Sending prompt to {self.model_name}...")
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=self.conversation_history,
                temperature=0.7,   # Slightly creative, good for conversation
                max_tokens=1024,   # Increased to allow the model to finish its <think> block
                stream=True        # Enable streaming!
            )
            
            full_text = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    token = chunk.choices[0].delta.content
                    full_text += token
                    yield token
            
            self.conversation_history.append({"role": "assistant", "content": full_text.strip()})
            self._trim_history()
            
        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            # Remove the user's message from history so we don't get out of sync if it failed
            self.conversation_history.pop() 
            yield "I'm sorry, I'm having trouble connecting to my brain right now."

    def generate_proactive_response(self, system_note: str) -> Iterator[str]:
        """
        Generates a proactive response triggered by internal system events rather than user input.
        
        This temporarily appends a system note to prompt the model (e.g., for silence nudges
        or session summaries) without waiting for a user utterance.

        Args:
            system_note (str): The internal directive for the AI (e.g., "Summarize the session").

        Yields:
            str: The generated tokens streamed from the LLM.
        """
        temp_message = {"role": "system", "content": system_note}
        messages = self.conversation_history + [temp_message]
        
        try:
            logger.debug(f"Sending proactive prompt to {self.model_name}...")
            
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
                stream=True
            )
            
            full_text = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content is not None:
                    token = chunk.choices[0].delta.content
                    full_text += token
                    yield token
            
            self.conversation_history.append({"role": "assistant", "content": full_text.strip()})
            self._trim_history()
            
        except Exception as e:
            logger.error(f"Error generating proactive LLM response: {e}")
            yield "I seem to be having an internal issue right now."