# --- 1. Imports ---
import os
import json
import tempfile
import asyncio
import requests
from datetime import datetime, date, timedelta
from typing import List, Optional

# --- FastAPI & Pydantic ---
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# --- Environment & Services ---
from dotenv import load_dotenv
from groq import Groq
from langchain_groq import ChatGroq
from langchain.schema import HumanMessage

# --- Local App Imports ---
from app.integrations.notion_integration import NotionIntegration
from app.services.email_service import EmailService
from app.audio_processor import AudioProcessor
from app.core.scheduler import start_scheduler
from app.db.database import engine, Base
from app.routes import chat, ping, ws_chat, reports

# --- 2. Initial Setup ---
print("[INFO] Loading environment variables...")
load_dotenv()

# --- 3. FastAPI App Instantiation ---
# Create the app instance ONCE.
app = FastAPI(title="ZenAI Backend", version="1.0.0")

# --- 4. Middleware ---
# Add middleware immediately after app creation.
origins = [
    "http://localhost:5173",  # React dev server
    "http://127.0.0.1:5173", # React dev server
    # Add your deployed frontend URL here
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Or ["*"] for public access
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 5. Service Initializations ---

# Initialize Groq (with error handling)
try:
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    models = groq_client.models.list()
    print(f"[DEBUG] Found {len(models.data)} available Groq models")
    
    preferred_models = [
        'llama-3.3-70b-versatile',
        'llama-3.1-8b-instant',
        'meta-llama/llama-4-scout-17b-16e-instruct',
        'gemma2-9b-it',
        'qwen/qwen3-32b'
    ]
    
    model_name = None
    for model in preferred_models:
        if any(m.id == model for m in models.data):
            model_name = model
            print(f"[INFO] Selected preferred model: {model_name}")
            break
    
    if not model_name:
        chat_models = [m.id for m in models.data if 'instruct' in m.id.lower() or 'chat' in m.id.lower()]
        if not chat_models:
            raise Exception("No suitable chat models available")
        model_name = chat_models[0]
        print(f"[INFO] Falling back to model: {model_name}")
    
    llm = ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name=model_name,
        temperature=0.1
    )
    print("[INFO] Groq client successfully initialized")
    
except Exception as e:
    print(f"[ERROR] Groq initialization failed: {e}")
    llm = None

# Initialize Audio Processor
try:
    audio_processor = AudioProcessor()
    print("[INFO] Audio processor initialized")
except Exception as e:
    print(f"[ERROR] Audio processor initialization failed: {e}")
    audio_processor = None

# Initialize Notion Integration
try:
    notion_integration = NotionIntegration()
    print("[INFO] Notion integration initialized")
except Exception as e:
    print(f"[ERROR] Notion integration initialization failed: {e}")
    notion_integration = None

# Initialize Email Service
try:
    email_service = EmailService()
    print("[INFO] Email service initialized")
except Exception as e:
    print(f"[ERROR] Email service initialization failed: {e}")
    email_service = None

# --- 6. Pydantic Models ---

# Request model
class MeetingRequest(BaseModel):
    meeting_text: str

# Response models
class TaskItem(BaseModel):
    title: str
    description: str
    assignee: Optional[str] = None
    priority: str  # High, Medium, Low
    due_date: Optional[str] = None

class MeetingAnalysis(BaseModel):
    key_decisions: List[str]
    action_items: List[TaskItem]
    risks_and_blockers: List[str]
    meeting_summary: str

# --- 7. Startup Events ---
# Combined startup event for scheduler and database
@app.on_event("startup")
async def startup_event():
    print("[INFO] Running startup tasks...")
    
    # Start background scheduler
    try:
        start_scheduler()
        print("[INFO] Background scheduler started.")
    except Exception as e:
        print(f"[ERROR] Failed to start scheduler: {e}")
        
    # Initialize database
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("[INFO] Database tables checked/created.")
    except Exception as e:
        print(f"[ERROR] Failed to initialize database: {e}")
    
    print("[INFO] Startup complete.")

# --- 8. Routers ---
# Include all routers from other files
app.include_router(ping.router, prefix="/api", tags=["Test"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(ws_chat.router, tags=["WebSocket Chat"])
app.include_router(reports.router, prefix="/api", tags=["Reports"])

# --- 9. API Endpoints (defined in main.py) ---

@app.get("/")
async def root():
    return {
        "message": "AI Project Manager Agent is running!",
        "groq_status": "connected" if llm else "failed",
        "audio_status": "enabled" if audio_processor else "disabled",
        "notion_status": "connected" if notion_integration else "disabled",
        "email_status": "enabled" if email_service else "disabled"
    }

@app.get("/test-notion")
async def test_notion():
    if not notion_integration:
        raise HTTPException(status_code=503, detail="Notion not initialized")
    
    try:
        response = notion_integration.client.databases.retrieve(
            database_id=notion_integration.database_id
        )
        return {
            "success": True,
            "database_title": response.get("title", [{}])[0].get("plain_text", "Unknown"),
            "database_id": notion_integration.database_id
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/analyze-meeting", response_model=MeetingAnalysis)
async def analyze_meeting_text(request: MeetingRequest):
    """
    Analyze meeting transcript and extract structured information
    """
    if not llm:
        raise HTTPException(status_code=503, detail="Groq API not initialized")
    
    meeting_text = request.meeting_text
    
    if not meeting_text.strip():
        raise HTTPException(status_code=400, detail="meeting_text cannot be empty")
    
    prompt = f"""
    You are an AI Project Manager. Analyze this meeting transcript and extract:
    
    1. Key decisions made
    2. Action items (with assignee if mentioned, priority, due date if mentioned)
    3. Risks and blockers identified
    4. Brief meeting summary
    
    Meeting transcript:
    {meeting_text}
    
    Format your response as JSON with this structure:
    {{
        "key_decisions": ["decision 1", "decision 2"],
        "action_items": [
            {{
                "title": "task title",
                "description": "detailed description",
                "assignee": "person name or null",
                "priority": "High/Medium/Low",
                "due_date": "date if mentioned or null"
            }}
        ],
        "risks_and_blockers": ["risk 1", "risk 2"],
        "meeting_summary": "brief summary of the meeting"
    }}
    
    Only return valid JSON, no additional text.
    """
    
    try:
        print(f"[INFO] Analyzing meeting text: {meeting_text[:100]}...")
        
        message = HumanMessage(content=prompt)
        response = llm([message])
        
        print("[DEBUG] Groq response received")
        
        content = response.content.strip()
        if content.startswith('```json'):
            content = content[7:-3].strip()
        elif content.startswith('```'):
            content = content[3:-3].strip()
            
        analysis = json.loads(content)
        return analysis
    
    except json.JSONDecodeError as e:
        error_msg = f"JSON parsing error: {e}"
        print(f"[ERROR] {error_msg}")
        print(f"[DEBUG] Raw response: {response.content}")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    
    except Exception as e:
        error_msg = f"Error during meeting analysis: {e}"
        print(f"[ERROR] {error_msg}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")

@app.post("/analyze-meeting-audio")
async def analyze_meeting_audio(audio_file: UploadFile = File(...)):
    """
    Upload audio file, transcribe it, and analyze the meeting
    Supported formats: MP3, MP4, M4A, WAV, WebM
    """
    if not llm:
        raise HTTPException(status_code=503, detail="Groq API not initialized")
    if not audio_processor:
        raise HTTPException(status_code=503, detail="Audio processor not initialized")
        
    file_extension = os.path.splitext(audio_file.filename)[1].lower()
    if file_extension not in audio_processor.supported_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported format. Supported: {', '.join(audio_processor.supported_formats)}"
        )
    
    temp_file_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file_path = temp_file.name
            await audio_processor.save_upload_file(audio_file, temp_file_path)
        
        print(f"[INFO] Audio file saved: {temp_file_path}")
        
        transcript = audio_processor.transcribe_audio(temp_file_path)
        print(f"[INFO] Transcript: {transcript[:200]}...")
        
        # Analyze the transcript
        analysis_request = MeetingRequest(meeting_text=transcript)
        analysis = await analyze_meeting_text(analysis_request)
        
        # Add transcript to response
        analysis['transcript'] = transcript
        return analysis
    
    except Exception as e:
        print(f"[ERROR] Audio analysis failed: {e}")
        # Re-raise HTTPExceptions from analyze_meeting_text
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        if temp_file_path:
            audio_processor.cleanup_file(temp_file_path)

@app.post("/analyze-and-sync")
async def analyze_and_sync_to_notion(request: MeetingRequest):
    """
    Analyze meeting text AND automatically create tasks in Notion
    """
    if not llm:
        raise HTTPException(status_code=503, detail="Groq API not initialized")
    if not notion_integration:
        raise HTTPException(status_code=503, detail="Notion integration not available")
        
    if not request.meeting_text.strip():
        raise HTTPException(status_code=400, detail="meeting_text cannot be empty")
    
    try:
        print("[INFO] Analyzing meeting and syncing to Notion...")
        
        # 1. Analyze the meeting
        analysis = await analyze_meeting_text(request)
        
        # 2. Create tasks in Notion
        notion_results = notion_integration.create_tasks_from_meeting(
            action_items=analysis.get("action_items", []),
            meeting_summary=analysis.get("meeting_summary", "Meeting"),
            meeting_date=datetime.now().strftime("%Y-%m-%d")
        )
        
        # 3. Add Notion sync results to response
        analysis["notion_sync"] = {
            "total_tasks": len(notion_results),
            "successful": sum(1 for r in notion_results if r.get("success")),
            "failed": sum(1 for r in notion_results if not r.get("success")),
            "tasks": notion_results
        }
        
        return analysis
        
    except Exception as e:
        print(f"[ERROR] Analysis/sync failed: {e}")
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")

@app.get("/dashboard")
async def get_dashboard():
    """Get project overview dashboard with task metrics"""
    if not notion_integration:
        raise HTTPException(status_code=503, detail="Notion not available")
    
    try:
        tasks = notion_integration.query_all_tasks_with_emails()
        
        total_tasks = len(tasks)
        completed = sum(1 for t in tasks if t['status'] == "Done")
        in_progress = sum(1 for t in tasks if t['status'] == "In Progress")
        todo = sum(1 for t in tasks if t['status'] == "To Do")
        
        today = date.today()
        overdue_count = 0
        
        for task in tasks:
            if task['due_date'] and task['status'] != "Done":
                try:
                    due = datetime.strptime(task['due_date'], "%Y-%m-%d").date()
                    if due < today:
                        task['is_overdue'] = True
                        overdue_count += 1
                    else:
                        task['is_overdue'] = False
                except:
                    task['is_overdue'] = False
            else:
                task['is_overdue'] = False
        
        return {
            "summary": {
                "total_tasks": total_tasks,
                "completed": completed,
                "in_progress": in_progress,
                "todo": todo,
                "overdue": overdue_count,
                "completion_rate": f"{(completed/total_tasks*100):.1f}%" if total_tasks > 0 else "0%"
            },
            "tasks": tasks
        }
    
    except Exception as e:
        print(f"[ERROR] Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")

@app.get("/tasks/overdue")
async def get_overdue_tasks():
    """Get list of overdue tasks with assignee emails"""
    if not notion_integration:
        raise HTTPException(status_code=503, detail="Notion not available")
    
    try:
        tasks = notion_integration.query_all_tasks_with_emails()
        today = date.today()
        overdue_tasks = []
        
        for task in tasks:
            if task['status'] == "Done":
                continue
            
            if task['due_date']:
                try:
                    due = datetime.strptime(task['due_date'], "%Y-%m-%d").date()
                    if due < today:
                        days_overdue = (today - due).days
                        overdue_tasks.append({
                            "title": task['title'],
                            "assignee": task['assignee_name'],
                            "assignee_email": task['assignee_email'],
                            "priority": task['priority'],
                            "due_date": task['due_date'],
                            "days_overdue": days_overdue,
                            "status": task['status'],
                            "url": task['url']
                        })
                except:
                    pass
        
        overdue_tasks.sort(key=lambda x: x['days_overdue'], reverse=True)
        
        return {
            "total_overdue": len(overdue_tasks),
            "tasks": overdue_tasks
        }
    
    except Exception as e:
        print(f"[ERROR] Overdue tasks error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/tasks/at-risk")
async def get_at_risk_tasks():
    """Get tasks at risk (due in next 2 days) with assignee emails"""
    if not notion_integration:
        raise HTTPException(status_code=503, detail="Notion not available")
    
    try:
        tasks = notion_integration.query_all_tasks_with_emails()
        
        today = date.today()
        risk_threshold = today + timedelta(days=2)
        at_risk_tasks = []
        
        for task in tasks:
            if task['status'] == "Done":
                continue
            
            if task['due_date']:
                try:
                    due = datetime.strptime(task['due_date'], "%Y-%m-%d").date()
                    
                    if today <= due <= risk_threshold:
                        days_until_due = (due - today).days
                        at_risk_tasks.append({
                            "title": task['title'],
                            "assignee": task['assignee_name'],
                            "assignee_email": task['assignee_email'],
                            "priority": task['priority'],
                            "due_date": task['due_date'],
                            "days_until_due": days_until_due,
                            "status": task['status'],
                            "url": task['url']
                        })
                except:
                    pass
        
        at_risk_tasks.sort(key=lambda x: x['days_until_due'])
        
        return {
            "total_at_risk": len(at_risk_tasks),
            "tasks": at_risk_tasks
        }
    
    except Exception as e:
        print(f"[ERROR] At-risk tasks error: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/reports/daily")
async def generate_daily_report():
    """
    Generate daily progress report
    """
    if not notion_integration:
        raise HTTPException(status_code=503, detail="Notion not available")
        
    try:
        dashboard = await get_dashboard()
        overdue = await get_overdue_tasks()
        at_risk = await get_at_risk_tasks()
        
        today_str = datetime.now().strftime("%A, %B %d, %Y")
        
        report_lines = [
            f"# Daily Project Report - {today_str}",
            "",
            "## Summary",
            f"- **Total Tasks**: {dashboard['summary']['total_tasks']}",
            f"- **Completed**: {dashboard['summary']['completed']} ({dashboard['summary']['completion_rate']})",
            f"- **In Progress**: {dashboard['summary']['in_progress']}",
            f"- **To Do**: {dashboard['summary']['todo']}",
            f"- **Overdue**: {dashboard['summary']['overdue']}",
            f"- **At Risk**: {len(at_risk['tasks'])}",
            "",
            f"## Overdue Tasks ({overdue['total_overdue']})",
            ""
        ]
        
        if overdue['tasks']:
            for task in overdue['tasks']:
                report_lines.append(f"- **{task['title']}** ({task['assignee']}) - {task['days_overdue']} days overdue")
        else:
            report_lines.append("- No overdue tasks!")
        
        report_lines.extend([
            "",
            f"## At-Risk Tasks ({at_risk['total_at_risk']})",
            ""
        ])
        
        if at_risk['tasks']:
            for task in at_risk['tasks']:
                report_lines.append(f"- **{task['title']}** ({task['assignee']}) - due in {task['days_until_due']} days")
        else:
            report_lines.append("- No at-risk tasks")
            
        report_lines.extend([
            "",
            "## Team Workload",
            ""
        ])
        
        assignee_counts = {}
        for task in dashboard['tasks']:
            assignee = task['assignee_name']
            if task['status'] != "Done":
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
        
        for assignee, count in sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- **{assignee}**: {count} active tasks")
        
        report = "\n".join(report_lines)
        
        return {
            "reported_date": today_str,
            "markdown": report,
            "summary": dashboard['summary'],
            "overdue_count": overdue['total_overdue'],
            "at_risk_count": at_risk['total_at_risk']
        }
        
    except Exception as e:
        print(f"[ERROR] Report generation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")

@app.post("/notifications/send-daily-report")
async def send_daily_report_email(email: Optional[str] = None):
    """
    Send daily report via email
    - If email is provided: send to that specific email
    - If no email: send to all team members who have tasks
    """
    if not email_service:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    try:
        report_data = await generate_daily_report()
        results = []
        
        if email:
            success = email_service.send_daily_report(
                report_markdown=report_data['markdown'],
                to_email=email
            )
            results.append({"email": email, "sent": success})
        else:
            dashboard = await get_dashboard()
            unique_emails = set()
            for task in dashboard['tasks']:
                if task.get('assignee_email'):
                    unique_emails.add((task['assignee_name'], task['assignee_email']))
            
            notification_email = os.getenv("NOTIFICATION_EMAIL")
            if notification_email:
                unique_emails.add(("Team Lead", notification_email))
            
            for assignee_name, assignee_email in unique_emails:
                success = email_service.send_daily_report(
                    report_markdown=report_data['markdown'],
                    to_email=assignee_email
                )
                results.append({
                    "assignee": assignee_name,
                    "email": assignee_email,
                    "sent": success
                })
        
        return {
            "total_sent": len(results),
            "successful": sum(1 for r in results if r.get('sent')),
            "failed": sum(1 for r in results if not r.get('sent')),
            "results": results
        }
    
    except Exception as e:
        print(f"[ERROR] Failed to send daily report: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/notifications/send-overdue-alerts")
async def send_overdue_alerts_email():
    """Send overdue task alerts to individual assignees using their Notion emails"""
    if not email_service:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    try:
        overdue = await get_overdue_tasks()
        results = []
        fallback_email = os.getenv("NOTIFICATION_EMAIL")
        
        for task in overdue['tasks']:
            target_email = task.get('assignee_email') or fallback_email
            
            if target_email:
                success = email_service.send_overdue_alert(
                    task_title=task['title'],
                    assignee=task['assignee'],
                    days_overdue=task['days_overdue'],
                    task_url=task['url'],
                    to_email=target_email
                )
                results.append({
                    "task": task['title'],
                    "assignee": task['assignee'],
                    "email": target_email,
                    "email_source": "notion" if task.get('assignee_email') else "fallback",
                    "sent": success
                })
            else:
                results.append({
                    "task": task['title'],
                    "assignee": task['assignee'],
                    "email": None,
                    "sent": False,
                    "error": "No email available"
                })
        
        return {
            "total_alerts": len(results),
            "successful": sum(1 for r in results if r.get('sent')),
            "failed": sum(1 for r in results if not r.get('sent')),
            "results": results
        }
    
    except Exception as e:
        print(f"[ERROR] Failed to send overdue alerts: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/notifications/send-at-risk-reminders")
async def send_at_risk_reminders_email():
    """Send deadline reminders using Notion emails"""
    if not email_service:
        raise HTTPException(status_code=503, detail="Email service not configured")
    
    try:
        at_risk = await get_at_risk_tasks()
        results = []
        fallback_email = os.getenv("NOTIFICATION_EMAIL")
        
        for task in at_risk['tasks']:
            target_email = task.get('assignee_email') or fallback_email
            
            if target_email:
                success = email_service.send_deadline_reminder(
                    task_title=task['title'],
                    assignee=task['assignee'],
                    days_until_due=task['days_until_due'],
                    task_url=task['url'],
                    to_email=target_email
                )
                results.append({
                    "task": task['title'],
                    "assignee": task['assignee'],
                    "email": target_email,
                    "email_source": "notion" if task.get('assignee_email') else "fallback",
                    "sent": success
                })
            else:
                results.append({
                    "task": task['title'],
                    "assignee": task['assignee'],
                    "email": None,
                    "sent": False,
                    "error": "No email available"
                })
        
        return {
            "total_reminders": len(results),
            "successful": sum(1 for r in results if r.get('sent')),
            "failed": sum(1 for r in results if not r.get('sent')),
            "results": results
        }
    
    except Exception as e:
        print(f"[ERROR] Failed to send at-risk reminders: {e}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

# --- 10. Serve Frontend ---
# This must come AFTER all API routes
frontend_path = os.path.join(os.path.dirname(__file__), "../frontend/dist")
if os.path.exists(frontend_path):
    print(f"[INFO] Serving frontend from: {frontend_path}")
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")
else:
    print(f"[WARN] Frontend directory not found: {frontend_path}")
    print("[WARN] Frontend will not be served by FastAPI.")

# --- 11. Main Entry Point ---
if __name__ == "__main__":
    import uvicorn
    print("[INFO] Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8080)