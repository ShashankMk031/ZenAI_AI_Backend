import os
import httpx
from app.core.config import settings


class NotionIntegration:
    """
    Handles communication with the Notion API for reading project tasks.
    """

    BASE_URL = "https://api.notion.com/v1/databases"

    def __init__(self):
        self.api_key = settings.NOTION_API_KEY
        self.database_id = settings.NOTION_DATABASE_ID
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Notion-Version": "2022-06-28",
            "Content-Type": "application/json",
        }

    def query_all_tasks(self):
        """
        Fetches all task entries from the configured Notion database.
        """
        url = f"{self.BASE_URL}/{self.database_id}/query"
        try:
            with httpx.Client(timeout=20) as client:
                response = client.post(url, headers=self.headers)
                response.raise_for_status()
                data = response.json()
                return self._parse_tasks(data)
        except httpx.RequestError as e:
            print(f"[Notion Network Error] {e}")
            return []
        except Exception as e:
            print(f"[Notion Error] {e}")
            return []

    def _parse_tasks(self, data):
        """
        Extracts and structures task information from Notion response data.
        """
        tasks = []
        for item in data.get("results", []):
            props = item.get("properties", {})

            title = (
                props.get("Name", {})
                .get("title", [{}])[0]
                .get("plain_text", "Untitled Task")
            )

            status = (
                props.get("Status", {})
                .get("status", {})
                .get("name", "Unknown")
            )

            assignee_name = (
                props.get("Assignee", {})
                .get("people", [{}])[0]
                .get("name", "Unassigned")
            )

            due_date = (
                props.get("Due", {})
                .get("date", {})
                .get("start", "No due date")
            )

            tasks.append(
                {
                    "title": title,
                    "status": status,
                    "assignee_name": assignee_name,
                    "due_date": due_date,
                }
            )

        return tasks
