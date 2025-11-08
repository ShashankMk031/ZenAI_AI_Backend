from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.integrations.notion_integration import NotionIntegration
from app.agents.groq_agent import GroqAgent
from app.db.database import AsyncSessionLocal
from app.db.models import Report
import asyncio


router = APIRouter()


class ChatRequest(BaseModel):
    user: str
    message: str


@router.post("/report")
async def generate_report(req: ChatRequest):
    """
    Fetches project tasks from Notion and generates an AI summary using Groq.
    Returns a markdown report and structured task statistics.
    """
    try:
        notion = NotionIntegration()
        groq_agent = GroqAgent()

        # Step 1: Fetch tasks from Notion
        tasks = notion.query_all_tasks()
        if not tasks:
            return {
                "messages": [
                    {"role": "user", "text": req.message},
                    {
                        "role": "assistant",
                        "text": "No tasks found in your Notion workspace. Please verify your database ID or API key.",
                    },
                ],
                "report_markdown": "No task data available.",
                "summary": {"total_tasks": 0, "completed": 0, "in_progress": 0, "todo": 0},
            }

        # Step 2: Generate AI summary using Groq
        summary_text = groq_agent.summarize_tasks(tasks)

        # Step 3: Build markdown report
        report_markdown = (
            f"# Project Report\n"
            f"**User:** {req.user}\n\n"
            f"**AI Summary:**\n{summary_text}\n\n"
            f"**Task Breakdown (Top 10):**\n"
        )

        for task in tasks[:10]:
            title = task.get("title", "Untitled")
            status = task.get("status", "Unknown")
            assignee = task.get("assignee_name", "Unassigned")
            due_date = task.get("due_date", "No due date")
            report_markdown += f"- {title} — {status} — {assignee} — Due: {due_date}\n"

        # Step 4: Build task summary
        summary = {
            "total_tasks": len(tasks),
            "completed": sum(
                1 for t in tasks if t.get("status", "").lower() in ("done", "completed")
            ),
            "in_progress": sum(
                1 for t in tasks if t.get("status", "").lower() == "in progress"
            ),
            "todo": sum(
                1 for t in tasks if t.get("status", "").lower() in ("to do", "todo")
            ),
        }

        # Step 5: Construct response messages
        messages = [
            {"role": "user", "text": req.message},
            {
                "role": "assistant",
                "text": "ZenAI successfully generated your Notion project report.",
            },
        ]

        # Step 6: Save the generated report to the database
        async with AsyncSessionLocal() as db:
            new_report = Report(
                user=req.user,
                summary_text=summary_text,
                report_markdown=report_markdown,
                task_summary=summary,
            )
            db.add(new_report)
            await db.commit()

        # Step 7: Return response
        return {
            "messages": messages,
            "report_markdown": report_markdown,
            "summary": summary,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Report generation failed: {e}")


# Helper (optional)
async def simulate_ai_delay():
    await asyncio.sleep(1.0)
