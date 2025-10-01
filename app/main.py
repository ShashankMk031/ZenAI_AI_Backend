from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import tempfile
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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

@app.get("/")
async def root():
    return {
        "message": "AI Project Manager Agent is running!", 
        "groq_status": "connected" if llm else "failed",
        "audio_status": "enabled" if audio_processor else "disabled"
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)