# Console Mode Testing Guide

## Overview

Console mode allows you to test the interview agent directly in your terminal with full audio input/output support. This is perfect for testing all three models (STT, LLM, TTS) in real-time.

## Quick Start

### Option 1: Using the dedicated script
```bash
cd backend
source venv/bin/activate
python run_console_agent.py
```

### Option 2: Using agent.py directly
```bash
cd backend
source venv/bin/activate
python agent.py console
```

## What Gets Tested

When you run the agent in console mode, you're testing:

1. **STT (Speech-to-Text)**
   - Your microphone input is captured
   - Speech is transcribed to text using the self-hosted STT model
   - Transcription appears in the console

2. **LLM (Large Language Model)**
   - Transcribed text is sent to the LLM
   - The agent processes your input and generates a response
   - Interview logic and instructions are applied

3. **TTS (Text-to-Speech)**
   - The LLM's response is converted to speech
   - Audio is played through your speakers/headphones
   - You hear the agent's response

## Requirements

### Hardware
- **Microphone**: For audio input (built-in or external)
- **Speakers/Headphones**: For audio output

### Software
- Python 3.9+ with virtual environment activated
- All dependencies installed: `pip install -r requirements.txt`
- Environment variables configured in `.env.local`

### Permissions
- Microphone access (macOS/Linux may prompt)
- Audio output permissions

## How to Use

1. **Start the agent:**
   ```bash
   python run_console_agent.py
   ```

2. **Wait for initialization:**
   - The agent will initialize all plugins (STT, LLM, TTS, VAD)
   - You'll see configuration logs
   - Wait for "Agent ready" or similar message

3. **Start speaking:**
   - Speak naturally into your microphone
   - The agent will transcribe your speech
   - Wait for the agent to respond

4. **Listen to responses:**
   - The agent will respond with audio
   - You'll also see the text transcript in the console

5. **Stop the agent:**
   - Press `Ctrl+C` to stop

## Testing Scenarios

### Basic Test
```
You: "Hello, my name is John"
Agent: [Responds with greeting and introduction]
```

### Interview Test
```
You: "I am applying for the RRB PO position"
Agent: [Starts interview process]
```

### Full Interview Flow
- Test Round 1: Self Introduction
- Test Round 2: GK & Current Affairs
- Test Round 3: Domain Knowledge
- Test Round 4: Banking Knowledge
- Test Round 5: Situational Questions

## Troubleshooting

### No Audio Input
- **Check microphone permissions**: System Settings > Privacy > Microphone
- **Test microphone**: Use system audio settings to verify it's working
- **Check console logs**: Look for STT initialization errors

### No Audio Output
- **Check speakers/headphones**: Verify they're connected and working
- **Check system volume**: Make sure volume is not muted
- **Check console logs**: Look for TTS initialization errors

### Agent Not Responding
- **Check LLM endpoint**: Run `python health_check.py`
- **Check network**: Verify connectivity to self-hosted API
- **Check logs**: Look for error messages in console

### Import Errors
- **Version mismatch**: Some import errors are expected (non-blocking)
- **Models still work**: The agent will function correctly despite import warnings
- **Check requirements**: Run `pip install -r requirements.txt`

## Expected Console Output

```
✅ Loading environment from /path/to/.env.local
======================================================================
🎤 CONSOLE MODE AGENT - AUDIO TESTING
======================================================================

Agent Name: my-interviewer

📋 What this does:
   - Starts the agent in console mode with audio support
   ...

🚀 Starting agent in console mode...

[Agent initialization logs]
[Plugin initialization logs]
[STT, LLM, TTS configuration logs]

[Ready to accept audio input]
```

## Tips for Testing

1. **Speak clearly**: Enunciate your words for better STT accuracy
2. **Wait for responses**: Don't interrupt the agent while it's speaking
3. **Check console logs**: Monitor for any errors or warnings
4. **Test incrementally**: Start with simple phrases, then test full interview flow
5. **Monitor model usage**: Check that all three models are being used

## Next Steps

After testing in console mode:

1. ✅ Verify all three models work correctly
2. ✅ Test the full interview flow
3. ✅ Check for any errors or issues
4. 🚀 Deploy to production or test with frontend

## Alternative Testing Methods

If console mode doesn't work:

1. **Health Check**: `python health_check.py`
2. **Model Tests**: `python test_models_console.py`
3. **Frontend Testing**: Use the web frontend to test with real UI
4. **Dev Mode**: `python agent.py dev` (connects to LiveKit Cloud)

## Support

For issues:
- Check `AUTOMATION_GUIDE.md` for troubleshooting
- Review console logs for specific error messages
- Verify all environment variables are set correctly
- Run health check: `python health_check.py`

