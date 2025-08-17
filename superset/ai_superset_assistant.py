from flask import render_template_string, request, jsonify, Response
from flask_appbuilder import BaseView, expose
from flask_login import current_user
import logging
import json
import uuid
import asyncio
import threading
from datetime import datetime
from functools import wraps
import os
from pathlib import Path

# Assuming these imports are correctly configured in your project
from app.server.llm import get_stream_agent_responce
from app.databases.postgres import Database

logger = logging.getLogger(__name__)

def admin_only(f):
    """Decorator to restrict access to authenticated users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user or not current_user.is_authenticated:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def failure_tolerant(f):
    """Decorator for error handling."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"AI Assistant error: {e}")
            return jsonify({"error": "Something went wrong"}), 500
    return decorated_function

class AIAssistantAgent:
    """Real AI Assistant agent using LangGraph"""
    
    def __init__(self):
        self.sessions = {}  # Track session metadata
    
    def create_session(self):
        """Create a new chat session"""
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            'created_at': datetime.now(),
            'username': getattr(current_user, 'username', 'anonymous') if current_user and current_user.is_authenticated else 'anonymous'
        }
        return session_id
    
    async def get_response_stream(self, message, session_id=None, username=None):
        """Generate AI response using real LangGraph implementation"""
        if not session_id or session_id not in self.sessions:
            session_id = self.create_session()
        
        if not username:
            username = self.sessions[session_id].get('username', 'anonymous')
        
        try:
            stream_generator = await get_stream_agent_responce(
                session_id=session_id,
                message=message,
                md_uri=os.environ.get('SQLALCHEMY_DATABASE_URI'),
                username=username
            )
            
            async for chunk in stream_generator():
                if chunk:
                    yield chunk
            
        except Exception as e:
            logger.error(f"Error generating AI response: {e}")
            error_message = "I'm sorry, I encountered an error while processing your request. Please try again."
            yield error_message
    
    def sync_get_response(self, message, session_id=None, username=None):
        """Synchronous wrapper for async response generation"""
        try:
            if not session_id or session_id not in self.sessions:
                session_id = self.create_session()
                
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            response_parts = []
            
            async def collect_response():
                async for chunk in self.get_response_stream(message, session_id, username):
                    response_parts.append(chunk)
                return ''.join(response_parts)
            
            complete_response = loop.run_until_complete(collect_response())
            return complete_response, session_id
        except Exception as e:
            logger.error(f"Error in sync response generation: {e}")
            fallback_response = "I'm experiencing technical difficulties. Please try again later."
            return fallback_response, session_id or self.create_session()
        finally:
            try:
                loop.close()
            except:
                pass

class AISupersetAssistantView(BaseView):
    
    default_view = 'assistant'
    template_folder = Path(__file__).parent / 'templates'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ai_agent = AIAssistantAgent()
        self._setup_database()
    
    def _setup_database(self):
        """Setup database for AI agent checkpointing"""
        try:
            def setup_db():
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(Database.setup(md_uri=os.environ.get('SQLALCHEMY_DATABASE_URI')))
                    logger.info("✅ AI Assistant database initialized successfully")
                except Exception as e:
                    logger.error(f"❌ Failed to setup AI Assistant database: {e}")
            
            thread = threading.Thread(target=setup_db, daemon=True)
            thread.start()
        except Exception as e:
            logger.error(f"Error starting database setup: {e}")
    
    @expose('/assistant/')
    @admin_only
    @failure_tolerant
    def assistant(self):
        """Main AI Assistant interface with real chat functionality"""
        
        # Interactive chat interface content
        assistant_content = '''
        <style>
            .ai-assistant-container {
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                height: calc(100vh - 100px);
                display: flex;
                flex-direction: column;
            }
            .assistant-header {
                background: linear-gradient(135deg, #4CAF50 0%, #45a049 100%);
                color: white;
                padding: 20px;
                border-radius: 10px 10px 0 0;
                text-align: center;
            }
            .assistant-title {
                margin: 0;
                font-size: 1.8rem;
                display: flex;
                align-items: center;
                justify-content: center;
                gap: 10px;
            }
            .chat-container {
                flex: 1;
                display: flex;
                flex-direction: column;
                background: white;
                border: 1px solid #e0e0e0;
                border-top: none;
            }
            .chat-messages {
                flex: 1;
                padding: 20px;
                overflow-y: auto;
                background: #f8f9fa;
                max-height: 500px;
            }
            .message {
                margin-bottom: 15px;
                padding: 12px 16px;
                border-radius: 12px;
                max-width: 80%;
                word-wrap: break-word;
            }
            .message.user {
                background: #007bff;
                color: white;
                margin-left: auto;
                text-align: right;
            }
            .message.assistant {
                background: white;
                color: #333;
                border: 1px solid #e0e0e0;
                margin-right: auto;
            }
            .message.assistant pre {
                background: #f1f3f4;
                padding: 10px;
                border-radius: 5px;
                overflow-x: auto;
                margin: 10px 0;
            }
            .message.assistant code {
                background: #f1f3f4;
                padding: 2px 4px;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
            }
            .message-time {
                font-size: 0.8rem;
                opacity: 0.7;
                margin-top: 5px;
            }
            .chat-input-container {
                padding: 20px;
                background: white;
                border-top: 1px solid #e0e0e0;
                border-radius: 0 0 10px 10px;
            }
            .chat-input-form {
                display: flex;
                gap: 10px;
                align-items: center;
            }
            .chat-input {
                flex: 1;
                padding: 12px 15px;
                border: 2px solid #e0e0e0;
                border-radius: 25px;
                font-size: 14px;
                outline: none;
                transition: border-color 0.3s;
            }
            .chat-input:focus {
                border-color: #4CAF50;
            }
            .chat-send-btn {
                background: #4CAF50;
                color: white;
                border: none;
                padding: 12px 20px;
                border-radius: 25px;
                cursor: pointer;
                font-weight: 500;
                transition: background 0.3s;
                min-width: 80px;
            }
            .chat-send-btn:hover:not(:disabled) {
                background: #45a049;
            }
            .chat-send-btn:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            .typing-indicator {
                display: none;
                padding: 12px 16px;
                color: #666;
                font-style: italic;
                background: white;
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                margin-bottom: 15px;
                max-width: 200px;
            }
            .typing-indicator.show {
                display: block;
            }
            .control-buttons {
                display: flex;
                gap: 10px;
                margin-bottom: 15px;
            }
            .control-btn {
                background: #17a2b8;
                color: white;
                border: none;
                padding: 8px 15px;
                border-radius: 20px;
                cursor: pointer;
                font-size: 0.9rem;
                transition: background 0.3s;
            }
            .control-btn:hover {
                background: #138496;
            }
            .status-bar {
                padding: 10px 20px;
                background: #f8f9fa;
                border-top: 1px solid #e0e0e0;
                font-size: 0.9rem;
                color: #666;
                display: flex;
                justify-content: between;
                align-items: center;
            }
            .session-info {
                font-size: 0.8rem;
                opacity: 0.8;
            }
            @media (max-width: 768px) {
                .ai-assistant-container {
                    padding: 10px;
                    height: calc(100vh - 80px);
                }
                .message {
                    max-width: 95%;
                }
                .chat-input-form {
                    flex-direction: column;
                    gap: 10px;
                }
                .chat-input {
                    width: 100%;
                }
            }
        </style>
        
        <div class="ai-assistant-container">
            <div class="assistant-header">
                <h1 class="assistant-title">
                    <span>🤖</span>
                    AI Superset Assistant
                </h1>
                <p style="margin: 5px 0 0 0; opacity: 0.9;">Your intelligent Apache Superset companion</p>
            </div>
            
            <div class="chat-container">
                <div class="chat-messages" id="chatMessages">
                    <div class="message assistant">
                        <div>
                            Hello! I'm your AI Superset Assistant 🚀<br><br>
                            What would you like to know about Apache Superset?
                        </div>
                        <div class="message-time">Just now</div>
                    </div>
                </div>
                
                <div class="typing-indicator" id="typingIndicator">
                    AI is thinking...
                </div>
                
                <div class="chat-input-container">
                    <div class="control-buttons">
                        <button class="control-btn" id="newChatBtn">New Chat</button>
                        <button class="control-btn" id="clearChatBtn">Clear Chat</button>
                    </div>
                    
                    <form class="chat-input-form" id="chatInputForm">
                        <input 
                            type="text" 
                            class="chat-input" 
                            id="messageInput"
                            placeholder="Ask me anything about Apache Superset..."
                            maxlength="500"
                            required
                        >
                        <button type="submit" class="chat-send-btn" id="sendBtn">
                            Send
                        </button>
                    </form>
                </div>
                
                <div class="status-bar">
                    <span>Status: <span id="connectionStatus">Connected</span></span>
                    <span class="session-info">Session: <span id="sessionId">Loading...</span></span>
                </div>
            </div>
        </div>
        
        <script>
            let currentSessionId = null;
            let csrfToken = null;
            
            document.addEventListener('DOMContentLoaded', function() {
                initializeCSRF().then(() => {
                    initializeSession();
                });
                document.getElementById('chatInputForm').addEventListener('submit', sendMessage);
                document.getElementById('newChatBtn').addEventListener('click', newChat);
                document.getElementById('clearChatBtn').addEventListener('click', clearChat);
                document.getElementById('showExamplesBtn').addEventListener('click', showExamples);
            });
            
            async function initializeCSRF() {
                try {
                    const response = await fetch('/api/v1/security/csrf_token/');
                    if (response.ok) {
                        const data = await response.json();
                        csrfToken = data.result;
                    }
                } catch (error) {
                    console.error('Error fetching CSRF token:', error);
                }
            }
            
            async function initializeSession() {
                try {
                    const headers = {
                        'Content-Type': 'application/json'
                    };
                    if (csrfToken) {
                        headers['X-CSRFToken'] = csrfToken;
                    }
                    
                    const response = await fetch('/aisupersetassistantview/api/new_session', {
                        method: 'POST',
                        headers: headers
                    });
                    
                    if (response.ok) {
                        const data = await response.json();
                        currentSessionId = data.session_id;
                        document.getElementById('sessionId').textContent = currentSessionId.substring(0, 8) + '...';
                        document.getElementById('connectionStatus').textContent = 'Connected';
                    } else {
                        throw new Error('Failed to initialize session');
                    }
                } catch (error) {
                    console.error('Error initializing session:', error);
                    document.getElementById('connectionStatus').textContent = 'Error';
                }
            }
            
            async function sendMessage(event) {
                event.preventDefault();
                
                const messageInput = document.getElementById('messageInput');
                const sendBtn = document.getElementById('sendBtn');
                const message = messageInput.value.trim();
                
                if (!message || !currentSessionId) return;
                
                messageInput.disabled = true;
                sendBtn.disabled = true;
                sendBtn.textContent = 'Sending...';
                
                addMessage(message, 'user');
                messageInput.value = '';
                
                showTypingIndicator();
                
                try {
                    let assistantMessageDiv = null;
                    let assistantContentDiv = null;
                    
                    function createAssistantMessage() {
                        const messagesContainer = document.getElementById('chatMessages');
                        assistantMessageDiv = document.createElement('div');
                        assistantMessageDiv.className = 'message assistant';
                        
                        assistantContentDiv = document.createElement('div');
                        assistantContentDiv.innerHTML = '';
                        
                        const timeDiv = document.createElement('div');
                        timeDiv.className = 'message-time';
                        timeDiv.textContent = new Date().toLocaleTimeString();
                        
                        assistantMessageDiv.appendChild(assistantContentDiv);
                        assistantMessageDiv.appendChild(timeDiv);
                        messagesContainer.appendChild(assistantMessageDiv);
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    }
                    
                    const headers = {
                        'Content-Type': 'application/json'
                    };
                    if (csrfToken) {
                        headers['X-CSRFToken'] = csrfToken;
                    }
                    
                    const response = await fetch('/aisupersetassistantview/api/chat_stream', {
                        method: 'POST',
                        headers: headers,
                        body: JSON.stringify({
                            message: message,
                            session_id: currentSessionId
                        })
                    });
                    
                    if (!response.ok) {
                        throw new Error('Failed to send message');
                    }
                    
                    hideTypingIndicator();
                    createAssistantMessage();
                    
                    const reader = response.body.getReader();
                    const decoder = new TextDecoder();
                    let buffer = '';
                    
                    while (true) {
                        const { done, value } = await reader.read();
                        if (done) break;
                        
                        buffer += decoder.decode(value, { stream: true });
                        const lines = buffer.split('\\n');
                        buffer = lines.pop();
                        
                        for (const line of lines) {
                            if (line.startsWith('data: ')) {
                                try {
                                    const data = JSON.parse(line.slice(6));
                                    
                                    if (data.type === 'session' && data.session_id) {
                                        currentSessionId = data.session_id;
                                        document.getElementById('sessionId').textContent = currentSessionId.substring(0, 8) + '...';
                                    } else if (data.type === 'chunk' && data.content) {
                                        assistantContentDiv.innerHTML += data.content;
                                        const messagesContainer = document.getElementById('chatMessages');
                                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                                    } else if (data.type === 'error') {
                                        assistantContentDiv.innerHTML = data.content;
                                    } else if (data.type === 'done') {
                                        const finalContent = assistantContentDiv.innerHTML
                                            .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                                            .replace(/```([\\s\\S]*?)```/g, '<pre><code>$1</code></pre>')
                                            .replace(/`([^`]+)`/g, '<code>$1</code>')
                                            .replace(/\\n/g, '<br>');
                                        assistantContentDiv.innerHTML = finalContent;
                                        break;
                                    }
                                } catch (e) {
                                    console.error('Error parsing streaming data:', e);
                                }
                            }
                        }
                    }
                } catch (error) {
                    console.error('Error sending message:', error);
                    hideTypingIndicator();
                    addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
                } finally {
                    messageInput.disabled = false;
                    sendBtn.disabled = false;
                    sendBtn.textContent = 'Send';
                    messageInput.focus();
                }
            }
            
            function addMessage(content, sender) {
                const messagesContainer = document.getElementById('chatMessages');
                const messageDiv = document.createElement('div');
                messageDiv.className = `message ${sender}`;
                
                const formattedContent = content
                    .replace(/\\*\\*(.*?)\\*\\*/g, '<strong>$1</strong>')
                    .replace(/```([\\s\\S]*?)```/g, '<pre><code>$1</code></pre>')
                    .replace(/`([^`]+)`/g, '<code>$1</code>')
                    .replace(/\\n/g, '<br>');
                
                messageDiv.innerHTML = `
                    <div>${formattedContent}</div>
                    <div class="message-time">${new Date().toLocaleTimeString()}</div>
                `;
                
                messagesContainer.appendChild(messageDiv);
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            function showTypingIndicator() {
                document.getElementById('typingIndicator').classList.add('show');
                const messagesContainer = document.getElementById('chatMessages');
                messagesContainer.scrollTop = messagesContainer.scrollHeight;
            }
            
            function hideTypingIndicator() {
                document.getElementById('typingIndicator').classList.remove('show');
            }
            
            async function newChat() {
                if (confirm('Start a new chat session? This will clear the current conversation.')) {
                    await initializeSession();
                    clearChatDisplay();
                    addMessage('Hello! I\\'m your AI Superset Assistant 🚀\\n\\nI can help you with:\\n• Creating and structuring DAGs\\n• Debugging workflow issues\\n• Performance optimization\\n• Best practices and patterns\\n\\nWhat would you like to know about Apache Superset?', 'assistant');
                }
            }
            
            function clearChat() {
                if (confirm('Clear the current chat history?')) {
                    clearChatDisplay();
                    addMessage('Chat cleared. How can I help you with Apache Superset?', 'assistant');
                }
            }
            
            function clearChatDisplay() {
                const messagesContainer = document.getElementById('chatMessages');
                messagesContainer.innerHTML = '';
            }
            
            function showExamples() {
                const examples = [
                    "How do I create a simple DAG?",
                    "Help me debug a failing task",
                    "What are DAG best practices?",
                    "How can I optimize my workflow performance?",
                    "Show me sensor examples"
                ];
                
                const messageInput = document.getElementById('messageInput');
                const randomExample = examples[Math.floor(Math.random() * examples.length)];
                messageInput.value = randomExample;
                messageInput.focus();
            }
            
            document.getElementById('messageInput').addEventListener('keypress', function(e) {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    document.querySelector('.chat-input-form').dispatchEvent(new Event('submit'));
                }
            });
        </script>
        '''
        
        return self.render_template(
            'ai_assistant.html',
            content=assistant_content,
            title="AI Superset Assistant",
            base_template="appbuilder/baselayout.html",
            appbuilder=self.appbuilder
        )
    
    @expose('/api/new_session', methods=['POST'])
    @admin_only
    @failure_tolerant
    def new_session(self):
        """Create a new chat session"""
        session_id = self.ai_agent.create_session()
        return jsonify({
            'session_id': session_id,
            'status': 'created',
            'message': 'New session initialized'
        })
    
    @expose('/api/chat', methods=['POST'])
    @admin_only
    @failure_tolerant
    def chat_api(self):
        """Handle chat messages with real AI"""
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        try:
            username = getattr(current_user, 'username', 'anonymous') if current_user and current_user.is_authenticated else 'anonymous'
            response, session_id = self.ai_agent.sync_get_response(message, session_id, username)
            return jsonify({
                'response': response,
                'session_id': session_id,
                'timestamp': datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Chat API error: {e}")
            return jsonify({'error': 'Failed to process message'}), 500
    
    @expose('/api/chat_stream', methods=['POST'])
    @admin_only
    @failure_tolerant  
    def chat_stream_api(self):
        """Handle streaming chat messages with real AI"""
        data = request.get_json()
        message = data.get('message', '').strip()
        session_id = data.get('session_id')
        
        if not message:
            return jsonify({'error': 'Message is required'}), 400
        
        def generate_stream():
            """Generator function for streaming responses"""
            try:
                if not session_id or session_id not in self.ai_agent.sessions:
                    new_session_id = self.ai_agent.create_session()
                else:
                    new_session_id = session_id
                        
                username = getattr(current_user, 'username', 'anonymous') if current_user and current_user.is_authenticated else 'anonymous'
                    
                yield f"data: {json.dumps({'type': 'session', 'session_id': new_session_id})}\n\n"
                    
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                    
                async def stream_response():
                    async for chunk in self.ai_agent.get_response_stream(message, new_session_id, username):
                        if chunk and chunk.strip():
                            yield f"data: {json.dumps({'type': 'chunk', 'content': chunk})}\n\n"
                    
                async_gen = stream_response()
                try:
                    while True:
                        try:
                            chunk_data = loop.run_until_complete(async_gen.__anext__())
                            yield chunk_data
                        except StopAsyncIteration:
                            break
                finally:
                    loop.close()
                    
                yield f"data: {json.dumps({'type': 'done'})}\n\n"
                    
            except Exception as e:
                logger.error(f"Streaming chat error: {e}")
                error_msg = json.dumps({
                    'type': 'error', 
                    'content': 'I encountered an error. Please try again.'
                })
                yield f"data: {error_msg}\n\n"
            
        return Response(
            generate_stream(),
            mimetype='text/plain',
            headers={
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Content-Type': 'text/plain; charset=utf-8'
            }
        )
    
    @expose('/api/clear_session', methods=['POST'])
    @admin_only
    @failure_tolerant
    def clear_session(self):
        """Clear a chat session"""
        data = request.get_json()
        session_id = data.get('session_id')
        
        if session_id and session_id in self.ai_agent.sessions:
            del self.ai_agent.sessions[session_id]
            return jsonify({'message': 'Session cleared successfully'})
        
        return jsonify({'error': 'Session not found'}), 404