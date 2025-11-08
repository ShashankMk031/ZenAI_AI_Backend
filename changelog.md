# Changelog - ZenAI AI Project Manager

## Project Context
ZenAI is an AI-powered project management automation system that listens to meeting recordings, extracts actionable insights, and automatically manages tasks in project management tools. The system focuses on execution automation rather than strategy - it handles repetitive PM work so humans can focus on leadership and innovation.


## Core Value Proposition
**Problem:** Project managers spend 1-2 hours daily on mechanical tasks (creating tickets, sending reminders, tracking deadlines)
**Solution:** Autonomous AI agent that handles these tasks automatically
**Result:** PMs save 30-45 minutes per day and focus on strategy instead of administration

--- 

## Email Notification with Notion Integration 

### Email Notification system complete 

**New Endpoints:**
- POST /notifications/send-daily-report - Send daily project summary via email
- POST /notifications/send-overdue-alerts - Send overdue task alerts to assignees
- POST /notifications/send-at-risk-reminders - Send deadline reminders to assignees

**Email Features Implemented:**
- Individual personalized emails to team members
- Extracts email addresses from Notion Person properties
- Professional HTML email formatting with styling
- Plain text fallback for compatibility
- Direct links to Notion tasks in emails
- Fallback to NOTIFICATION_EMAIL if no Notion email found

**Email Types:**
1. **Daily Project Report**
   - Summary metrics (total, completed, overdue, at-risk)
   - Detailed overdue task list
   - At-risk task breakdown
   - Team workload distribution
   - Can send to entire team or specific person

2. **Overdue Task Alerts**
   - Red alert styling for urgency
   - Shows days overdue count
   - Personalized to assignee
   - Direct Notion task link
   - Motivational call to action

3. **Deadline Reminders**
   - Orange reminder styling
   - Shows days until due
   - Encouraging tone
   - Proactive (sent before deadline)
   - Direct task access

**Technical Implementation:**
- Created app/services/email_service.py module
- EmailService class with SMTP integration
- Support for Gmail, Outlook, Yahoo, SendGrid
- Basic markdown to HTML conversion
- Error handling and logging for email failures
- Async-ready architecture

**Configuration:**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-password-here
NOTIFICATION_EMAIL=fallback-email@gmail.com
```

**Dependencies Added:**
- aiosmtplib==3.0.1 (SMTP client - not used yet, ready for async)
- email-validator==2.1.0 (Email validation)
- smtplib (built-in Python SMTP)

**Email Extraction from Notion:**
- Reads Notion Person property
- Extracts email addresses automatically
- No manual email mapping required
- Falls back to NOTIFICATION_EMAIL if needed

## Notion person property integration 

### Enhanced Notion Integration with Real Emails

**Updated Notion Integration:**
- Support for Person property type (not just text)
- Automatic email extraction from Notion users
- New method: get_assignee_email_from_task()
- New method: query_all_tasks_with_emails()

**Dashboard Enhanced:**
- Now includes assignee_name and assignee_email for all tasks
- Email addresses displayed in task details
- Ready for automated notifications

**API Response Updates:**
- All task endpoints now return assignee_email field
- Example:
```json
{
  "assignee_name": "A",
  "assignee_email": "a@company.com"
}
```

**Migration Path:**
1. Change Assignee property from Text to Person in Notion
2. Invite team members to Notion workspace
3. Assign tasks to Notion users (not text names)
4. ZenAI automatically extracts their email addresses
5. Emails sent to correct person automatically

---

#Progress tracking & Reporting system 

### Dashboard & Monitoring Features

**New Endpoints:**
- GET /dashboard - Real-time project overview with task metrics
- GET /tasks/overdue - List of all overdue tasks with days overdue count
- GET /tasks/at-risk - Tasks due within 2 days that need attention
- GET /reports/daily - Automated daily progress report in markdown format

**Dashboard Features:**
- Real-time task metrics (total, completed, in-progress, todo)
- Completion rate calculation
- Overdue task counter
- At-risk task detection (due within 48 hours)
- Individual task status tracking with URLs
- Team workload distribution

**Overdue Task Detection:**
- Automatic calculation of days overdue
- Filters out completed tasks
- Sorts by most overdue first (priority)
- Includes assignee, priority, and due date information
- Direct task URLs for quick access

**At-Risk Task Monitoring:**
- Identifies tasks due within next 2 days
- Excludes completed tasks
- Sorts by urgency (soonest first)
- Helps prevent last-minute rushes
- Proactive risk management

**Daily Report Generation:**
- Markdown formatted reports
- Summary metrics (total, completed, overdue, at-risk)
- Detailed overdue task list
- At-risk task breakdown
- Team workload analysis
- Clean, shareable format
- Email-ready

**Technical Implementation:**
- Direct Notion API queries for real-time data
- Date comparison logic for overdue detection
- 48-hour window for at-risk calculation
- Markdown formatting for reports
- Error handling for API failures

--- 


## Natural lang date parsing 


### Date processing 

### Intelligent Date Processing

**Date Parser Utility Created:**
- Created app/utils/date_parser.py module
- Converts natural language dates to YYYY-MM-DD format
- Supports both past and future dates
- Handles 15+ different date formats

**Supported Date Formats:**
- Relative dates: "tomorrow", "yesterday", "today"
- Day names: "Monday", "Friday", "next Monday", "last Friday"
- Week references: "next week", "last week"
- Numeric: "in 3 days", "5 days ago", "3 days ago"
- Standard: "2025-10-15" (pass-through)

**Integration:**
- Automatic date parsing in Notion task creation
- AI extracts natural language dates from meetings
- Parser converts to ISO format before Notion sync
- Validates date format before sending to Notion
- Handles parsing errors gracefully
- Logs warnings for unparseable dates

**Technical Implementation:**
- Uses Python datetime for calculations
- Regex pattern matching for complex formats
- Timezone-aware date handling
- Weekday calculation algorithm
- Error recovery for invalid inputs
 
## Audio Transcription & Processing 

### Audio Intelligence Features

**New Endpoints:**
- POST /analyze-meeting-audio - Accepts audio files, transcribes them, and returns structured analysis

**Audio Processing Pipeline:**
Audio Upload → Temporary Storage → Whisper Transcription → LLM Analysis → Structured JSON

**Technical Implementation:**
- Created app/audio_processor.py module
  - AudioProcessor class handles file operations and transcription
  - Supports: MP3, MP4, M4A, WAV, WebM formats
  - Automatic temporary file cleanup after processing
  - Async file handling with aiofiles

- Integrated OpenAI Whisper-1 API
  - Transcribes audio to text with high accuracy
  - Handles transcription errors gracefully
  - Returns full transcript along with analysis
  - Cost: ~$0.006 per minute of audio

- Enhanced app/main.py
  - Added audio file upload endpoint
  - File format validation
  - Multi-service status tracking in health check
  - Error handling for missing audio processor
  - Temporary file management

**Dependencies Added:**
- openai==1.35.0 (Whisper API client)
- python-multipart==0.0.6 (File upload handling)
- aiofiles==23.2.1 (Async file operations)

**Response Format:**
```json
{
  "transcript": "full meeting transcription",
  "key_decisions": ["decision 1", "decision 2"],
  "action_items": [
    {
      "title": "task name",
      "description": "details",
      "assignee": "person or null",
      "priority": "High/Medium/Low",
      "due_date": "date or null"
    }
  ],
  "risks_and_blockers": ["risk 1"],
  "meeting_summary": "brief overview"
}
```

**Health Check Enhanced:**
- GET / now returns audio_status in addition to groq_status
- Helps diagnose which services are operational

---

## Core AI Agent & Notion Integration 

### Foundation & Core Features

**Core AI Agent Implementation:**
- FastAPI backend with automatic OpenAPI documentation
- RESTful API design for easy integration
- Environment-based configuration via .env
- Structured logging for debugging

**AI Integration:**
- Groq LLM for natural language processing (Llama 3.3 70B)
- LangChain framework for AI agent orchestration
- Smart model selection - automatically detects available models
- Preferred models in priority order:
  1. llama-3.3-70b-versatile (primary - best quality)
  2. llama-3.1-8b-instant (fast fallback)
  3. meta-llama/llama-4-scout-17b-16e-instruct
  4. gemma2-9b-it
  5. qwen/qwen3-32b

**Meeting Analysis Capabilities:**
- POST /analyze-meeting - Accepts meeting transcript as text
- Extracts structured information:
  - Key Decisions: Important choices made during meeting
  - Action Items: Tasks with optional assignee, priority, due date
  - Risks & Blockers: Identified obstacles and concerns
  - Meeting Summary: Concise overview
- Returns validated JSON response via Pydantic models
- Low temperature (0.1) for consistent, deterministic responses

**Notion Integration:**
- POST /analyze-and-sync - Analyze meeting AND create tasks in Notion
- Direct HTTP API integration (bypassed notion-client library for reliability)
- Automatic task creation from meeting analysis
- Support for multiple task properties:
  - Name (Title)
  - Description (Text)
  - Assignee (Text initially, Person property later)
  - Priority (Select: High, Medium, Low) Default: Medium
  - Status (Select: To Do, In Progress, Done) Default: To Do
  - Due Date (Date)
  - Meeting Date (Date)
  - Source (Text - tracks which meeting created the task)

**Technical Details:**
- Markdown code block cleanup (handles ```json formatting from AI)
- JSON parsing with error recovery
- Input validation via Pydantic models
- Batch task creation from meetings
- Full sync status reporting in API responses

**Data Models:**
```python
TaskItem: title, description, assignee, priority, due_date
MeetingAnalysis: key_decisions, action_items, risks_and_blockers, meeting_summary
```

**Core Dependencies:**
- fastapi==0.104.1
- uvicorn==0.24.0
- langchain==0.1.20
- langchain-groq==0.1.3
- groq==0.9.0
- pydantic==2.8.0
- python-dotenv==1.0.0
- requests==2.31.0
- httpx==0.27.0

**Configuration:**
```bash
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...
NOTION_API_KEY=ntn_... (supports both ntn_ and secret_ prefixes)
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

---

## Architecture Overview

### System Design Flow
```
Input Layer:
  - Text transcripts (POST /analyze-meeting)
  - Audio files (POST /analyze-meeting-audio)

Processing Layer:
  - AudioProcessor → Whisper API → Transcript
  - LangChain → Groq LLM → Structured Analysis
  - DateParser → ISO Format Dates

Integration Layer:
  - Notion API (direct HTTP) → Task Creation
  - Gmail SMTP → Email Notifications

Monitoring Layer:
  - Dashboard → Real-time Metrics
  - Overdue Detection → Automated Alerts
  - At-Risk Monitoring → Proactive Reminders

Output Layer:
  - Structured JSON responses (Pydantic validated)
  - Email notifications (HTML formatted)
  - Daily reports (Markdown)
```

### Project Structure
```
ZenAI/
├── app/
│   ├── __init__.py
│   ├── main.py (FastAPI app + 11 endpoints)
│   ├── audio_processor.py (Whisper transcription)
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── notion_integration.py (Direct HTTP API)
│   ├── utils/
│   │   ├── __init__.py
│   │   └── date_parser.py (Natural language dates)
│   ├── services/
│   │   ├── __init__.py
│   │   └── email_service.py (SMTP email)
│   ├── core/ (Reserved for future)
│   └── agents/ (Reserved for future)
├── venv/ (Virtual environment)
├── .env (Environment variables)
├── requirements.txt (Python dependencies)
├── CHANGELOG.md (This file)
└── README.md (Setup documentation)
```

### Environment Variables Required
```bash
# AI Services
GROQ_API_KEY=gsk_...
OPENAI_API_KEY=sk-...

# Notion Integration
NOTION_API_KEY=ntn_...
NOTION_DATABASE_ID=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx

# Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=app-password
NOTIFICATION_EMAIL=fallback@gmail.com
```

---

## API Endpoints Reference

### Core Endpoints
| Method | Endpoint | Purpose | Input | Output |
|--------|----------|---------|-------|--------|
| GET | `/` | Health check | None | Service status (all services) |
| POST | `/analyze-meeting` | Analyze text | `{"meeting_text": "..."}` | Meeting analysis JSON |
| POST | `/analyze-meeting-audio` | Analyze audio | Audio file (multipart) | Transcript + analysis |
| POST | `/analyze-and-sync` | Analyze + Notion sync | `{"meeting_text": "..."}` | Analysis + sync status |

### Monitoring Endpoints
| Method | Endpoint | Purpose | Output |
|--------|----------|---------|--------|
| GET | `/dashboard` | Project overview | Real-time metrics + task list |
| GET | `/tasks/overdue` | Overdue tasks | Tasks with days overdue |
| GET | `/tasks/at-risk` | At-risk tasks | Tasks due within 48h |
| GET | `/reports/daily` | Daily report | Markdown formatted report |

### Notification Endpoints
| Method | Endpoint | Purpose | Input | Output |
|--------|----------|---------|-------|--------|
| POST | `/notifications/send-daily-report` | Email daily report | `?email=...` (optional) | Send status |
| POST | `/notifications/send-overdue-alerts` | Email overdue alerts | None | Batch send status |
| POST | `/notifications/send-at-risk-reminders` | Email deadline reminders | None | Batch send status |

### Interactive Documentation
- **Swagger UI:** http://localhost:8080/docs
- **ReDoc:** http://localhost:8080/redoc

---

## Development Environment

**Current Setup:**
- **OS:** macOS (cross-platform compatible)
- **Python:** 3.12
- **IDE:** VS Code + Windsurf
- **Virtual Environment:** venv/
- **Package Manager:** pip
- **Default Port:** 8080

**Running the Server:**
```bash
cd ~/Documents/Ubuntu-applications/ZenAI
source venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8080 --reload
```

**Note:** Codebase is fully cross-platform. Only system-level package installation differs between macOS (Homebrew) and Ubuntu (apt).

---

## Performance & Limitations

### Current Performance
- **Text analysis:** ~2-5 seconds
- **Audio transcription:** ~10-30 seconds (depends on audio length)
- **Notion sync:** ~1-2 seconds per task
- **Dashboard queries:** ~1-2 seconds
- **Email sending:** ~1-2 seconds per email

### API Usage & Costs
- **Groq (free tier):** 100 requests/day
- **OpenAI Whisper:** ~$0.006 per minute of audio
- **Gmail SMTP:** Free (with app passwords)
- **Notion API:** Free for standard usage

### Known Limitations
- Audio files limited to 25MB (Whisper constraint)
- No real-time streaming yet
- Single meeting processing (no batch mode)
- English language optimized (other languages may vary)
- Notion properties must exist in database before sync
- Date parser may not handle all edge cases

---

## Testing Status

### Tested & Working 
- Text-based meeting analysis
- Audio file upload and transcription
- Multi-format audio support (MP3, WAV, M4A, MP4, WebM)
- Notion task creation and sync
- Natural language date parsing (15+ formats)
- Dashboard metrics and real-time updates
- Overdue task detection with day counting
- At-risk task monitoring (48-hour window)
- Daily report generation (markdown)
- Email notifications (HTML + plain text)
- Notion Person property integration
- Email address extraction from Notion
- Cross-platform compatibility (Ubuntu → macOS)

### Not Yet Tested 
- Scheduled automation (not implemented)
- Large audio files (>10 minutes)
- Non-English languages
- Concurrent request handling
- High-volume task creation (100+ tasks)
- Multiple simultaneous meetings
- Email delivery to 50+ recipients

---

## Design Philosophy

### Core Principles
1. **Execution over Strategy:** Automate repetitive PM tasks, not strategic planning
2. **Human Augmentation:** Assist human PMs, don't replace them
3. **Reliability:** Graceful error handling, never crash
4. **Transparency:** Clear logging, structured outputs
5. **Modularity:** Easy to extend and integrate new tools

### What ZenAI Does
- Extract action items from meetings automatically
- Track deadlines and detect overdue tasks
- Flag risks and blockers proactively
- Send personalized reminders to team members
- Update project management tools (Notion)
- Generate daily progress reports
- Monitor team workload distribution
