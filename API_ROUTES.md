# API Route Map

## Public (No Auth)
| Method | Path | Description |
|--------|------|-------------|
| GET | / | Root application status |
| GET | /health | Health check |
| GET | /ready | Application readiness check |
| GET | /metrics | Prometheus metrics |
| POST | /api/auth/login | General Login interface (detects Student, Admin, Manager), returns JWT |
| POST | /api/auth/admin/login | Explicit Admin/Manager Login portal |
| POST | /api/auth/student/register | General Student registration |
| POST | /api/auth/request-password-reset | Request reset OTP via email |
| POST | /api/auth/reset-password | Reset password directly using 6-digit OTP |
| POST | /api/auth/change-password | Authorized password rotation logic |
| GET | /api/public/interview-config | Frontend configuration helper (public) |
| GET | /api/slots/student/available | Retrieve list of all globally available interview slots |
| GET | /api/files/{file_id} | Retrieves uploaded public asset or resume by ID |
| POST | /api/compiler/execute | Native remote code evaluation pipeline |

## Admin & Manager Routes (require admin/manager token)
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/admin/slots | Admin: Create a single interview slot |
| GET | /api/admin/slots | Admin: Retrieve filtered slots |
| GET | /api/admin/slots/{slot_id} | Admin: Fetch specific slot object |
| PUT | /api/admin/slots/{slot_id} | Admin: Reconfigure slot bounds/capacities |
| DELETE | /api/admin/slots/{slot_id} | Admin: Physically or virtually delete a slot |
| POST | /api/admin/slots/create-day | Admin: Create continuous blocks of uniform slots automatically |
| GET | /api/admin/slots/{slot_id}/check-consistency | Admin: Diagnostics script checking slot DB bounds tracking |
| GET | /api/admin/job-description | Manager: Read configured organization JD template |
| PUT | /api/admin/job-description | Manager: Update structured JD template |
| POST | /api/admin/managers | Admin: Provision an active organization manager |
| GET | /api/admin/managers | Admin: Read list of managers |
| DELETE | /api/admin/managers/{manager_id} | Admin: Disenfranchise a manager access log |
| GET | /api/admin/system-instructions | Manager: Read general LiveKit system instructions |
| PUT | /api/admin/system-instructions | Manager: Mutate LiveKit context instructions |
| POST | /api/admin/register-candidate | Manager: Upload isolated candidate identity manually |
| POST | /api/admin/bulk-register | Manager: Execute CSV formatted identity ingestion |
| GET | /api/admin/candidates | Manager: Lookup active platform applicants |
| POST | /api/admin/schedule-interview | Manager: Force interview allocation overriding logic params |
| POST | /api/admin/schedule-interview/bulk | Manager: Legacy bulk scheduling protocol mapped to active slots |
| POST | /api/admin/schedule-interview/bulk-json | Manager: Enhanced JSON payload struct mapped to multi-slot transactions |
| GET | /api/admin/gemini-usage | Manager: Billing proxy to detect token cost/consumption thresholds |

## User Management Routes
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/users/ | Internal explicit User scaffolding |
| GET | /api/users/ | Read paginated lists of application Users |
| GET | /api/users/{user_id} | Search user entity |
| PUT | /api/users/{user_id} | Manipulate user details directly from high-level |
| DELETE | /api/users/{user_id} | Physically delete user data/schema block |
| POST | /api/users/bulk-enroll | Admin: CSV automated student account activation |
| POST | /api/users/remove-student-auth | Admin: Disabling authorization blocks for bad actors |

## Student Routes (require student token)
| Method | Path | Description |
|--------|------|-------------|
| POST | /api/resume/upload-application | Student: Post structured resume attachments securely |
| GET | /api/student/application-form | Student: Get application tracking data |
| POST | /api/student/application-form/upload | Student: General form application processing upload |
| GET | /api/student/my-assignments | Student: Active assignment bounds returned against login scope |
| POST | /api/student/select-slot | Student: Actionable logic handler placing user securely onto specific Slot. Executes compensation patterns if failed. |
| GET | /api/student/my-interview | Student: Historical and active interview reservations mapped to token string |

## Bookings and Interview Logistics (Multi-Auth Access)
| Method | Path | Description |
|--------|------|-------------|
| GET | /api/bookings/booking/{token} | Unauthenticated / Multi-tier fetch specific interview metadata securely via string code mapping |
| GET | /api/interviews/session-state/{token} | Determines active state logic (Running / Passed) for continuity hooks |
| POST | /api/interviews/connection-details | Establishes LiveKit API token negotiation using session parameters |
| POST | /api/interviews/analyze-code | Interacts with deep-interview AI models for interactive compiler bounds checking |
| GET | /api/interviews/api/student/analytics | General statistical dashboard logic per individual evaluation array |
| GET | /api/interviews/evaluation/{token} | Secure evaluation report data return bound by Token string (Secured effectively) |
| GET | /api/integration/health | Health check for integration (API Key Auth) |
| POST | /api/integration/enroll-students | Bulk enroll students for a batch |
| GET | /api/integration/students | Get all enrolled students for a batch |
| POST | /api/integration/schedule-interview | Create multiple interview slots for a batch. Accepts optional `student_ids` (array) for enrollment validation. |
| GET | /api/integration/slots | List available slots for a batch |
| POST | /api/integration/book-slot | Book a slot for an enrolled student |
| POST | /api/integration/register-webhook | Register an LMS callback URL |
| GET | /api/integration/evaluation/{token} | Fetch results for an LMS-booked interview |
