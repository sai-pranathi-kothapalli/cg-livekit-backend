# STT Error Troubleshooting Guide

## Problem: Session Closes Due to STT 500 Errors

### Error Pattern
```
APIStatusError: Internal Server Error (status_code=500)
AgentSession is closing due to unrecoverable error
type='stt_error' recoverable=False
```

### Root Cause
The STT (Speech-to-Text) API endpoint is returning **500 Internal Server Error**. LiveKit's STT plugin retries 3 times, then marks the error as unrecoverable and closes the session.

### STT Configuration
- **Endpoint**: `https://ai.skillifire.com/api/stt/v1`
- **Model**: `medium`
- **Retry Logic**: Built into LiveKit (3 attempts)

## Solutions

### 1. Check STT API Server Health

```bash
# Test STT API accessibility
curl -X POST "https://ai.skillifire.com/api/stt/v1/audio/transcriptions" \
  -H "Content-Type: application/json" \
  -d '{"model":"medium"}'
```

**Expected**: Should return validation error (needs file), not 500 error.

### 2. Check STT Server Logs

Check the STT server logs for:
- Memory issues
- Model loading errors
- Request timeout errors
- Resource exhaustion

### 3. STT Server Issues to Check

1. **Server Overload**: Too many concurrent requests
2. **Model Loading**: Model not loaded or crashed
3. **Memory Issues**: Out of memory errors
4. **Network Issues**: Intermittent connectivity
5. **API Version Mismatch**: Incompatible API version

### 4. Temporary Workaround

If STT errors are intermittent:
- **Restart STT Server**: May resolve temporary issues
- **Reduce Load**: Limit concurrent interviews
- **Monitor**: Watch for patterns (time of day, specific audio formats)

### 5. Long-term Solutions

1. **STT Server Monitoring**: Add health checks and monitoring
2. **Load Balancing**: Distribute STT requests across multiple servers
3. **Fallback STT**: Implement fallback STT service
4. **Error Recovery**: Improve STT server error handling

## Prevention

### Monitor STT Health
- Check STT API before starting interviews
- Log STT errors with context
- Alert on repeated STT failures

### Best Practices
1. **Keep STT Server Stable**: Ensure adequate resources
2. **Monitor Resource Usage**: CPU, memory, disk
3. **Regular Health Checks**: Ping STT API periodically
4. **Error Logging**: Log all STT errors for analysis

## Current Behavior

- **STT Retries**: 3 automatic retries (0.1s, 2.0s, 2.0s delays)
- **After 3 Failures**: Session closes with "unrecoverable error"
- **Error Type**: `stt_error` with `recoverable=False`

## Notes

- STT errors are handled at the LiveKit framework level
- We cannot easily override LiveKit's STT retry logic
- The fix must be at the STT API server level
- Ensure STT API server is stable and has adequate resources

