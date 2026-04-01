import pytest
import asyncio
from unittest.mock import patch, MagicMock
from io import StringIO
from scripts.dev_utils.check_user_role import check_user_full_details

@pytest.mark.asyncio
async def test_check_user_full_details_not_found():
    with patch('scripts.dev_utils.check_user_role.supabase') as mock_supabase:
        mock_response = MagicMock()
        mock_response.data = []
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            await check_user_full_details("test@example.com")
            output = fake_out.getvalue()
            assert "No users found with this email." in output

@pytest.mark.asyncio
async def test_check_user_full_details_success():
    with patch('scripts.dev_utils.check_user_role.supabase') as mock_supabase:
        # Mock users table
        mock_user_res = MagicMock()
        mock_user_res.data = [{"id": "u123", "role": "student", "email": "test@example.com"}]
        
        # Mock application_forms table
        mock_form_res = MagicMock()
        mock_form_res.data = [{"id": "f456", "status": "approved"}]
        
        # Mock interview_bookings table
        mock_booking_res = MagicMock()
        mock_booking_res.data = [{"token": "t789"}]
        
        # Mock evaluations table
        mock_eval_res = MagicMock()
        mock_eval_res.data = [{"id": "e012", "overall_score": 8.5}]
        
        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.side_effect = [
            mock_user_res,
            mock_form_res,
            mock_booking_res
        ]
        
        # Special case for evaluations using 'in_'
        mock_supabase.table.return_value.select.return_value.in_.return_value.execute.return_value = mock_eval_res
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            await check_user_full_details("test@example.com")
            output = fake_out.getvalue()
            
            assert "User ID: u123, Role: student" in output
            assert "Application Form found: ID=f456, Status=approved" in output
            assert "Tokens found: 1" in output
            assert "Evaluations found: 1" in output
            assert "Eval ID: e012, Score: 8.5" in output

@pytest.mark.asyncio
async def test_check_user_full_details_error():
    with patch('scripts.dev_utils.check_user_role.supabase') as mock_supabase:
        mock_supabase.table.side_effect = Exception("Supabase Error")
        
        with patch('sys.stdout', new=StringIO()) as fake_out:
            await check_user_full_details("test@example.com")
            output = fake_out.getvalue()
            assert "Error: Supabase Error" in output
