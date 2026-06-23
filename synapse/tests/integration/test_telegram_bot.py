import pytest
from unittest.mock import AsyncMock, patch
from telegram import Update, User, Chat, Message
from app.telegram_bot import handle_message, session_service

# Mock Update object
@pytest.fixture
def mock_update():
    update = AsyncMock(spec=Update)
    update.effective_chat = AsyncMock(spec=Chat)
    update.effective_chat.id = 123456789
    update.message = AsyncMock(spec=Message)
    update.message.text = "Hello, what is your purpose?"
    return update

# Mock Context
@pytest.fixture
def mock_context():
    context = AsyncMock()
    context.bot = AsyncMock()
    return context

@pytest.mark.asyncio
async def test_handle_message_triggers_agent(mock_update, mock_context):
    """
    Test that handle_message correctly calls the runner 
    and sends a response back to Telegram.
    """
    # Patch the runner to avoid real API calls to Gemini
    with patch("app.telegram_bot.runner.run_async") as mock_run:
        # Define a mock async generator for the agent response
        class MockAsyncGenerator:
            def __init__(self):
                self.called = False
            def __aiter__(self):
                return self
            async def __anext__(self):
                if self.called:
                    raise StopAsyncIteration
                self.called = True
                
                class MockEvent:
                    def is_final_response(self): return True
                    @property
                    def content(self):
                        class MockContent:
                            parts = [type('obj', (object,), {'text': 'I am Synapse, your GBP assistant.'})]
                        return MockContent()
                return MockEvent()

        # runner.run_async must return this async generator
        mock_run.return_value = MockAsyncGenerator()

        # Call the handler
        await handle_message(mock_update, mock_context)

        # Verify runner was called
        mock_run.assert_called_once()
        
        # Verify bot sent the message back
        mock_context.bot.send_message.assert_called_once()
        args, kwargs = mock_context.bot.send_message.call_args
        assert kwargs['text'] == "I am Synapse, your GBP assistant."
        assert kwargs['chat_id'] == 123456789
