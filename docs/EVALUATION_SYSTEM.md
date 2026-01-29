# Interview Evaluation System

## Overview

Complete evaluation system for storing and displaying interview transcripts, metrics, and performance evaluations.

## Database Schema

### Tables Created

1. **interview_transcripts** - Stores complete conversation history
   - `booking_token` - Links to interview booking
   - `room_name` - LiveKit room identifier
   - `message_role` - 'user', 'assistant', or 'system'
   - `message_content` - Full message text
   - `message_index` - Order in conversation
   - `timestamp` - When message was sent

2. **interview_evaluations** - Overall evaluation metrics
   - `booking_token` - Links to interview booking
   - `duration_minutes` - Interview duration
   - `total_questions` - Questions asked
   - `rounds_completed` - Number of rounds completed
   - `overall_score` - Score out of 10
   - `rounds_data` - JSONB array of round summaries
   - `strengths` - JSONB array of strengths
   - `areas_for_improvement` - JSONB array of improvement areas

3. **interview_round_evaluations** - Detailed round breakdown
   - `evaluation_id` - Links to main evaluation
   - `round_number` - 1-5
   - `round_name` - Name of round
   - `questions_asked` - Count
   - `average_rating` - Average score for round
   - `time_spent_minutes` - Actual time
   - `time_target_minutes` - Target time
   - `topics_covered` - JSONB array
   - `performance_summary` - Text summary

## Migration

Run the migration SQL file in Supabase:

```bash
# File: docs/migration_create_evaluation_tables.sql
```

## Backend Services

### 1. TranscriptStorageService
- **Location**: `app/services/transcript_storage_service.py`
- **Purpose**: Saves interview transcripts to database
- **Methods**:
  - `save_transcript_message()` - Save single message
  - `save_transcript_batch()` - Save multiple messages
  - `get_transcript()` - Retrieve full transcript

### 2. EvaluationService
- **Location**: `app/services/evaluation_service.py`
- **Purpose**: Calculate and store evaluation metrics
- **Methods**:
  - `create_evaluation()` - Create/update evaluation
  - `save_round_evaluation()` - Save round details
  - `get_evaluation()` - Retrieve evaluation
  - `calculate_evaluation_from_transcript()` - Auto-calculate from transcript

### 3. TranscriptStorageWrapper
- **Location**: `worker/services/transcript_storage_wrapper.py`
- **Purpose**: Wraps transcript forwarding to also save to database
- **Features**:
  - Shared message index counter per booking
  - Automatic token extraction from room name
  - Coordinates with frontend transcript forwarding

## API Endpoints

### GET `/api/evaluation/{token}`
Returns comprehensive evaluation data:

```json
{
  "booking": { ... },
  "candidate": { ... },
  "interview_metrics": {
    "duration_minutes": 35,
    "rounds_completed": 5,
    "total_questions": 28
  },
  "rounds": [ ... ],
  "overall_score": 7.2,
  "strengths": [ ... ],
  "areas_for_improvement": [ ... ],
  "transcript": [ ... ]
}
```

## Frontend

### Evaluation Page
- **Route**: `/evaluation/:token`
- **Location**: `src/pages/InterviewEvaluationPage.tsx`
- **Features**:
  - Interview overview
  - Overall performance score
  - Round-by-round breakdown
  - Full transcript view
  - Application context
  - Strengths & areas for improvement

### Access Points
- **Students**: "My Interviews" → Completed → "View Evaluation"
- **Admins**: "Candidates List" → "Evaluation" link

## Agent Integration

### Automatic Transcript Saving
- Agent messages: Saved via `TranscriptStorageWrapper` in LLM chat wrapper
- User messages: Saved via `user_input_transcribed` event handler
- Both use shared message index for proper ordering

### Evaluation Creation
- Automatically created at end of interview
- Calculates metrics from transcript
- Stores round-by-round data if available

## Setup Instructions

1. **Run Database Migration**:
   ```sql
   -- Run docs/migration_create_evaluation_tables.sql in Supabase
   ```

2. **Restart Backend Server**:
   ```bash
   cd Livekit-Backend-agent-backend
   source venv/bin/activate
   python backend_server.py
   ```

3. **Restart Worker**:
   ```bash
   cd worker
   source ../venv/bin/activate
   python agent.py dev
   ```

4. **Frontend** (already updated):
   - Evaluation page is ready
   - API integration complete

## Future Enhancements

1. **AI-Powered Analysis**:
   - Use LLM to generate strengths/improvements from transcript
   - Analyze response quality and depth
   - Generate personalized feedback

2. **Advanced Metrics**:
   - Response time analysis
   - Confidence scoring
   - Topic coverage analysis
   - Communication quality metrics

3. **Real-time Updates**:
   - Live evaluation updates during interview
   - Progress tracking
   - Round completion indicators

4. **Export Features**:
   - PDF evaluation reports
   - CSV export for bulk analysis
   - Email evaluation summaries

## Notes

- Transcripts are saved in real-time during the interview
- Evaluation is created automatically when interview ends
- Message indexing ensures proper conversation order
- All data is linked via `booking_token` for easy retrieval
