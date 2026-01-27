# STT Fallback Setup Guide

## Overview

This guide explains how to set up ElevenLabs STT as a fallback service to prevent session closure when the primary STT service fails.

## Problem

When the primary STT service returns 500 errors, LiveKit retries 3 times, then closes the session. This causes interviews to stop unexpectedly.

## Solution

The FallbackSTT wrapper automatically switches to ElevenLabs STT when the primary STT fails 3 times, preventing session closure.

## Setup

### 1. Install ElevenLabs Plugin

```bash
cd backend
source venv/bin/activate
pip install livekit-plugins-elevenlabs==1.3.6
```

Or add to `requirements.txt`:
```
livekit-plugins-elevenlabs==1.3.6
```

### 2. Get ElevenLabs API Key

1. Sign up at https://elevenlabs.io
2. Go to your profile → API Keys
3. Create a new API key
4. Copy the key

### 3. Configure Environment Variables

Add to `backend/.env` or `backend/.env.local`:

```bash
# ElevenLabs STT Fallback Configuration
ELEVENLABS_STT_API_KEY=your_api_key_here
ELEVENLABS_STT_ENABLED=true
```

### 4. Restart Agent

```bash
pkill -9 -f "python.*agent.py"
cd agent
source ../backend/venv/bin/activate
python3 agent.py dev
```

## How It Works

1. **Primary STT**: Uses self-hosted STT (`https://ai.skillifire.com/api/stt/v1`)
2. **Failure Detection**: Monitors for 500 errors, timeouts, connection issues
3. **Automatic Switch**: After 3 failures, switches to ElevenLabs STT
4. **Recovery**: If primary STT recovers, switches back automatically
5. **Session Protection**: Prevents session closure on STT failures

## Behavior

### Normal Operation
- Uses primary STT (self-hosted)
- Logs: `✅ Primary STT (OpenAI-compatible) initialized`

### On Failure
- Detects recoverable errors (500, timeout, etc.)
- Counts failures (1/3, 2/3, 3/3)
- Switches to ElevenLabs after 3 failures
- Logs: `🔄 Switching to ElevenLabs fallback STT after 3 failures`

### On Recovery
- If primary STT succeeds again, switches back
- Logs: `✅ Primary STT recovered after X failures`

## Logs to Watch

```
✅ FallbackSTT initialized: primary=STT, fallback=ElevenLabs
⚠️  Primary STT failed (1/3): APIStatusError: Internal Server Error
⚠️  Primary STT failed (2/3): APIStatusError: Internal Server Error
⚠️  Primary STT failed (3/3): APIStatusError: Internal Server Error
🔄 Switching to ElevenLabs fallback STT after 3 failures
✅ Fallback STT succeeded
```

## Cost Considerations

- **ElevenLabs STT**: Pay-per-use (check ElevenLabs pricing)
- **Usage**: Only used when primary STT fails
- **Optimization**: Primary STT should be stable to minimize costs

## Troubleshooting

### Fallback Not Activating

1. **Check Configuration**:
   ```bash
   echo $ELEVENLABS_STT_ENABLED
   echo $ELEVENLABS_STT_API_KEY
   ```

2. **Check Plugin Installation**:
   ```bash
   pip list | grep elevenlabs
   ```

3. **Check Logs**:
   ```bash
   grep -i "fallback\|elevenlabs" agent/agent.log
   ```

### Fallback Also Failing

- Check ElevenLabs API key validity
- Check ElevenLabs account quota/limits
- Check network connectivity to ElevenLabs

### Primary STT Not Recovering

- Check primary STT server health
- Restart primary STT server if needed
- Monitor primary STT server logs

## Disabling Fallback

To disable fallback (not recommended):

```bash
ELEVENLABS_STT_ENABLED=false
```

Or remove the API key:
```bash
# Comment out or remove
# ELEVENLABS_STT_API_KEY=...
```

## Notes

- Fallback is **optional** - interviews will work without it, but sessions may close on STT failures
- Fallback only activates after **3 consecutive failures**
- Fallback automatically switches back to primary when it recovers
- ElevenLabs STT is a cloud service - ensure API key has sufficient quota

