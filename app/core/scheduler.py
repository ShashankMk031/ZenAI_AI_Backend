import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime
from app.integrations.notion_integration import NotionIntegration
from app.agents.groq_agent import GroqAgent
from app.core.config import settings


async def run_scheduled_report():
    print(f"[{datetime.now()}] Running ZenAI Notion sync task...")
    try:
        notion = NotionIntegration()
        groq = GroqAgent()

        # Fetch all tasks
        tasks = notion.query_all_tasks()

        if not tasks:
            print("[Scheduler] No tasks found in Notion database.")
            return

        # Generate AI summary
        summary = groq.summarize_tasks(tasks)
        print("[Scheduler] ✅ Report generated successfully.")
        print(summary[:300] + "...")  # Print only first part for logs

    except Exception as e:
        print(f"[Scheduler Error] {e}")


def start_scheduler():
    """Starts the recurring Notion sync scheduler."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(run_scheduled_report, "interval", minutes=settings.AGENT_INTERVAL_MINUTES)
    scheduler.start()
    print(f"[Scheduler] ZenAI background task started — every {settings.AGENT_INTERVAL_MINUTES} minutes.")
