import os
from typing import Any, Dict, List
from langchain_core.messages import BaseMessage, AIMessage

model_type, model_id = os.environ.get('LLM_MODEL_ID', 'mock:mock').split(':', 1)

class MockChatModel:
    """Mock chat model for testing when no real model is configured"""
    
    def __init__(self, **kwargs):
        self.model = "mock-model"
        
    def invoke(self, messages: List[BaseMessage], **kwargs) -> AIMessage:
        """Mock invoke method that returns a helpful message"""
        user_message = ""
        for msg in messages:
            if hasattr(msg, 'content'):
                user_message = str(msg.content)
                break
        
        mock_response = f"""I'm a mock AI assistant running in demo mode. You asked: "{user_message}"

To enable real AI functionality, you need to:
1. Set the LLM_MODEL_ID environment variable (e.g., 'openai:gpt-4')
2. Configure the appropriate API keys

For now, I can help with basic Superset questions using my mock responses."""
        
        return AIMessage(content=mock_response)
    
    def stream(self, messages: List[BaseMessage], **kwargs):
        """Mock streaming method"""
        response = self.invoke(messages, **kwargs)
        import time
        words = response.content.split()
        for word in words:
            from langchain_core.messages import AIMessageChunk
            # Add a small delay to simulate real streaming
            time.sleep(0.05)
            yield AIMessageChunk(content=word + " ")

if model_type == 'bedrock':
    try:
        from .inference.bedrock_model import ChatBedrock
        ChatModel = ChatBedrock
    except Exception:
        ChatModel = MockChatModel
elif model_type == 'antropic':
    try:
        from .inference.antropic_model import ChatAnthropic
        ChatModel = ChatAnthropic  
    except Exception:
        ChatModel = MockChatModel
elif model_type == 'openai':
    try:
        from .inference.openai_model import ChatOpenAI
        ChatModel = ChatOpenAI
    except Exception:
        ChatModel = MockChatModel
else:
    ChatModel = MockChatModel
