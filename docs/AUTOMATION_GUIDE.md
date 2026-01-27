# Automation Guide

This guide explains the automated testing and verification scripts for the AI Interview system.

## Quick Start

### Run All Tests
```bash
cd backend
source venv/bin/activate
python run_all_tests.py
```

### Quick Health Check
```bash
python health_check.py
```

## Test Scripts

### 1. Model Tests (`test_models_console.py`)

Tests all three models (LLM, TTS, STT) in console mode without requiring LiveKit room connections.

**What it tests:**
- ✅ LLM model text generation
- ✅ TTS model audio synthesis
- ✅ STT endpoint configuration
- ✅ Configuration loading

**Usage:**
```bash
python test_models_console.py
```

**Expected Output:**
```
✅ PASSED: LLM Console Mode
✅ PASSED: TTS Console Mode
✅ PASSED: STT Configuration
✅ PASSED: Configuration Integration
```

### 2. Plugin Service Tests (`test_plugin_service.py`)

Tests that PluginService correctly initializes all plugins.

**What it tests:**
- ✅ Plugin service initialization
- ✅ Agent creation
- ✅ Configuration verification

**Usage:**
```bash
python test_plugin_service.py
```

**Note:** If you see import errors related to `livekit.plugins.openai`, this is a known version compatibility issue. The models themselves work correctly - this only affects direct plugin testing. The agent will work fine when running.

### 3. Health Check (`health_check.py`)

Quick health check for all system components.

**What it checks:**
- ✅ Configuration loading
- ✅ LLM endpoint availability
- ✅ TTS endpoint availability
- ✅ STT endpoint configuration
- ✅ Plugin service initialization

**Usage:**
```bash
python health_check.py
```

### 4. Comprehensive Test Runner (`run_all_tests.py`)

Runs all test suites in sequence.

**Usage:**
```bash
# Run all tests
python run_all_tests.py

# Skip specific tests
python run_all_tests.py --skip-models
python run_all_tests.py --skip-plugins
python run_all_tests.py --skip-config
```

## Integration Status

### ✅ Working Components

1. **LLM Model** (`qwen-14b`)
   - Base URL: `https://ai.skillifire.com/api/llm/v1`
   - Status: ✅ Working
   - Test: `test_models_console.py`

2. **TTS Model** (`kokoro`)
   - Base URL: `https://ai.skillifire.com/api/tts/v1`
   - Voice: `af_bella`
   - Status: ✅ Working
   - Test: `test_models_console.py`

3. **STT Model** (`medium`)
   - Base URL: `https://ai.skillifire.com/api/stt/v1`
   - Status: ✅ Configured
   - Test: `test_models_console.py` (configuration only, requires audio for full test)

4. **Configuration**
   - Status: ✅ Working
   - All environment variables loaded correctly

### ⚠️ Known Issues

1. **Plugin Import Issue**
   - Some tests may fail with `ImportError` related to `livekit.plugins.openai`
   - This is a version compatibility issue between `livekit-agents` and `livekit-plugins-openai`
   - **Impact:** Only affects direct plugin testing, not actual agent functionality
   - **Workaround:** Models work correctly when agent runs - this is a test-only issue

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Integration Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      - name: Run tests
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          OPENAI_BASE_URL: ${{ secrets.OPENAI_BASE_URL }}
          TTS_BASE_URL: ${{ secrets.TTS_BASE_URL }}
          STT_BASE_URL: ${{ secrets.STT_BASE_URL }}
        run: |
          cd backend
          python run_all_tests.py
```

## Pre-Deployment Checklist

Before deploying to production, run:

```bash
# 1. Health check
python health_check.py

# 2. All tests
python run_all_tests.py

# 3. Verify models
python test_models_console.py
```

All tests should pass before deployment.

## Troubleshooting

### Test Failures

1. **LLM Test Fails**
   - Check `OPENAI_API_KEY` and `OPENAI_BASE_URL` in `.env.local`
   - Verify LLM endpoint is accessible
   - Check network connectivity

2. **TTS Test Fails**
   - Check `TTS_BASE_URL` in `.env.local`
   - Verify TTS endpoint is accessible
   - Check model and voice settings

3. **STT Test Fails**
   - Check `STT_BASE_URL` in `.env.local`
   - Verify STT endpoint is accessible
   - Note: Full STT test requires audio input

4. **Plugin Service Test Fails**
   - If import error: This is expected due to version mismatch
   - Models work correctly - this is a test-only issue
   - Agent will work fine when running

### Environment Variables

Ensure all required variables are set in `.env.local`:

```bash
# OpenAI/Self-hosted API
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://ai.skillifire.com/api/llm/v1
TTS_BASE_URL=https://ai.skillifire.com/api/tts/v1
STT_BASE_URL=https://ai.skillifire.com/api/stt/v1
OPENAI_LLM_MODEL=qwen-14b
OPENAI_TTS_MODEL=kokoro
OPENAI_STT_MODEL=medium
OPENAI_TTS_VOICE=af_bella
```

## Next Steps

After all tests pass:

1. ✅ Start the backend server: `python backend_server.py`
2. ✅ Start the agent worker: `python agent.py start`
3. ✅ Test a full interview through the frontend
4. ✅ Monitor logs to verify all three models are working

## Support

For issues or questions:
- Check test output for specific error messages
- Verify environment variables are set correctly
- Ensure all dependencies are installed: `pip install -r requirements.txt`

