# Conversation History Management

## Overview

This document describes the conversation history management system implemented to prevent context window overflow and enable long-running interviews.

## Problem

After 4-5 conversation exchanges, the agent would stop responding. This was caused by:
- **Context Window Overflow**: The LLM model (`qwen-14b`) has a limited context window (~8K tokens)
- **Unbounded History**: Conversation messages accumulated indefinitely
- **No Truncation**: Old messages were never removed, causing context to exceed limits

## Solution

Implemented a **sliding window conversation history manager** that:
1. **Tracks conversation messages** separately from system instructions
2. **Truncates old messages** when limits are approached
3. **Preserves recent context** to maintain conversation continuity
4. **Always keeps system instructions** intact

## Implementation

### Components

1. **`ConversationHistoryManager`** (`agent/services/conversation_history_manager.py`)
   - Tracks user and assistant messages
   - Estimates token counts
   - Truncates old messages using sliding window
   - Maintains minimum message count for continuity

2. **`HistoryManagedLLMWrapper`** (`backend/app/services/history_managed_llm_wrapper.py`)
   - Wraps LLM chat calls to intercept messages
   - Manages conversation history before passing to LLM
   - Integrates with transcript forwarding

3. **Configuration** (`backend/app/config.py`)
   - `MAX_CONVERSATION_TOKENS`: Max tokens for conversation (default: 4000)
   - `MAX_CONVERSATION_MESSAGES`: Max messages to keep (default: 20)
   - `MIN_CONVERSATION_MESSAGES`: Minimum messages to always keep (default: 6)

### How It Works

1. **Message Interception**: When LiveKit Agent calls `LLM.chat()`, the wrapper intercepts the call
2. **History Management**: Extracts conversation messages, manages them with truncation
3. **Truncation Logic**: Removes oldest messages when:
   - Message count exceeds `MAX_CONVERSATION_MESSAGES`, OR
   - Token count exceeds `MAX_CONVERSATION_TOKENS`
4. **Message Passing**: Passes truncated history + system instructions to LLM
5. **Continuity**: Always keeps at least `MIN_CONVERSATION_MESSAGES` for context

## Configuration

### Environment Variables

Add these to your `.env` file:

```bash
# Conversation History Management
MAX_CONVERSATION_TOKENS=4000      # Max tokens for conversation (excluding system)
MAX_CONVERSATION_MESSAGES=20      # Max messages to keep
MIN_CONVERSATION_MESSAGES=6       # Minimum messages to always keep
```

### Token Budget Breakdown

For `qwen-14b` with ~8K token context window:
- **System Instructions**: ~3500 tokens (fixed)
- **Conversation History**: ~4000 tokens (managed, truncates when exceeded)
- **Reserve**: ~500 tokens (buffer for new messages)

## LLM Model Requirements

### Current Model: `qwen-14b`

**Context Window**: ~8K tokens (verify with your model provider)

**Recommendations**:
1. **Verify Context Window**: Confirm your `qwen-14b` instance supports at least 8K tokens
2. **Model Configuration**: Ensure your LLM API accepts the full context window
3. **Token Counting**: The system uses conservative token estimation (~3.5 chars/token)
4. **Alternative Models**: For longer conversations, consider models with larger context windows:
   - `qwen-72b`: 32K tokens
   - `llama-3-70b`: 8K+ tokens
   - `gpt-4`: 8K-128K tokens (depending on version)

### Model-Specific Settings

If your model has a different context window, adjust `MAX_CONVERSATION_TOKENS`:

```bash
# For 16K token model (e.g., some qwen variants)
MAX_CONVERSATION_TOKENS=12000

# For 32K token model
MAX_CONVERSATION_TOKENS=28000
```

**Formula**: `MAX_CONVERSATION_TOKENS = (Model Context Window) - (System Instructions) - (Reserve)`

## Testing

### Verify Long Conversations

1. **Start an interview** and have 10+ exchanges
2. **Check logs** for truncation messages:
   ```
   🗑️  Truncated conversation history: removed X old messages (Y tokens)
   ```
3. **Verify continuity**: Agent should maintain context despite truncation
4. **Monitor tokens**: Check logs for token counts:
   ```
   📊 History managed: X conversation messages (Y tokens)
   ```

### Expected Behavior

- ✅ Conversations can run for 30+ minutes
- ✅ Old messages are removed when limits approached
- ✅ Recent context (last 6+ messages) always preserved
- ✅ System instructions never truncated
- ✅ No context window overflow errors

## Troubleshooting

### Agent Still Stops After Few Messages

1. **Check Model Context Window**: Verify your model supports the expected token count
2. **Reduce `MAX_CONVERSATION_TOKENS`**: If model has smaller context window
3. **Check Logs**: Look for truncation messages to verify it's working
4. **Verify Configuration**: Ensure environment variables are loaded

### Messages Being Truncated Too Aggressively

1. **Increase `MAX_CONVERSATION_TOKENS`**: If model supports larger context
2. **Increase `MIN_CONVERSATION_MESSAGES`**: To preserve more context
3. **Check Token Estimation**: Verify token counting is accurate

### Context Lost Between Messages

1. **Increase `MIN_CONVERSATION_MESSAGES`**: Preserve more recent history
2. **Check Truncation Logic**: Ensure it's not removing too many messages
3. **Verify Message Order**: Ensure messages are in correct chronological order

## Architecture Notes

- **LiveKit Agent**: Manages messages internally and passes them to `LLM.chat()`
- **Wrapper**: Intercepts calls, manages history, passes truncated version to LLM
- **History Manager**: Tracks messages separately, handles truncation logic
- **Transcript Service**: Unchanged, continues to forward transcripts to frontend

## Future Enhancements

1. **Conversation Summarization**: Summarize old messages instead of deleting
2. **Adaptive Truncation**: Adjust limits based on conversation length
3. **Token Counting**: Use actual model tokenizer for accurate counting
4. **History Persistence**: Save conversation history for later reference

