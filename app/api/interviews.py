from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.interviews import (
    EvaluationResponse,
    RoundEvaluationResponse,
    ConnectionDetailsRequest,
    ConnectionDetailsResponse,
)
from app.services.container import (
    booking_service,
    evaluation_service,
    transcript_storage_service,
    slot_service,
)
from app.utils.logger import get_logger
from app.config import get_config
from app.utils.auth_dependencies import get_current_student, get_optional_student
from app.utils.datetime_utils import get_now_ist, parse_datetime_safe
from livekit import api as livekit_api
import json
import random

logger = get_logger(__name__)
config = get_config()

# Interview evaluation and LiveKit connection endpoints
router = APIRouter(tags=["Interviews"])


@router.get("/evaluation/{token}", response_model=EvaluationResponse)
async def get_evaluation(token: str):
    """
    Get comprehensive evaluation data for an interview.

    Returns:
        Complete evaluation including transcript, metrics, rounds, and scores
    """
    try:
        # Get booking
        booking = booking_service.get_booking(token)
        if not booking:
            logger.warning(f"[API] Get evaluation failed: Interview {token} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Interview not found"
            )

        # Get transcript
        transcript = transcript_storage_service.get_transcript(token)

        # Get evaluation (may be preliminary with no score yet)
        evaluation = evaluation_service.get_evaluation(token)

        # If evaluation is missing OR still in preliminary "analysis in progress" state,
        # recalculate a full evaluation from the transcript.
        if transcript and (not evaluation or evaluation.get("overall_score") is None):
            logger.info(f"[API] Evaluation missing or incomplete for {token}, recalculating from transcript...")
            evaluation_id = evaluation_service.calculate_evaluation_from_transcript(
                booking_token=token,
                room_name=booking.get('room_name') or f"room_{token}",
                transcript=transcript,
            )
            if evaluation_id:
                evaluation = evaluation_service.get_evaluation(token)

        # Format response
        candidate_data = {
            "name": booking.get("name", ""),
            "email": booking.get("email", ""),
            "application_form": {
                "text": booking.get("application_text"),
                "url": booking.get("application_url"),
            } if booking.get("application_text") else None,
        }

        # Build interview metrics
        interview_metrics = None
        if evaluation:
            interview_metrics = {
                "duration_minutes": evaluation.get("duration_minutes"),
                "rounds_completed": evaluation.get("rounds_completed", 0),
                "total_questions": evaluation.get("total_questions", 0),
                "average_response_time": None,  # Can be calculated from transcript timestamps
            }

        # Format rounds
        rounds: List[RoundEvaluationResponse] = []
        if evaluation and evaluation.get("rounds"):
            for round_data in evaluation["rounds"]:
                rounds.append(RoundEvaluationResponse(
                    round_number=round_data.get("round_number", 0),
                    round_name=round_data.get("round_name", ""),
                    questions_asked=round_data.get("questions_asked", 0),
                    average_rating=round_data.get("average_rating"),
                    time_spent_minutes=round_data.get("time_spent_minutes"),
                    time_target_minutes=round_data.get("time_target_minutes"),
                    topics_covered=round_data.get("topics_covered", []),
                    performance_summary=round_data.get("performance_summary"),
                    response_ratings=round_data.get("response_ratings", []),
                ))

        return EvaluationResponse(
            booking=booking,
            candidate=candidate_data,
            interview_metrics=interview_metrics,
            rounds=rounds,
            overall_score=evaluation.get("overall_score") if evaluation else None,
            strengths=evaluation.get("strengths", []) if evaluation else [],
            areas_for_improvement=evaluation.get("areas_for_improvement", []) if evaluation else [],
            transcript=transcript,
            communication_quality=evaluation.get("communication_quality") if evaluation else None,
            technical_knowledge=evaluation.get("technical_knowledge") if evaluation else None,
            problem_solving=evaluation.get("problem_solving") if evaluation else None,
            overall_feedback=evaluation.get("overall_feedback") if evaluation else None,
            token_usage=evaluation.get("token_usage") if evaluation else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch evaluation: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg
        )


@router.post("/connection-details", response_model=ConnectionDetailsResponse)
async def connection_details(
    request: ConnectionDetailsRequest,
    current_student: Optional[dict] = Depends(get_optional_student)
):
    """
    Generate LiveKit connection details for interview.

    Creates a participant token and room configuration with agent.

    If a token is provided, requires student authentication and verifies ownership.
    """
    try:
        # Validate LiveKit config
        if not config.livekit.url:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LIVEKIT_URL is not configured"
            )
        if not config.livekit.api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LIVEKIT_API_KEY is not configured"
            )
        if not config.livekit.api_secret:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="LIVEKIT_API_SECRET is not configured"
            )

        # Extract agent name from request
        logger.debug(f"[API] 📥 Received connection-details request:")
        logger.debug(f"[API]   room_config: {request.room_config}")
        logger.debug(f"[API]   token: {request.token if request.token else 'None'}")
        logger.info(f"[API] 📥 Received connection-details request:")
        logger.info(f"   room_config: {request.room_config}")
        logger.info(f"   token: {request.token if request.token else 'None'}")

        agent_name = None
        if request.room_config and isinstance(request.room_config, dict):
            agents = request.room_config.get("agents", [])
            logger.info(f"   Found agents array: {agents}")
            if agents and len(agents) > 0:
                first_agent_dict = agents[0]
                logger.debug(f"[API] 🔍 First agent dict from request: {first_agent_dict}")
                logger.debug(f"[API]   Keys in agent dict: {list(first_agent_dict.keys())}")
                logger.info(f"[API] 🔍 First agent dict from request: {first_agent_dict}")
                logger.info(f"[API]   Keys in agent dict: {list(first_agent_dict.keys())}")

                # Try both snake_case and camelCase
                agent_name = first_agent_dict.get("agent_name") or first_agent_dict.get("agentName")
                if not agent_name:
                    logger.debug(f"[API]   ⚠️  Neither 'agent_name' nor 'agentName' found in dict!")
                    logger.debug(f"[API]   Available keys: {list(first_agent_dict.keys())}")
                    logger.warning(f"[API]   ⚠️  Neither 'agent_name' nor 'agentName' found in dict!")
                else:
                    logger.debug(f"[API]   ✅ Extracted agent_name: '{agent_name}'")
                    logger.info(f"[API]   ✅ Extracted agent_name: '{agent_name}'")

        # Use default agent name from config if not provided
        if not agent_name:
            agent_name = config.livekit.agent_name
            logger.info(f"   Using default agent_name from config: '{agent_name}'")
        else:
            logger.info(f"   ✅ Using agent_name: '{agent_name}'")

        # If token is provided, fetch booking to get application text and validate time window
        application_text = None
        if request.token:
            # Optional: Require student login to open interview link (configurable)
            if config.REQUIRE_LOGIN_FOR_INTERVIEW:
                if not current_student:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Authentication required to access interview. Please log in as a student."
                    )
            else:
                logger.info("[API] Interview link open to anyone (REQUIRE_LOGIN_FOR_INTERVIEW=false)")

            try:
                booking = booking_service.get_booking(request.token)
                if not booking:
                    logger.warning(f"[API] Connection details failed: Interview {request.token} not found")
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Interview not found"
                    )

                # Optional: Verify that the booking belongs to the logged-in student (only when login required)
                if config.REQUIRE_LOGIN_FOR_INTERVIEW and current_student:
                    booking_user_id = booking.get('user_id')
                    if booking_user_id:
                        # Verify that the booking belongs to the logged-in student
                        auth_user_id = current_student.get('id')
                        if booking_user_id != auth_user_id:
                            raise HTTPException(
                                status_code=status.HTTP_403_FORBIDDEN,
                                detail="You do not have permission to access this interview"
                            )

                        logger.info(f"[API] ✅ Verified interview ownership: booking.user_id={booking_user_id}, student.user_id={auth_user_id}")
                    else:
                        # If booking has no user_id, allow access (for backward compatibility with old bookings)
                        logger.warning(f"[API] ⚠️  Booking {request.token} has no user_id - allowing access for backward compatibility")

                # Validate interview time window (can only join during the scheduled interview time)
                if booking.get("scheduled_at"):
                    scheduled_at_str = booking["scheduled_at"]
                    # Parse scheduled_at - handle UTC or IST format properly
                    try:
                        scheduled_at = parse_datetime_safe(scheduled_at_str)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"[API] Failed to parse scheduled_at: {e}, using fallback")
                        # Fallback: try parsing without timezone
                        naive_dt = datetime.fromisoformat(scheduled_at_str.replace('Z', '').replace('+00:00', ''))
                        scheduled_at = naive_dt.replace(tzinfo=config.IST)  # type: ignore

                    now = get_now_ist()

                    # Get interview duration from slot if available, otherwise default to 30 minutes
                    duration_minutes = 30  # Default duration
                    slot_id = booking.get("slot_id")
                    if slot_id:
                        try:
                            slot = slot_service.get_slot(slot_id)
                            logger.info(f"[API] Slot retrieved for connection-details: slot_id={slot_id}, duration_minutes={slot.get('duration_minutes') if slot else 'N/A'}, slot_keys={list(slot.keys()) if slot else 'N/A'}")
                            if slot and slot.get("duration_minutes"):
                                duration_minutes = slot["duration_minutes"]
                                logger.info(f"[API] Using duration_minutes from slot: {duration_minutes} minutes")
                            elif slot:
                                # Calculate duration from slot start and end times if available
                                slot_datetime_str = slot.get("slot_datetime")
                                if slot_datetime_str:
                                    try:
                                        slot_start = parse_datetime_safe(slot_datetime_str)

                                        # Get end time from slot or calculate
                                        slot_end_str = slot.get("end_time")
                                        if slot_end_str:
                                            slot_end = parse_datetime_safe(slot_end_str)
                                            duration_minutes = int((slot_end - slot_start).total_seconds() / 60)
                                            logger.info(f"[API] Calculated duration_minutes from slot times: {duration_minutes} minutes")
                                    except (ValueError, TypeError) as e:
                                        logger.warning(f"[API] Failed to parse slot times: {e}")
                                        pass
                            else:
                                logger.warning(f"[API] Slot not found for slot_id: {slot_id}")
                        except Exception as e:
                            logger.warning(f"[API] Failed to get slot duration: {e}")
                    else:
                        logger.warning(f"[API] No slot_id in booking, using default duration: 30 minutes")

                    interview_end_time = scheduled_at + timedelta(minutes=duration_minutes)

                    # Check if current time is before scheduled time (with 15-minute grace period for early joining)
                    grace_period = timedelta(minutes=15)
                    if now < (scheduled_at - grace_period):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Interview has not started yet. You can join up to 15 minutes early. Scheduled time: {scheduled_at.strftime('%Y-%m-%d %H:%M:%S IST')}"
                        )

                    # Check if current time is after interview end time
                    if now > interview_end_time:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"Interview window has expired. The interview was scheduled from {scheduled_at.strftime('%Y-%m-%d %H:%M:%S IST')} to {interview_end_time.strftime('%Y-%m-%d %H:%M:%S IST')}."
                        )

                    logger.info(f"[API] Interview time window validated: scheduled_at={scheduled_at}, end_time={interview_end_time}, now={now}, duration={duration_minutes} minutes")

                if booking.get("application_text"):
                    application_text = booking["application_text"]
                    logger.info(f"[API] Found application text for token {request.token} ({len(application_text)} chars)")
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"[API] Failed to fetch booking for application: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to validate interview: {str(e)}"
                )

        # [MODIFIED] Generate deterministic room details
        # Random identities cause the backend to treat re-connections as new participants,
        # potentially triggering duplicate agents if not handled carefully.
        booking_token = getattr(request, "token", None) or ""
        
        # Use a deterministic identity for the user centered around the booking token
        if booking_token:
            participant_identity = f"user_{booking_token}"
            room_name = f"interview_{booking_token}"
        else:
            # Fallback for sandbox/agent-only rooms
            participant_identity = f"voice_assistant_user_{random.randint(1, 99999)}"
            room_name = f"voice_assistant_room_{random.randint(1, 99999)}"
        
        participant_name = "Candidate"

        # Create room metadata (application_text + booking_token for worker transcript storage)
        room_metadata_dict: Dict[str, Any] = {}
        if application_text:
            room_metadata_dict["application_text"] = application_text
        if booking_token:
            room_metadata_dict["booking_token"] = booking_token
            room_metadata_dict["token"] = booking_token

        # Metadata dictionary for room (application_text + booking_token)

        room_metadata = json.dumps(room_metadata_dict) if room_metadata_dict else None

        # [OK] Prepare LiveKitAPI to explicitly create/update the room
        try:
            # Convert wss:// to https:// for the API client
            api_url = config.livekit.url.replace("wss://", "https://").replace("ws://", "http://")
            
            # Use LiveKitAPI (1.1.0 way)
            async with livekit_api.LiveKitAPI(
                api_url,
                config.livekit.api_key,
                config.livekit.api_secret
            ) as lkapi:
                # Explicitly create room (or update metadata) to trigger job dispatch
                await lkapi.room.create_room(
                    livekit_api.CreateRoomRequest(
                        name=room_name,
                        metadata=room_metadata or ""
                    )
                )

                # [OK] Explicitly create agent dispatch to trigger job request ONLY if an agent isn't already there
                try:
                    # Check for existing agent participant to ensure idempotency
                    participants_resp = await lkapi.room.list_participants(
                        livekit_api.ListParticipantsRequest(room=room_name)
                    )
                    agent_exists = any(
                        p.identity.startswith("agent-") 
                        for p in participants_resp.participants
                    )
                    
                    if agent_exists:
                        logger.info(f"[API] 🤖 Agent already present in room '{room_name}'. Skipping duplicate dispatch.")
                    else:
                        await lkapi.agent_dispatch.create_dispatch(
                            livekit_api.CreateAgentDispatchRequest(
                                agent_name=agent_name,
                                room=room_name,
                                metadata=room_metadata or ""
                            )
                        )
                        logger.info(f"[API] 🚀 Agent dispatch created for room '{room_name}' with agent '{agent_name}'")
                except Exception as dispatch_e:
                    logger.warning(f"[API] ⚠️ Failed to check participants or create explicit agent dispatch: {dispatch_e}")

            logger.info(f"[API] 🏠 Room '{room_name}' prepared with metadata and dispatch requested")
        except Exception as e:
            logger.warning(f"[API] ⚠️ Failed to explicitly create/update room metadata: {e}")
            logger.info("   (Token-level metadata will still be sent as fallback)")

        # Create LiveKit AccessToken
        token = (
            livekit_api.AccessToken(config.livekit.api_key, config.livekit.api_secret)
            .with_identity(participant_identity)
            .with_name(participant_name)
            .with_metadata(room_metadata or "")
            .with_grants(
                livekit_api.VideoGrants(
                    room_join=True,
                    room=room_name,
                )
            )
        )

        jwt_token = token.to_jwt()

        logger.info(f"[API] ✅ Generated connection details for room: {room_name}")

        return ConnectionDetailsResponse(
            serverUrl=config.livekit.url,
            participantToken=jwt_token,
            roomName=room_name,
            participantName=participant_name,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[API] Error generating connection details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate connection details: {str(e)}"
        )


@router.get("/api/student/analytics")
async def get_student_analytics(current_student: dict = Depends(get_current_student)):
    """
    Get analytics and progress for the current logged-in student.
    """
    try:
        user_id = current_student.get("id") or current_student.get("user_id")
        email = current_student.get("email")

        # 1. Get all bookings for this student
        # Try by user_id first (preferred for enrolled users)
        bookings: List[Dict[str, Any]] = []
        if user_id:
            bookings = booking_service.get_bookings_by_user_id(user_id)

        # If no bookings found by user_id, try by email (fallback for older bookings or pre-enrollment)
        if not bookings and email:
            bookings = booking_service.get_bookings_by_email(email)

        booking_tokens = [b["token"] for b in bookings if b.get("token")]

        # 2. Calculate analytics using the service
        analytics = evaluation_service.get_student_analytics(booking_tokens)

        return analytics

    except Exception as e:
        logger.error(f"[API] Error fetching student analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch analytics: {str(e)}"
        )


