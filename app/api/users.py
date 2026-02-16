from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, status

from app.schemas.users import (
    EnrollUserRequest,
    UpdateUserRequest,
    UserResponse,
    UserDetailResponse,
    BulkEnrollResponse,
    ScheduleInterviewForUserRequest,
    BulkScheduleInterviewResponse,
    InterviewSummary,
)
from app.services.container import (
    booking_service,
    evaluation_service,
    user_service,
    auth_service,
    slot_service,
    assignment_service,
    email_service,
)
from app.utils.logger import get_logger
from app.utils.auth_dependencies import get_current_admin
from app.db.supabase import get_supabase
from app.utils.datetime_utils import get_now_ist, IST, to_ist

logger = get_logger(__name__)
import pandas as pd
from io import BytesIO
import asyncio

# Admin-facing enrolled user management endpoints
router = APIRouter(tags=["Users"])


@router.post("/", response_model=UserResponse)
async def enroll_user(
    request: EnrollUserRequest,
    background_tasks: BackgroundTasks,
    current_admin: dict = Depends(get_current_admin)
):
    """
    Enroll a new user (without scheduling interview).
    Creates student account with temporary password and sends email.
    """
    try:
        logger.info(f"[API] Enrolling user: {request.email}")

        # Generate temporary password
        temporary_password = auth_service.generate_temporary_password()

        # Create student account with temporary password
        try:
            student = auth_service.register_student(
                email=request.email,
                password=temporary_password,
                name=request.name,
                phone=request.phone,
                must_change_password=True,
            )
        except Exception as e:
            error_msg = str(e)
            if "already registered" in error_msg.lower() or "unique constraint" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"User with email {request.email} already exists",
                )
            raise

        # Validate or Auto-assign slots
        target_slot_ids = request.slot_ids
        if not target_slot_ids:
            try:
                now = get_now_ist()
                two_days_from_now = now + timedelta(days=2)
                all_slots = slot_service.get_all_slots(status="active", include_past=False)

                target_slot_ids = []
                for slot in all_slots:
                    try:
                        slot_dt_str = slot["slot_datetime"]
                        if slot_dt_str.endswith("Z") or "+" in slot_dt_str:
                            slot_dt = to_ist(datetime.fromisoformat(slot_dt_str.replace("Z", "+00:00")))
                        else:
                            slot_dt = datetime.fromisoformat(slot_dt_str).replace(tzinfo=IST)

                        if (
                            slot_dt >= now
                            and slot_dt <= two_days_from_now
                            and slot.get("current_bookings", 0) < slot.get("max_capacity", 1)
                        ):
                            target_slot_ids.append(slot["id"])
                    except Exception:
                        continue
                logger.info(f"[API] Auto-assigned {len(target_slot_ids)} slots to user {request.email}")
            except Exception as e:
                logger.error(f"[API] Failed to auto-assign slots: {str(e)}")
        
        if not target_slot_ids:
                logger.warning(f"[API] Enrollment failed: No available slots for auto-assignment for {request.email}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="No available slots found for auto-assignment. Please provide slot_ids manually.",
                )
        elif request.slot_ids: # Only enforce the 10-slot rule if they provided them manually
            if len(target_slot_ids) < 10:
                logger.warning(f"[API] Enrollment failed: User {request.email} provided only {len(target_slot_ids)} slots, minimum 10 required.")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="At least 10 slots must be assigned to the user",
                )

            two_days_from_now = get_now_ist() + timedelta(days=2)
            for slot_id in target_slot_ids:
                slot = slot_service.get_slot(slot_id)
                if not slot:
                    logger.warning(f"[API] Enrollment failed: Slot {slot_id} not found")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Slot {slot_id} not found",
                    )
                if slot["status"] != "active":
                    logger.warning(f"[API] Enrollment failed: Slot {slot_id} is not active ({slot['status']})")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Slot {slot_id} is not active",
                    )
                try:
                    slot_datetime_str = slot["slot_datetime"]
                    if slot_datetime_str.endswith("Z") or "+" in slot_datetime_str:
                        slot_datetime = to_ist(datetime.fromisoformat(slot_datetime_str.replace("Z", "+00:00")))
                    else:
                        slot_datetime = datetime.fromisoformat(slot_datetime_str).replace(tzinfo=IST)

                    if slot_datetime > two_days_from_now:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=f"All slots must be within the next 2 days. Slot {slot_id} is beyond that.",
                        )
                except (ValueError, KeyError, TypeError):
                    pass

        # Create enrolled_users record
        user = user_service.create_user(
            name=request.name,
            email=request.email,
            phone=request.phone,
            notes=request.notes,
        )

        # Assign slots to user
        if target_slot_ids:
            try:
                assignment_service.assign_slots_to_user(user["id"], target_slot_ids)
                logger.info(f"[API] ✅ Assigned {len(target_slot_ids)} slots to user {user['id']}")
            except Exception as e:
                logger.warning(f"[API] ⚠️ Failed to assign slots: {str(e)}")

        # Send enrollment email in background
        logger.info(f"[API] 📧 Preparing to send enrollment email to {request.email}")

        async def send_enrollment_email_bg():
            try:
                success, error = await email_service.send_enrollment_email(
                    to_email=request.email,
                    name=request.name,
                    email=request.email,
                    temporary_password=temporary_password,
                )
                if success:
                    logger.info(f"[API] ✅ Enrollment email sent successfully to {request.email}")
                else:
                    logger.error(f"[API] ❌ Enrollment email failed to send to {request.email}: {error}")
            except Exception as e:
                logger.error(f"[API] ❌ Exception while sending enrollment email to {request.email}: {str(e)}")

        asyncio.create_task(send_enrollment_email_bg())

        return UserResponse(**user)

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to enroll user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.post("/bulk-enroll", response_model=BulkEnrollResponse)
async def bulk_enroll_users(
    file: UploadFile = File(...),
    current_admin: dict = Depends(get_current_admin),
):
    """
    Bulk enroll users from Excel file.
    """
    try:
        logger.info(f"[API] Bulk enrolling users from file: {file.filename}")

        try:
            contents = await file.read()
            df = pd.read_excel(BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read Excel file: {str(e)}",
            )

        required_columns = ["name", "email"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Missing required columns: {', '.join(missing_columns)}. "
                    f"Expected columns: {', '.join(required_columns)} (phone and notes are optional)"
                ),
            )

        total = len(df)
        successful = 0
        failed = 0
        errors: List[str] = []

        now_dt = get_now_ist()
        two_days_from_now = now_dt + timedelta(days=2)
        all_slots = slot_service.get_all_slots(status="active", include_past=False)
        auto_assign_slot_ids: List[str] = []
        for slot in all_slots:
            try:
                slot_dt_str = slot["slot_datetime"]
                if slot_dt_str.endswith("Z") or "+" in slot_dt_str:
                    slot_dt = to_ist(datetime.fromisoformat(slot_dt_str.replace("Z", "+00:00")))
                else:
                    slot_dt = datetime.fromisoformat(slot_dt_str).replace(tzinfo=IST)

                if (
                    slot_dt >= now_dt
                    and slot_dt <= two_days_from_now
                    and slot.get("current_bookings", 0) < slot.get("max_capacity", 1)
                ):
                    auto_assign_slot_ids.append(slot["id"])
            except Exception:
                continue

        logger.info(f"[API] Bulk enrollment will auto-assign {len(auto_assign_slot_ids)} slots to each user")

        for idx, row in df.iterrows():
            try:
                name = str(row["name"]).strip()
                email = str(row["email"]).strip()
                phone = str(row.get("phone", "")).strip() if pd.notna(row.get("phone")) else None
                notes = str(row.get("notes", "")).strip() if pd.notna(row.get("notes")) else None

                if not name or not email:
                    raise ValueError("name and email are required and cannot be empty")

                temporary_password = auth_service.generate_temporary_password()

                try:
                    student = auth_service.register_student(
                        email=email,
                        password=temporary_password,
                        name=name,
                        phone=phone,
                        must_change_password=True,
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "already registered" in error_msg.lower() or "unique constraint" in error_msg.lower():
                        raise ValueError(f"User with email {email} already exists")
                    raise ValueError(f"Failed to create student account: {str(e)}")

                try:
                    user = user_service.create_user(
                        name=name,
                        email=email,
                        phone=phone,
                        notes=notes,
                    )
                except Exception as e:
                    error_msg = str(e)
                    if "unique constraint" in error_msg.lower() or "already exists" in error_msg.lower():
                        raise ValueError(f"Enrolled user with email {email} already exists")
                    raise ValueError(f"Failed to create enrolled user: {str(e)}")

                if auto_assign_slot_ids:
                    try:
                        assignment_service.assign_slots_to_user(user["id"], auto_assign_slot_ids)
                        logger.info(f"[API] ✅ Auto-assigned {len(auto_assign_slot_ids)} slots to user {user['id']}")
                    except Exception as e:
                        logger.warning(f"[API] ⚠️ Failed to auto-assign slots for {email}: {str(e)}")

                async def send_enrollment_email_bg(email_addr: str, name_val: str, temp_pass: str):
                    try:
                        await email_service.send_enrollment_email(
                            to_email=email_addr,
                            name=name_val,
                            email=email_addr,
                            temporary_password=temp_pass,
                        )
                        logger.info(f"[API] ✅ Bulk enrollment email sent to {email_addr}")
                    except Exception as e:
                        logger.warning(f"[API] ⚠️ Bulk enrollment email failed for {email_addr}: {str(e)}")

                asyncio.create_task(send_enrollment_email_bg(email, name, temporary_password))

                successful += 1
                logger.info(f"[API] ✅ Enrolled user {idx + 1}/{total}: {email}")

            except Exception as e:
                failed += 1
                error_msg = f"Row {idx + 2}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[API] {error_msg}")

        await asyncio.sleep(0.1)

        logger.info(f"[API] Bulk enrollment complete: {successful}/{total} successful")

        return BulkEnrollResponse(
            success=True,
            total=total,
            successful=successful,
            failed=failed,
            errors=errors if errors else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to bulk enroll users: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.get("/", response_model=List[UserResponse])
async def get_all_users(
    current_admin: dict = Depends(get_current_admin),
    limit: Optional[int] = None,
    skip: Optional[int] = None,
):
    """
    Get all enrolled users with optional pagination.
    """
    try:
        users = user_service.get_all_users(limit=limit, skip=skip)
        return [UserResponse(**user) for user in users]
    except Exception as e:
        error_msg = f"Failed to fetch users: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.get("/{user_id}", response_model=UserDetailResponse)
async def get_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """
    Get an enrolled user by ID with full interview history.
    Accessible to both admins and managers.
    """
    try:
        user = user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )

        bookings = booking_service.get_user_bookings(user_id)
        if not bookings:
            user_email = (user.get("email") or "").strip()
            if user_email:
                bookings = booking_service.get_bookings_by_email(user_email)
        else:
            user_email = (user.get("email") or "").strip()
            if user_email:
                email_bookings = booking_service.get_bookings_by_email(user_email)
                seen_tokens = {b.get("token") for b in bookings if b.get("token")}
                for b in email_bookings:
                    t = b.get("token")
                    if t and t not in seen_tokens:
                        bookings.append(b)
                        seen_tokens.add(t)

        booking_tokens = [b["token"] for b in bookings]
        evaluations = evaluation_service.get_evaluations_for_bookings(booking_tokens)
        eval_map = {e["booking_token"]: e for e in evaluations}

        interviews: List[InterviewSummary] = []
        for booking in bookings:
            token = booking.get("token")
            evaluation = eval_map.get(token)

            summary = InterviewSummary(
                token=token,
                scheduled_at=booking.get("scheduled_at", ""),
                status=booking.get("status", "scheduled"),
                overall_score=evaluation.get("overall_score") if evaluation else None,
                overall_feedback=evaluation.get("overall_feedback") if evaluation else None,
                evaluation_url=f"/evaluation/{token}" if evaluation else None,
                interview_url=f"/interview/{token}" if booking.get("status") == "scheduled" else None,
            )
            interviews.append(summary)

        overall_analysis = None
        try:
            analytics = evaluation_service.get_student_analytics(booking_tokens)
            overall_analysis = analytics.get("overall_analysis")
            if not overall_analysis:
                scored_evals = [e for e in evaluations if e.get("overall_feedback")]
                scored_evals.sort(key=lambda x: x.get("created_at", ""))
                if scored_evals:
                    overall_analysis = scored_evals[-1].get("overall_feedback")
        except Exception as e:
            logger.warning(f"[API] Could not compute overall analysis for user {user_id}: {e}")

        user_response = UserResponse(**user)
        return UserDetailResponse(
            **user_response.dict(),
            interviews=interviews,
            overall_analysis=overall_analysis,
        )

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to fetch user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    current_admin: dict = Depends(get_current_admin),
):
    """
    Update an enrolled user.
    """
    try:
        user = user_service.update_user(
            user_id=user_id,
            name=request.name,
            email=request.email,
            phone=request.phone,
            status=request.status,
            notes=request.notes,
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        return UserResponse(**user)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to update user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.delete("/{user_id}")
async def delete_user(user_id: str, current_admin: dict = Depends(get_current_admin)):
    """
    Delete an enrolled user and all associated data.
    """
    try:
        user = user_service.get_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found",
            )
        email = user.get("email")

        bookings = booking_service.get_bookings_by_user_id(user_id)
        booking_tokens = [b.get("token") for b in bookings if b.get("token")]

        try:
            if booking_tokens:
                from app.api.main import transcript_storage_service  # type: ignore

                transcript_storage_service.delete_by_booking_tokens(booking_tokens)
        except Exception as e:
            logger.warning(f"[API] Could not delete transcripts for user {user_id}: {e}")

        try:
            if booking_tokens:
                evaluation_service.delete_evaluations_by_booking_tokens(booking_tokens)
        except Exception as e:
            logger.warning(f"[API] Could not delete evaluations for user {user_id}: {e}")

        try:
            slot_service.release_slots_for_user(user_id)
        except Exception as e:
            logger.warning(f"[API] Could not release slots for user {user_id}: {e}")

        try:
            if email:
                from app.api.main import admin_service  # type: ignore

                admin_service.delete_student_account_by_email(email)
        except Exception as e:
            logger.warning(f"[API] Could not delete student auth for user {user_id}: {e}")

        user_service.delete_user(user_id)

        return {"success": True, "message": "User and associated data deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to delete user: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


@router.post("/remove-student-auth")
async def remove_student_auth_by_email(
    request: "UserResponse",  # just need email field; reuse existing model
    current_admin: dict = Depends(get_current_admin),
):
    """
    Remove student auth for a given email (safety utility).
    """
    try:
        email = request.email
        if not email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required",
            )

        from app.api.main import admin_service  # type: ignore

        deleted_auth = admin_service.delete_student_account_by_email(email)

        return {
            "success": True,
            "deleted_auth": deleted_auth,
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to remove student auth: {str(e)}"
        logger.error(f"[API] {error_msg}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_msg,
        )


