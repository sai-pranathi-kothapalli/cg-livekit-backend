# Agent Duration Adaptation

## Overview

The interview agent now automatically adapts its behavior based on the interview duration. The LLM divides time proportionally and adjusts question selection, phase timing, and conversation flow to fit the available time.

## How It Works

### 1. **Duration Detection**
- System detects interview duration from slot (`end_time - start_time`)
- Falls back to default 30 minutes if no slot info
- Duration is passed to `ProfessionalArjun` agent during initialization

### 2. **Dynamic Instruction Adaptation**
The `_adapt_instructions_for_duration()` method modifies the agent's instructions:

**Time Tracking (Proportional):**
- 0-33%: Background, family, education
- 33-66%: Career choice, banking knowledge
- 66-90%: Job readiness, strengths
- 90-100%: Closing

**Phase Timing (Proportional):**
- Intro: 10% of duration (min 0.5 min)
- Main Interview: 85% of duration
- Closing: 5% of duration (min 0.5 min)

**Question Count:**
- Estimated as: `main_minutes / 2` (roughly 1 question per 2 minutes)
- Minimum: 2 questions

### 3. **Duration-Specific Guidance**

#### 5-Minute Interviews:
- **Intro (30 sec)**: Name + location only
- **Main (4 min)**: 2-3 key questions
  - 1 background question
  - 1-2 banking/GK questions
- **Closing (30 sec)**: Brief thank you
- **Strategy**: Very focused, skip detailed follow-ups

#### 10-Minute Interviews:
- **Intro (1 min)**: Name + brief introduction
- **Main (8 min)**: 4-6 questions
  - 2 background questions
  - 2-3 banking/GK questions
  - 1 job readiness question
- **Closing (1 min)**: Thank you + brief feedback
- **Strategy**: Cover key areas efficiently, limit follow-ups to 1 per topic

#### 15-Minute Interviews:
- **Intro (1-2 min)**: Name + introduction
- **Main (12-13 min)**: 6-8 questions
  - 2-3 background questions
  - 3-4 banking/GK questions
  - 1-2 job readiness questions
- **Closing (1 min)**: Thank you + feedback
- **Strategy**: Balanced coverage, brief follow-ups allowed

#### 30-Minute Interviews (Default):
- **Intro (3-4 min)**: Comprehensive introduction
- **Main (22-23 min)**: 10-15 questions
  - Full coverage of all areas
  - Natural follow-ups
- **Closing (3-4 min)**: Comprehensive feedback
- **Strategy**: Natural flow, explore interesting threads

#### 45+ Minute Interviews:
- **Intro (4-5 min)**: Comprehensive introduction
- **Main (37-38 min)**: 15-20 questions
  - Deep dive into all areas
  - Multiple follow-up questions
  - Explore interesting threads in detail
- **Closing (3-4 min)**: Comprehensive feedback
- **Strategy**: Thorough assessment, explore topics in depth

## Example Adaptations

### 10-Minute Interview:
```
Title: "RRB/IBPS Officer Scale-I Interview (10 Minutes)"

Time Tracking:
- 0-3 min: Background, family, education
- 3-6 min: Career choice, banking knowledge
- 6-9 min: Job readiness, strengths
- 9-10 min: Closing

Phase 1: WELCOME (1 min)
Phase 2: MAIN INTERVIEW (8 min)
Phase 3: CLOSING (1 min)

Question Guidance: "You'll only ask approximately 4 questions in this 10-minute interview."
```

### 5-Minute Interview:
```
Title: "RRB/IBPS Officer Scale-I Interview (5 Minutes)"

Time Tracking:
- 0-1 min: Background, family, education
- 1-3 min: Career choice, banking knowledge
- 3-4 min: Job readiness, strengths
- 4-5 min: Closing

Phase 1: WELCOME (0.5 min)
Phase 2: MAIN INTERVIEW (4 min)
Phase 3: CLOSING (0.5 min)

Question Guidance: "You'll only ask approximately 2 questions in this 5-minute interview."

Duration-Specific Guidance:
- Brief intro (30 seconds)
- Main interview (4 minutes): 2-3 key questions
- Closing (30 seconds): Brief thank you
- Strategy: Very focused, skip detailed follow-ups
```

## Benefits

✅ **Flexible Scheduling**: Support interviews of any duration (5, 10, 15, 30, 45+ minutes)
✅ **Proportional Time Management**: LLM divides time intelligently based on duration
✅ **Appropriate Question Count**: Agent knows how many questions to ask
✅ **Natural Adaptation**: Instructions adapt automatically, no manual configuration needed
✅ **Consistent Quality**: Maintains interview quality regardless of duration

## Technical Details

### Code Flow:
1. `entrypoint.py` detects `interview_duration_minutes` from slot
2. Passes duration to `ProfessionalArjun(duration_minutes=...)`
3. `_adapt_instructions_for_duration()` modifies instructions
4. Agent uses adapted instructions throughout interview
5. Time-based termination still works (from previous implementation)

### Instruction Modification:
- Uses regex to replace hardcoded time values
- Calculates proportional timings
- Adds duration-specific guidance sections
- Updates question count estimates
- Maintains all core rules and question bank

## Testing

To test different durations:
1. Create slots with different durations (5, 10, 30, 45 minutes)
2. Start interview
3. Verify agent follows proportional timing
4. Check that question count matches guidance
5. Confirm interview ends at correct time

## Notes

- Agent never mentions time pressure to candidate
- All adaptations are internal (LLM uses them for decision-making)
- Question bank (149 questions) remains available for all durations
- Agent still follows natural conversation flow
- Duration adaptation works with both dynamic and static prompts
