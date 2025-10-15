from dotenv import load_dotenv 
import os 

# Load environment variables
load_dotenv() 

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import json
import tempfile
from app.integrations.notion_integration import NotionIntegration
from datetime import datetime

app = FastAPI(title="AI Project Manager Agent", version="1.0.0")

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

# Initialize Groq (with error handling)
try:
    from groq import Groq
    from langchain_groq import ChatGroq
    from langchain.schema import HumanMessage
    
    # Initialize Groq client
    groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    
    # List available models and filter for chat-compatible ones
    models = groq_client.models.list()
    print(f"[DEBUG] Found {len(models.data)} available models")
    
    # Prefer these models in order
    preferred_models = [
        'llama-3.3-70b-versatile',
        'llama-3.1-8b-instant',
        'meta-llama/llama-4-scout-17b-16e-instruct',
        'gemma2-9b-it',
        'qwen/qwen3-32b'
    ]
    
    # Find the first available preferred model
    model_name = None
    for model in preferred_models:
        if any(m.id == model for m in models.data):
            model_name = model
            print(f"[INFO] Selected preferred model: {model_name}")
            break
    
    # Fallback to any model that might work if no preferred model found
    if not model_name:
        chat_models = [m.id for m in models.data if 'instruct' in m.id.lower() or 'chat' in m.id.lower()]
        if not chat_models:
            raise Exception("No suitable chat models available")
        model_name = chat_models[0]
        print(f"[INFO] Falling back to model: {model_name}")
    
    # Initialize the language model
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
    from app.audio_processor import AudioProcessor
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

@app.get("/")
async def root():
    return {
        "message": "AI Project Manager Agent is running!", 
        "groq_status": "connected" if llm else "failed",
        "audio_status": "enabled" if audio_processor else "disabled",
        "notion_status": "connected" if notion_integration else "disabled"
    } 
@app.get("/test-notion") 
async def test_notion():
    # Test notion connection directly 
    if not notion_integration:
        return {"error" : "Notion not initialized"} 
    
    try : 
        # Trying to query the database 
        response = notion_integration.client.databases.retrieve(
            database_id = notion_integration.database_id 
        ) 
        return { 
            "success" : True, 
            "database_title " : response.get("title", [{}])[0].get("plain_text", "Unknown" ), 
            "database_id " : notion_integration.database_id 
            } 
    except Exception as e : 
        return { 
            "success" : False, 
            "error" : str(e) 
        }

@app.post("/analyze-meeting")
async def analyze_meeting_text(request: MeetingRequest):
    """
    Analyze meeting transcript and extract structured information
    """
    
    if not llm:
        raise HTTPException(status_code=500, detail="Groq API not initialized")
    
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
        
        # Call Groq API
        message = HumanMessage(content=prompt)
        response = llm([message])
        
        print(f"[DEBUG] Groq response received")
        
        # Clean the response to handle markdown code blocks
        content = response.content.strip()
        if content.startswith('```json'):
            content = content[7:-3].strip()
        elif content.startswith('```'):
            content = content[3:-3].strip()
            
        # Parse the JSON response
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
        raise HTTPException(status_code=500, detail="Groq API not initialized")
    
    if not audio_processor:
        raise HTTPException(status_code=500, detail="Audio processor not initialized")
    
    # Validate file format
    file_extension = os.path.splitext(audio_file.filename)[1].lower()
    if file_extension not in audio_processor.supported_formats:
        raise HTTPException(
            status_code=400, 
            detail=f"Unsupported format. Supported: {', '.join(audio_processor.supported_formats)}"
        )
    
    # Create temporary file
    temp_file_path = None
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as temp_file:
            temp_file_path = temp_file.name
            await audio_processor.save_upload_file(audio_file, temp_file_path)
        
        print(f"[INFO] Audio file saved: {temp_file_path}")
        
        # Transcribe audio
        transcript = audio_processor.transcribe_audio(temp_file_path)
        
        print(f"[INFO] Transcript: {transcript[:200]}...")
        
        # Analyze the transcript using existing logic
        prompt = f"""
        You are an AI Project Manager. Analyze this meeting transcript and extract:
        
        1. Key decisions made
        2. Action items (with assignee if mentioned, priority, due date if mentioned)
        3. Risks and blockers identified
        4. Brief meeting summary
        
        Meeting transcript:
        {transcript}
        
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
        
        # Call Groq API
        message = HumanMessage(content=prompt)
        response = llm([message])
        
        # Clean and parse response
        content = response.content.strip()
        if content.startswith('```json'):
            content = content[7:-3].strip()
        elif content.startswith('```'):
            content = content[3:-3].strip()
        
        analysis = json.loads(content)
        
        # Add transcript to response
        analysis['transcript'] = transcript
        
        return analysis
    
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    
    except Exception as e:
        print(f"[ERROR] Audio analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")
    
    finally:
        # Cleanup temporary file
        if temp_file_path:
            audio_processor.cleanup_file(temp_file_path)

@app.post("/analyze-and-sync")
async def analyze_and_sync_to_notion(request: MeetingRequest):
    """
    Analyze meeting text AND automatically create tasks in Notion
    """
    
    if not llm:
        raise HTTPException(status_code=500, detail="Groq API not initialized")
    
    if not notion_integration:
        raise HTTPException(status_code=500, detail="Notion integration not available")
    
    meeting_text = request.meeting_text
    
    if not meeting_text.strip():
        raise HTTPException(status_code=400, detail="meeting_text cannot be empty")
    
    # First, analyze the meeting (reuse existing logic)
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
        print(f"[INFO] Analyzing meeting and syncing to Notion...")
        
        # Call Groq API
        message = HumanMessage(content=prompt)
        response = llm([message])
        
        # Clean and parse response
        content = response.content.strip()
        if content.startswith('```json'):
            content = content[7:-3].strip()
        elif content.startswith('```'):
            content = content[3:-3].strip()
        
        analysis = json.loads(content)
        
        # Create tasks in Notion
        notion_results = notion_integration.create_tasks_from_meeting(
            action_items=analysis.get("action_items", []),
            meeting_summary=analysis.get("meeting_summary", "Meeting"),
            meeting_date=datetime.now().strftime("%Y-%m-%d")
        )
        
        # Add Notion sync results to response
        analysis["notion_sync"] = {
            "total_tasks": len(notion_results),
            "successful": sum(1 for r in notion_results if r.get("success")),
            "failed": sum(1 for r in notion_results if not r.get("success")),
            "tasks": notion_results
        }
        
        return analysis
    
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON parsing error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to parse AI response: {str(e)}")
    
    except Exception as e:
        print(f"[ERROR] Analysis/sync failed: {e}")
        raise HTTPException(status_code=500, detail=f"Operation failed: {str(e)}")

import requests

@app.get("/dashboard")
async def get_dashboard():
    """Get project overview dashboard with task metrics"""
    
    if not notion_integration:
        raise HTTPException(status_code=500, detail="Notion not available")
    
    try:
        # Query all tasks from Notion
        url = f"https://api.notion.com/v1/databases/{notion_integration.database_id}/query"
        response = requests.post(url, headers=notion_integration.headers, json={})
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to query Notion")
        
        data = response.json()
        tasks = data.get("results", [])
        
        # Calculate metrics
        total_tasks = len(tasks)
        completed = sum(1 for t in tasks if t.get("properties", {}).get("Status", {}).get("select", {}).get("name") == "Done")
        in_progress = sum(1 for t in tasks if t.get("properties", {}).get("Status", {}).get("select", {}).get("name") == "In Progress")
        todo = sum(1 for t in tasks if t.get("properties", {}).get("Status", {}).get("select", {}).get("name") == "To Do")
        
        # Get today's date for overdue calculation
        from datetime import datetime, date
        today = date.today()
        
        # Extract task details
        task_list = []
        overdue_count = 0
        
        for t in tasks:
            props = t.get("properties", {})
            
            # Get task name
            title = props.get("Name", {}).get("title", [{}])[0].get("plain_text", "Untitled")
            
            # Get status
            status = props.get("Status", {}).get("select", {}).get("name", "Unknown")
            
            # Get priority
            priority = props.get("Priority", {}).get("select", {}).get("name", "Unknown")
            
            # Get assignee
            assignee_data = props.get("Assignee", {}).get("rich_text", [])
            assignee = assignee_data[0].get("plain_text", "Unassigned") if assignee_data else "Unassigned"
            
            # Get due date
            due_date_obj = props.get("Due Date", {}).get("date")
            due_date = due_date_obj.get("start") if due_date_obj else None
            
            # Check if overdue
            is_overdue = False
            if due_date and status != "Done":
                try:
                    due = datetime.strptime(due_date, "%Y-%m-%d").date()
                    if due < today:
                        is_overdue = True
                        overdue_count += 1
                except:
                    pass
            
            task_list.append({
                "title": title,
                "status": status,
                "priority": priority,
                "assignee": assignee,
                "due_date": due_date,
                "is_overdue": is_overdue,
                "url": t.get("url")
            })
        
        return {
            "summary": {
                "total_tasks": total_tasks,
                "completed": completed,
                "in_progress": in_progress,
                "todo": todo,
                "overdue": overdue_count,
                "completion_rate": f"{(completed/total_tasks*100):.1f}%" if total_tasks > 0 else "0%"
            },
            "tasks": task_list
        }
    
    except Exception as e:
        print(f"[ERROR] Dashboard error: {e}")
        raise HTTPException(status_code=500, detail=f"Dashboard error: {str(e)}")


@app.get("/tasks/overdue")
async def get_overdue_tasks():
    """Get list of overdue tasks"""
    
    if not notion_integration:
        raise HTTPException(status_code=500, detail="Notion not available")
    
    try:
        # Query all tasks
        url = f"https://api.notion.com/v1/databases/{notion_integration.database_id}/query"
        response = requests.post(url, headers=notion_integration.headers, json={})
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to query Notion")
        
        data = response.json()
        tasks = data.get("results", [])
        
        from datetime import datetime, date
        today = date.today()
        
        overdue_tasks = []
        
        for t in tasks:
            props = t.get("properties", {})
            status = props.get("Status", {}).get("select", {}).get("name", "Unknown")
            
            # Skip completed tasks
            if status == "Done":
                continue
            
            # Get due date
            due_date_obj = props.get("Due Date", {}).get("date")
            due_date = due_date_obj.get("start") if due_date_obj else None
            
            if due_date:
                try:
                    due = datetime.strptime(due_date, "%Y-%m-%d").date()
                    if due < today:
                        # Task is overdue
                        days_overdue = (today - due).days
                        
                        title = props.get("Name", {}).get("title", [{}])[0].get("plain_text", "Untitled")
                        assignee_data = props.get("Assignee", {}).get("rich_text", [])
                        assignee = assignee_data[0].get("plain_text", "Unassigned") if assignee_data else "Unassigned"
                        priority = props.get("Priority", {}).get("select", {}).get("name", "Unknown")
                        
                        overdue_tasks.append({
                            "title": title,
                            "assignee": assignee,
                            "priority": priority,
                            "due_date": due_date,
                            "days_overdue": days_overdue,
                            "status": status,
                            "url": t.get("url")
                        })
                except:
                    pass
        
        # Sort by days overdue (most overdue first)
        overdue_tasks.sort(key=lambda x: x["days_overdue"], reverse=True)
        
        return {
            "total_overdue": len(overdue_tasks),
            "tasks": overdue_tasks
        }
    
    except Exception as e:
        print(f"[ERROR] Overdue tasks error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching overdue tasks: {str(e)}")


@app.get("/tasks/at-risk")
async def get_at_risk_tasks():
    """Get tasks at risk of missing deadlines (due within 2 days)"""
    
    if not notion_integration:
        raise HTTPException(status_code=500, detail="Notion not available")
    
    try:
        url = f"https://api.notion.com/v1/databases/{notion_integration.database_id}/query"
        response = requests.post(url, headers=notion_integration.headers, json={})
        
        if response.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to query Notion")
        
        data = response.json()
        tasks = data.get("results", [])
        
        from datetime import datetime, date, timedelta
        today = date.today()
        risk_threshold = today + timedelta(days=2)  # Next 2 days
        
        at_risk_tasks = []
        
        for t in tasks:
            props = t.get("properties", {})
            status = props.get("Status", {}).get("select", {}).get("name", "Unknown")
            
            # Only look at non-completed tasks
            if status == "Done":
                continue
            
            due_date_obj = props.get("Due Date", {}).get("date")
            due_date = due_date_obj.get("start") if due_date_obj else None
            
            if due_date:
                try:
                    due = datetime.strptime(due_date, "%Y-%m-%d").date()
                    
                    # Task is due soon (within 2 days) and not done
                    if today <= due <= risk_threshold:
                        days_until_due = (due - today).days
                        
                        title = props.get("Name", {}).get("title", [{}])[0].get("plain_text", "Untitled")
                        assignee_data = props.get("Assignee", {}).get("rich_text", [])
                        assignee = assignee_data[0].get("plain_text", "Unassigned") if assignee_data else "Unassigned"
                        priority = props.get("Priority", {}).get("select", {}).get("name", "Unknown")
                        
                        at_risk_tasks.append({
                            "title": title,
                            "assignee": assignee,
                            "priority": priority,
                            "due_date": due_date,
                            "days_until_due": days_until_due,
                            "status": status,
                            "url": t.get("url")
                        })
                except:
                    pass
        
        # Sort by urgency (soonest first)
        at_risk_tasks.sort(key=lambda x: x["days_until_due"])
        
        return {
            "total_at_risk": len(at_risk_tasks),
            "tasks": at_risk_tasks
        }
    
    except Exception as e:
        print(f"[ERROR] At-risk tasks error: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching at-risk tasks: {str(e)}")
    
@app.get("/reports/daily") 
async def generate_daily_report(): 
    """
        Generate daily progress report 
    """ 
    if not notion_integration: 
        raise HTTPException(status_code=500, detail="Notion not available") 
    try : 
        # Get dashboard data 
        dashboard = await get_dashboard() 
        overdue = await get_overdue_tasks()  
        at_risk = await get_at_risk_tasks() 
        
        from datetime import datetime 
        today = datetime.now().strftime("%A, %B %d, %Y") 
        
        # Build report 
        report_lines = [
            f"# Daily Project Report - {today}",
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
        # gropus by assignee 
        assignee_counts = {}
        for task in dashboard['tasks']:
            assignee = task['assignee']
            if task['status'] != "Done":
                assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
        
        for assignee, count in sorted(assignee_counts.items(), key=lambda x: x[1], reverse=True):
            report_lines.append(f"- **{assignee}**: {count} active tasks")
        
        # Join all lines
        report = "\n".join(report_lines)
        
        return { 
                "reported_date" : today, 
                "markdown" : report, 
                "summary" : dashboard['summary'], 
                "overdue_count" : overdue['total_overdue'], 
                "at_risk_count" : at_risk['total_at_risk']
            } 
    except Exception as e : 
        raise HTTPException(status_code = 500, details = f"Report generation failed: {str(e)}")
    
          
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)