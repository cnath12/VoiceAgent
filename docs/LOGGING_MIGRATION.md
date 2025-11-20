# Logging Migration Guide

## Overview

This guide helps migrate from print() statements to structured logging.

## Current State

- **155 print() statements** across codebase
  - 110 in `src/main.py`
  - 45 in `src/handlers/`
- Emoji-heavy debug output (🚨, 🔧, ✅, ❌, etc.)
- No consistent log levels
- Not machine-parseable

## Target State

- Structured logging using Python's `logging` module
- Appropriate log levels (DEBUG, INFO, WARNING, ERROR)
- Machine-parseable output for log aggregation
- No emojis in production logs

## Migration Strategy

### 1. Use Structured Logging Utilities

Replace:
```python
print(f"🚨 IMMEDIATE DEBUG: /voice/answer endpoint called!")
```

With:
```python
from src.utils.structured_logging import log_call_event

log_call_event(
    logger,
    event="endpoint_called",
    call_sid=call_sid,
    level=logging.DEBUG,
    endpoint="/voice/answer"
)
```

### 2. Choose Appropriate Log Levels

| Print Statement Pattern | Log Level | Reasoning |
|------------------------|-----------|-----------|
| `print(f"✅ ... created!")` | DEBUG | Detailed diagnostic info |
| `print(f"🔧 Creating ...")` | DEBUG | Internal state changes |
| `print(f"⚠️ WARNING ...")` | WARNING | Unexpected but handled |
| `print(f"❌ FAILED ...")` | ERROR | Operation failed |
| `print(f"🗣️ USER SAID ...")` | INFO | Important business event |
| `print(f"🎯 Extracted ...")` | DEBUG | Data extraction details |

### 3. Structured Fields

Use structured fields instead of string formatting:

Replace:
```python
print(f"🗣️ USER SAID: '{text}' for {call_sid}")
```

With:
```python
log_transcription(
    logger,
    text=text,
    call_sid=call_sid,
    is_final=True
)
```

### 4. Remove Emoji and Excessive Formatting

Replace:
```python
print(f"🔥 IMPORTANT FRAME: {frame_type} direction={direction}")
```

With:
```python
logger.debug(
    "frame_processing",
    extra={
        "frame_type": frame_type,
        "direction": direction
    }
)
```

## Migration Priorities

### Phase 1: Critical Paths (main.py)

1. **WebSocket Events** (lines 389-710)
   - Connection establishment
   - Media frame processing
   - Transcription handling

2. **Pipeline Creation** (lines 91-314)
   - Component initialization
   - Service creation
   - Error handling

3. **Twilio Webhook** (lines 317-384)
   - Incoming call handling
   - TwiML generation

### Phase 2: Handlers

1. **voice_handler.py** - Main orchestrator
2. **insurance_handler.py** - Insurance collection
3. **symptom_handler.py** - Symptom collection
4. **demographics_handler.py** - Demographics
5. **scheduling_handler.py** - Scheduling

### Phase 3: Services & Utils

1. **llm_service.py**
2. **email_service.py**
3. **provider_service.py**
4. **address_service.py**

## Quick Reference

### Common Patterns

#### Before
```python
print(f"🔧 Creating pipeline for {call_sid}...")
print(f"✅ Pipeline created successfully!")
```

#### After
```python
logger.debug("Creating pipeline", extra={"call_sid": call_sid})
logger.info("Pipeline created", extra={"call_sid": call_sid})
```

---

#### Before
```python
print(f"❌ Pipeline creation failed: {e}")
```

#### After
```python
log_error(logger, e, "Pipeline creation failed", call_sid=call_sid)
```

---

#### Before
```python
print(f"\n🗣️ ===== USER SAID: '{text}' ===== (Final Transcription)")
```

#### After
```python
log_transcription(logger, text, call_sid, is_final=True)
```

## Testing

After migration:

```bash
# Run with DEBUG level to see all logs
export LOG_LEVEL=DEBUG
uvicorn src.main:app --reload

# Run with INFO level (production)
export LOG_LEVEL=INFO
uvicorn src.main:app
```

## Validation Checklist

- [ ] All print() statements removed from src/
- [ ] Appropriate log levels used
- [ ] No emojis in log messages
- [ ] Structured fields used for important data
- [ ] Log output parseable by log aggregators
- [ ] PII/PHI redacted from logs
- [ ] Performance impact negligible

## Tools

```bash
# Find remaining print statements
grep -rn "print(" src/

# Count by file
find src/ -name "*.py" -exec grep -c "print(" {} + | grep -v ":0$"
```

## Next Steps

1. Apply migration to main.py (110 statements)
2. Apply migration to handlers (45 statements)
3. Update tests to check logs instead of stdout
4. Add structured logging to CI/CD validation
