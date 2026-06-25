# Email Management System - API Reference

## Base URL
```
http://localhost:8000/api/admin/mails/
```

## Authentication
All endpoints require authentication. Include in request headers:
```
Authorization: Bearer <token>
```
or use session authentication (in browser).

---

## Email Templates

### List Templates
```http
GET /api/admin/mails/templates/
```

**Query Parameters:**
- `search` (string) - Search in name, slug, description
- `template_type` (string) - Filter by type (transactional, marketing, system)
- `is_active` (boolean) - Filter active/inactive
- `language_code` (string) - Filter by language (en, es, fr, etc.)
- `template_group` (string) - Filter by group
- `page` (integer) - Page number for pagination

**Response:**
```json
{
  "count": 10,
  "next": "http://localhost:8000/api/admin/mails/templates/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "name": "Welcome Email",
      "slug": "welcome-email",
      "template_type": "transactional",
      "is_active": true,
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Create Template
```http
POST /api/admin/mails/templates/
```

**Request Body:**
```json
{
  "name": "Welcome Email",
  "slug": "welcome-email",
  "description": "Sent when user signs up",
  "subject": "Welcome to {{company_name}}!",
  "html_content": "<h1>Welcome {{user_name}}!</h1><p>Thank you for joining us.</p>",
  "text_content": "Welcome {{user_name}}! Thank you for joining us.",
  "template_type": "transactional",
  "template_group": "account",
  "language_code": "en",
  "is_active": true,
  "email_enabled": true,
  "in_app_enabled": false,
  "push_enabled": false,
  "sms_enabled": false
}
```

**Response:** 201 Created with full template object

### Get Template
```http
GET /api/admin/mails/templates/:id/
```

**Response:**
```json
{
  "id": "uuid",
  "name": "Welcome Email",
  "slug": "welcome-email",
  "description": "Sent when user signs up",
  "subject": "Welcome to {{company_name}}!",
  "html_content": "<h1>Welcome {{user_name}}!</h1>",
  "text_content": "Welcome {{user_name}}!",
  "template_type": "transactional",
  "template_group": "account",
  "language_code": "en",
  "is_active": true,
  "email_enabled": true,
  "created_by": {
    "id": 1,
    "email": "admin@example.com"
  },
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Update Template
```http
PUT /api/admin/mails/templates/:id/
```

**Request Body:** Same as Create Template

**Response:** 200 OK with updated template object

### Delete Template
```http
DELETE /api/admin/mails/templates/:id/
```

**Permissions:** Superuser only

**Response:** 204 No Content

### Clone Template
```http
POST /api/admin/mails/templates/:id/clone/
```

**Request Body:**
```json
{
  "name": "Welcome Email (Copy)"
}
```

**Response:** 201 Created with cloned template object

### Preview Template
```http
POST /api/admin/mails/templates/:id/preview/
```

**Request Body (optional):**
```json
{
  "context": {
    "user_name": "John Doe",
    "company_name": "Airtasker",
    "verification_link": "https://example.com/verify"
  }
}
```

**Response:**
```json
{
  "subject": "Welcome to Airtasker!",
  "html_content": "<h1>Welcome John Doe!</h1>",
  "text_content": "Welcome John Doe!",
  "variables_used": ["user_name", "company_name"],
  "missing_variables": []
}
```

---

## SMTP Configuration

### Get Active SMTP Config
```http
GET /api/admin/mails/smtp/
```

**Permissions:** Superuser only

**Response:**
```json
{
  "id": "uuid",
  "name": "Gmail SMTP",
  "provider": "gmail",
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "noreply@example.com",
  "password": "********",
  "use_tls": true,
  "use_ssl": false,
  "timeout": 30,
  "is_active": true,
  "test_status": "success",
  "last_tested_at": "2024-01-01T00:00:00Z"
}
```

### Update SMTP Config
```http
PUT /api/admin/mails/smtp/
```

**Permissions:** Superuser only

**Request Body:**
```json
{
  "name": "Gmail SMTP",
  "provider": "gmail",
  "host": "smtp.gmail.com",
  "port": 587,
  "username": "noreply@example.com",
  "password": "your_app_password",
  "use_tls": true,
  "use_ssl": false,
  "timeout": 30,
  "from_email": "noreply@example.com",
  "from_name": "Airtasker"
}
```

**Response:** 200 OK with updated config

### Test SMTP Connection
```http
POST /api/admin/mails/smtp/test-connection/
```

**Permissions:** Superuser only

**Response:**
```json
{
  "success": true,
  "message": "SMTP connection successful",
  "tested_at": "2024-01-01T00:00:00Z"
}
```

### Send Test Email
```http
POST /api/admin/mails/smtp/send-test/
```

**Permissions:** Superuser only

**Request Body:**
```json
{
  "test_email": "test@example.com"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Test email sent successfully",
  "recipient": "test@example.com"
}
```

---

## Notification Rules

### List All Rules (Grouped)
```http
GET /api/admin/mails/rules/
```

**Response:**
```json
{
  "account": [
    {
      "id": "uuid",
      "event_name": "user_registered",
      "event_category": "account",
      "display_name": "User Registration",
      "description": "Sent when a new user signs up",
      "email_enabled": true,
      "in_app_enabled": true,
      "push_enabled": false,
      "sms_enabled": false,
      "template": {
        "id": "uuid",
        "name": "Welcome Email"
      }
    }
  ],
  "tasks": [
    {
      "id": "uuid",
      "event_name": "task_created",
      "event_category": "tasks",
      "display_name": "Task Created",
      "description": "Sent when a new task is posted",
      "email_enabled": true,
      "in_app_enabled": true,
      "push_enabled": true,
      "sms_enabled": false
    }
  ]
}
```

### Update Rule
```http
PUT /api/admin/mails/rules/:id/
```

**Request Body:**
```json
{
  "email_enabled": true,
  "in_app_enabled": false,
  "push_enabled": true,
  "sms_enabled": false,
  "template_id": "uuid"
}
```

**Response:** 200 OK with updated rule

### Bulk Update Rules
```http
POST /api/admin/mails/rules/bulk-update/
```

**Request Body:**
```json
{
  "category": "marketing",
  "email_enabled": false,
  "push_enabled": true
}
```

**Response:**
```json
{
  "success": true,
  "updated_count": 5
}
```

---

## Email Logs

### List Logs
```http
GET /api/admin/mails/logs/
```

**Query Parameters:**
- `status` (string) - Filter by status (pending, sent, delivered, bounced, failed)
- `recipient_email` (string) - Filter by recipient
- `template_id` (uuid) - Filter by template
- `date_from` (date) - Start date (YYYY-MM-DD)
- `date_to` (date) - End date (YYYY-MM-DD)
- `search` (string) - Search in subject or recipient
- `page` (integer) - Page number

**Response:**
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/admin/mails/logs/?page=2",
  "previous": null,
  "results": [
    {
      "id": "uuid",
      "recipient_email": "user@example.com",
      "subject": "Welcome to Airtasker",
      "status": "delivered",
      "template_used": {
        "id": "uuid",
        "name": "Welcome Email"
      },
      "sent_at": "2024-01-01T00:00:00Z",
      "delivered_at": "2024-01-01T00:01:00Z",
      "opened_at": "2024-01-01T00:05:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ]
}
```

### Get Log Detail
```http
GET /api/admin/mails/logs/:id/
```

**Response:**
```json
{
  "id": "uuid",
  "recipient_email": "user@example.com",
  "recipient_user": {
    "id": 1,
    "email": "user@example.com",
    "first_name": "John"
  },
  "subject": "Welcome to Airtasker",
  "html_content": "<h1>Welcome John!</h1>",
  "text_content": "Welcome John!",
  "status": "delivered",
  "template_used": {
    "id": "uuid",
    "name": "Welcome Email",
    "slug": "welcome-email"
  },
  "smtp_config_used": {
    "id": "uuid",
    "name": "Gmail SMTP"
  },
  "sent_at": "2024-01-01T00:00:00Z",
  "delivered_at": "2024-01-01T00:01:00Z",
  "opened_at": "2024-01-01T00:05:00Z",
  "clicked_at": null,
  "bounced_at": null,
  "failed_at": null,
  "error_message": null,
  "retry_count": 0,
  "external_id": "msg_123456",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:05:00Z"
}
```

---

## Email Settings

### Get Settings
```http
GET /api/admin/mails/settings/
```

**Response:**
```json
{
  "id": "uuid",
  "company_name": "Airtasker",
  "company_logo_url": "https://example.com/logo.png",
  "primary_color": "#FF5722",
  "secondary_color": "#FFC107",
  "background_color": "#F5F5F5",
  "footer_text": "© 2024 Airtasker. All rights reserved.",
  "footer_address": "123 Street, City, Country",
  "footer_phone": "+1234567890",
  "footer_email": "support@example.com",
  "social_facebook": "https://facebook.com/airtasker",
  "social_twitter": "https://twitter.com/airtasker",
  "social_linkedin": "https://linkedin.com/company/airtasker",
  "social_instagram": "https://instagram.com/airtasker",
  "email_enabled": true,
  "unsubscribe_enabled": true,
  "unsubscribe_text": "If you no longer wish to receive these emails, you can unsubscribe here.",
  "created_at": "2024-01-01T00:00:00Z",
  "updated_at": "2024-01-01T00:00:00Z"
}
```

### Update Settings
```http
PUT /api/admin/mails/settings/
```

**Request Body:** Same as Get Settings response

**Response:** 200 OK with updated settings

---

## Analytics

### Get Dashboard Stats
```http
GET /api/admin/mails/analytics/dashboard/
```

**Query Parameters:**
- `date_from` (ISO datetime) - Start of date range
- `date_to` (ISO datetime) - End of date range
- Default: Last 30 days

**Response:**
```json
{
  "summary": {
    "total_sent": 1234,
    "total_delivered": 1100,
    "total_failed": 50,
    "delivery_rate": 89.14,
    "open_rate": 45.2,
    "click_rate": 12.5,
    "bounce_rate": 2.1,
    "unsubscribe_rate": 0.8,
    "average_delivery_time": "2.5 minutes",
    "total_emails": 5000
  },
  "date_range": {
    "from": "2024-01-01T00:00:00Z",
    "to": "2024-01-31T23:59:59Z"
  }
}
```

---

## Error Responses

### 400 Bad Request
```json
{
  "error": "Invalid data provided",
  "details": {
    "field_name": ["Error message"]
  }
}
```

### 401 Unauthorized
```json
{
  "detail": "Authentication credentials were not provided."
}
```

### 403 Forbidden
```json
{
  "error": "You do not have permission to perform this action."
}
```

### 404 Not Found
```json
{
  "error": "Resource not found"
}
```

### 500 Internal Server Error
```json
{
  "error": "An internal error occurred. Please try again later."
}
```

---

## Common Headers

**Request Headers:**
```
Authorization: Bearer <token>
Content-Type: application/json
Accept: application/json
```

**Response Headers:**
```
Content-Type: application/json
X-Total-Count: 100
X-Page: 1
X-Per-Page: 20
```

---

## Rate Limiting

- Test emails: 10 per hour per user
- SMTP connection tests: 5 per 10 minutes per user
- Standard endpoints: 100 requests per minute per user

---

## Pagination

All list endpoints support pagination:

**Request:**
```
GET /api/admin/mails/templates/?page=2&page_size=20
```

**Response:**
```json
{
  "count": 100,
  "next": "http://localhost:8000/api/admin/mails/templates/?page=3",
  "previous": "http://localhost:8000/api/admin/mails/templates/?page=1",
  "results": [...]
}
```

Default page size: 20
Maximum page size: 100

---

## Testing with cURL

**Get Templates:**
```bash
curl -X GET http://localhost:8000/api/admin/mails/templates/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Create Template:**
```bash
curl -X POST http://localhost:8000/api/admin/mails/templates/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Email",
    "slug": "test-email",
    "subject": "Test",
    "html_content": "<p>Test</p>",
    "template_type": "transactional"
  }'
```

**Test SMTP:**
```bash
curl -X POST http://localhost:8000/api/admin/mails/smtp/send-test/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"test_email": "test@example.com"}'
```

---

## Notes

- All datetime fields are in ISO 8601 format with UTC timezone
- All UUID fields accept standard UUID format (with or without hyphens)
- Passwords in SMTP config are masked with `********` in responses
- Deleted templates cannot be recovered
- Email logs are read-only and cannot be modified via API
- Notification rules are pre-seeded and cannot be created/deleted via API
