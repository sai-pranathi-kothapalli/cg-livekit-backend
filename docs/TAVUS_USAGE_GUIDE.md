# Tavus Avatar Integration Guide

## Overview

Tavus is a video avatar service that provides realistic AI-powered video avatars for real-time conversations. This guide explains how Tavus was integrated with LiveKit Agents and how to use it in similar projects.

**Note:** Tavus has been removed from this project. This document serves as a reference for future implementations.

---

## What is Tavus?

Tavus provides:
- **Video Avatars**: Realistic AI-powered video representations
- **Real-time Conversations**: Live video streaming during interviews
- **Audio + Video**: Provides both video feed and audio (TTS) in one package
- **Customizable Personas**: Use pre-created personas or replicas

---

## Integration Architecture

### How Tavus Works with LiveKit

```
LiveKit Room
    ↓
Agent Session (STT, LLM, TTS, VAD)
    ↓
Tavus Avatar Session (Video + Audio)
    ↓
Suppresses TTS when active
```

### Key Components

1. **Tavus Plugin** (`livekit-plugins-tavus`)
   - Provides `tavus.AvatarSession` class
   - Handles video streaming and audio output

2. **Conditional TTS Wrapper**
   - Tracks Tavus activation state
   - Suppresses OpenAI TTS when Tavus is active
   - Re-enables TTS if Tavus fails

3. **Plugin Service Integration**
   - Checks Tavus configuration
   - Initializes Tavus avatar session
   - Handles error cases and fallback

---

## Configuration

### Environment Variables

```bash
# Required
TAVUS_API_KEY=your_tavus_api_key

# Use either persona_id OR replica_id (not both)
TAVUS_PERSONA_ID=your_persona_id
# OR
TAVUS_REPLICA_ID=your_replica_id
```

### Configuration Class

```python
@dataclass
class TavusConfig:
    """Tavus Avatar configuration"""
    api_key: Optional[str] = None
    persona_id: Optional[str] = None
    replica_id: Optional[str] = None
```

---

## Implementation Details

### 1. Plugin Service Integration

#### Check Configuration

```python
def _check_tavus_config(self) -> bool:
    """Check if Tavus avatar is configured."""
    tavus_config = self.config.tavus
    
    if tavus_config.api_key and (tavus_config.persona_id or tavus_config.replica_id):
        return True
    return False
```

#### Initialize Tavus Avatar

```python
async def start_tavus_avatar(
    self,
    session: AgentSession,
    room: rtc.Room
) -> tavus.AvatarSession:
    """Start Tavus avatar session and disable OpenAI TTS."""
    
    avatar_plugin = tavus.AvatarSession(
        api_key=tavus_config.api_key,
        persona_id=tavus_config.persona_id,
        replica_id=tavus_config.replica_id,
    )
    
    await avatar_plugin.start(session, room)
    
    # Mark Tavus as active and suppress TTS
    self._tavus_active = True
    if self._tts_wrapper:
        self._tts_wrapper.set_tavus_active(True)
    
    return avatar_plugin
```

### 2. Conditional TTS Wrapper

The wrapper tracks Tavus state and suppresses TTS when Tavus is active:

```python
class ConditionalTTSWrapper:
    """Wrapper for TTS that tracks Tavus activation state."""
    
    def __init__(self, tts_plugin: Any):
        self._tts = tts_plugin
        self._tavus_active = False
    
    def set_tavus_active(self, active: bool):
        """Set Tavus activation state."""
        self._tavus_active = active
        if active:
            logger.info("🔇 Tavus is active - TTS will be suppressed")
        else:
            logger.info("🔊 Tavus inactive - TTS is active")
```

### 3. Agent Entrypoint Integration

```python
# After AgentSession is started
if plugins.get("use_tavus"):
    try:
        avatar_plugin = await plugin_service.start_tavus_avatar(session, room)
        logger.info("✅ Tavus Avatar session started!")
    except Exception as e:
        # Handle errors and fallback to TTS
        plugin_service.set_tavus_inactive()
        logger.warning(f"Tavus failed: {e}")
```

---

## Usage Flow

### 1. Setup

1. **Get Tavus Account**
   - Sign up at https://tavus.io
   - Create a persona or replica
   - Get API key from dashboard

2. **Configure Environment**
   ```bash
   TAVUS_API_KEY=your_api_key
   TAVUS_PERSONA_ID=your_persona_id
   # OR
   TAVUS_REPLICA_ID=your_replica_id
   ```

3. **Install Plugin**
   ```bash
   pip install livekit-plugins-tavus
   ```

### 2. Initialization

The system automatically:
- Checks if Tavus is configured
- Initializes TTS wrapper
- Prepares for Tavus activation

### 3. Session Start

When an interview session starts:
1. AgentSession is created with TTS plugin
2. If Tavus is configured, avatar session starts
3. Tavus provides video + audio
4. OpenAI TTS is suppressed automatically

### 4. Fallback Handling

If Tavus fails:
- Error is logged with details
- OpenAI TTS automatically re-enables
- Interview continues with audio-only TTS

---

## Error Handling

### Common Errors

#### 1. Out of Credits (402)
```
Error: "out of conversational credits"
Solution: Add credits to your Tavus account at https://tavus.io
```

#### 2. Invalid API Key (401)
```
Error: "unauthorized"
Solution: Check your TAVUS_API_KEY in .env
```

#### 3. Persona/Replica Not Found (404)
```
Error: "not found"
Solution: Verify TAVUS_PERSONA_ID or TAVUS_REPLICA_ID is correct
```

#### 4. Access Forbidden (403)
```
Error: "forbidden"
Solution: Check API key permissions and account access
```

### Error Handling Code

```python
try:
    avatar_plugin = await plugin_service.start_tavus_avatar(session, room)
except Exception as e:
    error_msg = str(e)
    
    # Re-enable TTS since Tavus failed
    plugin_service.set_tavus_inactive()
    
    if "out of conversational credits" in error_msg or "402" in error_msg:
        logger.warning("Tavus Avatar failed - Out of credits")
    elif "401" in error_msg or "unauthorized" in error_msg.lower():
        logger.warning("Tavus Avatar failed - Invalid API key")
    elif "404" in error_msg or "not found" in error_msg.lower():
        logger.warning("Tavus Avatar failed - Persona/Replica not found")
    elif "403" in error_msg or "forbidden" in error_msg.lower():
        logger.warning("Tavus Avatar failed - Access forbidden")
    else:
        logger.warning(f"Tavus Avatar failed - {error_msg}")
    
    logger.info("✅ Fallback: OpenAI TTS is now active")
```

---

## Best Practices

### 1. Always Have a Fallback

- Never rely solely on Tavus
- Always configure TTS as fallback
- Test fallback behavior

### 2. Error Handling

- Catch all Tavus exceptions
- Log detailed error information
- Automatically fallback to TTS
- Don't fail the interview if Tavus fails

### 3. Configuration

- Use environment variables
- Make Tavus optional (not required)
- Provide clear configuration messages

### 4. Testing

- Test with Tavus configured
- Test with Tavus unconfigured
- Test Tavus failure scenarios
- Verify TTS fallback works

---

## Code Structure

### Files Involved

1. **`app/config.py`**
   - `TavusConfig` dataclass
   - Configuration loading from environment

2. **`app/services/plugin_service.py`**
   - `_check_tavus_config()` - Check configuration
   - `start_tavus_avatar()` - Start avatar session
   - `set_tavus_inactive()` - Disable Tavus
   - `ConditionalTTSWrapper` - TTS wrapper class

3. **`app/agents/entrypoint.py`**
   - `_start_tavus_avatar()` - Error handling wrapper
   - Integration with agent session

### Dependencies

```python
from livekit.plugins import tavus
```

```txt
livekit-plugins-tavus==1.3.6
```

---

## Integration Example

### Complete Integration Code

```python
from livekit.plugins import tavus
from livekit.agents import AgentSession
from livekit import rtc

# 1. Check configuration
tavus_config = config.tavus
if tavus_config.api_key and (tavus_config.persona_id or tavus_config.replica_id):
    use_tavus = True
else:
    use_tavus = False

# 2. Initialize TTS (required by AgentSession)
tts_plugin = openai.TTS(...)
tts_wrapper = ConditionalTTSWrapper(tts_plugin)

# 3. Create AgentSession
session = AgentSession(
    stt=stt_plugin,
    llm=llm_plugin,
    tts=tts_wrapper,  # Wrapped TTS
    vad=vad_plugin,
)

# 4. Start session
await session.start(room=room, agent=agent)

# 5. Start Tavus if configured
if use_tavus:
    try:
        avatar_plugin = tavus.AvatarSession(
            api_key=tavus_config.api_key,
            persona_id=tavus_config.persona_id,
            replica_id=tavus_config.replica_id,
        )
        await avatar_plugin.start(session, room)
        tts_wrapper.set_tavus_active(True)
        logger.info("✅ Tavus Avatar active")
    except Exception as e:
        logger.warning(f"Tavus failed: {e}")
        tts_wrapper.set_tavus_active(False)
        # Interview continues with TTS only
```

---

## Troubleshooting

### Tavus Not Starting

1. **Check Configuration**
   ```bash
   echo $TAVUS_API_KEY
   echo $TAVUS_PERSONA_ID
   ```

2. **Verify API Key**
   - Test API key with Tavus dashboard
   - Check account status and credits

3. **Check Logs**
   - Look for Tavus initialization messages
   - Check for error details

### Double Audio Issue

- **Symptom**: Hearing both Tavus and TTS audio
- **Cause**: TTS not properly suppressed
- **Solution**: Verify `ConditionalTTSWrapper` is working
- **Check**: AgentSession should suppress TTS when Tavus is active

### Video Not Showing

- **Symptom**: Audio works but no video
- **Cause**: Tavus video track not published
- **Solution**: Check LiveKit room tracks
- **Verify**: Tavus avatar session started successfully

---

## Cost Considerations

### Tavus Pricing

- **Conversational Credits**: Charged per minute of video
- **API Calls**: May have rate limits
- **Account Limits**: Check your plan limits

### Cost Optimization

1. **Use TTS for Development**: Only use Tavus in production
2. **Monitor Usage**: Track conversational credits
3. **Set Alerts**: Get notified when credits are low
4. **Fallback Strategy**: Always have TTS as backup

---

## Migration Notes

### Why Tavus Was Removed

- **Cost**: Tavus charges per minute of video
- **Complexity**: Adds another service dependency
- **Optional Feature**: Not required for core functionality
- **TTS Sufficient**: Audio-only TTS works well for interviews

### If You Want to Re-add Tavus

1. **Install Plugin**
   ```bash
   pip install livekit-plugins-tavus==1.3.6
   ```

2. **Add Configuration**
   - Add `TavusConfig` back to `config.py`
   - Add environment variables

3. **Restore Code**
   - Uncomment Tavus-related code in `plugin_service.py`
   - Restore `_start_tavus_avatar()` in `entrypoint.py`
   - Add Tavus import back

4. **Test**
   - Test with Tavus configured
   - Test fallback behavior
   - Verify error handling

---

## Summary

Tavus provides video avatars for real-time conversations but adds:
- **Cost**: Per-minute charges
- **Complexity**: Additional service dependency
- **Optional**: Not required for core interview functionality

The implementation used:
- Conditional TTS wrapper to suppress TTS when Tavus is active
- Error handling with automatic fallback to TTS
- Optional configuration (works without Tavus)

For most use cases, audio-only TTS is sufficient and more cost-effective.

---

**Document Version:** 1.0  
**Last Updated:** January 2026  
**Status:** Reference Only (Tavus removed from project)

