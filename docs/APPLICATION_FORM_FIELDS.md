# Application Form Fields Storage

## All Fields Being Stored

### Personal Details ✅
- `full_name` - Required
- `post` - Optional
- `category` - Optional
- `date_of_birth` - Optional (converted to DATE format)
- `gender` - Optional
- `marital_status` - Optional
- `aadhaar_number` - Optional
- `pan_number` - Optional
- `father_name` - Optional
- `mother_name` - Optional
- `spouse_name` - Optional

### Address Details ✅
- `correspondence_address1` - Optional
- `correspondence_address2` - Optional
- `correspondence_address3` - Optional
- `correspondence_state` - Optional
- `correspondence_district` - Optional
- `correspondence_pincode` - Optional
- `permanent_address1` - Optional
- `permanent_address2` - Optional
- `permanent_address3` - Optional
- `permanent_state` - Optional
- `permanent_district` - Optional ✅ **FIXED: Was missing, now included**
- `permanent_pincode` - Optional

### Contact Details ✅
- `email` - Auto-filled from authenticated student
- `mobile_number` - Auto-filled from enrolled_user.phone
- `alternative_number` - Optional (can be added to form if needed)

### Educational Qualification ✅
- `ssc_board` - Optional
- `ssc_passing_date` - Optional
- `ssc_percentage` - Optional
- `ssc_class` - Optional
- `graduation_degree` - Optional
- `graduation_college` - Optional
- `graduation_specialization` - Optional
- `graduation_passing_date` - Optional
- `graduation_percentage` - Optional
- `graduation_class` - Optional

### Other Details ✅
- `religion` - Optional
- `religious_minority` - Boolean (default: False)
- `local_language_studied` - Boolean (default: False)
- `local_language_name` - Optional
- `computer_knowledge` - Boolean (default: False)
- `computer_knowledge_details` - Optional
- `languages_known` - JSONB (stored as JSON object)

### Application Specific ✅
- `state_applying_for` - Optional
- `regional_rural_bank` - Optional
- `exam_center_preference1` - Optional
- `exam_center_preference2` - Optional
- `medium_of_paper` - Optional

### File Upload ✅
- `application_file_url` - Optional (URL to uploaded PDF)
- `application_text` - Auto-generated from form data or extracted from PDF

## Storage Method

**Fixed:** Fields are now stored **directly as database columns** (not nested in a `data` JSONB field).

Each field maps directly to a column in the `application_forms` table.

## Verification

To verify all fields are being stored, run this SQL:

```sql
-- Check a specific user's application form
SELECT 
    full_name,
    post,
    category,
    date_of_birth,
    gender,
    mobile_number,
    email,
    correspondence_state,
    permanent_district,  -- This was missing before
    ssc_board,
    graduation_degree,
    religion,
    state_applying_for,
    application_text
FROM application_forms
WHERE user_id = 'YOUR_USER_ID'
LIMIT 1;
```

## Changes Made

1. ✅ **Fixed missing `permanent_district` field** - Now included in form_data
2. ✅ **Fixed storage method** - Fields stored as columns, not nested JSON
3. ✅ **Added contact fields** - email and mobile_number auto-filled from user record
4. ✅ **Date conversion** - date_of_birth properly converted to DATE format
5. ✅ **Fixed user_id reference** - Changed from student_id to user_id (enrolled_users.id)
