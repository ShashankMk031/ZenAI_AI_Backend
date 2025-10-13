import os
import requests
from typing import List, Dict, Optional
from datetime import datetime
from dotenv import load_dotenv

class NotionIntegration:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        self.api_key = os.getenv("NOTION_API_KEY")
        self.database_id = os.getenv("NOTION_DATABASE_ID")
        
        print(f"[DEBUG] API Key loaded: {self.api_key[:15] if self.api_key else 'None'}...")
        print(f"[DEBUG] Database ID: {self.database_id}")
        
        if not self.api_key:
            raise Exception("NOTION_API_KEY not found")
        
        if not self.database_id:
            raise Exception("NOTION_DATABASE_ID not found")
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28"
        }
        
        print(f"[INFO] Notion integration initialized with database: {self.database_id}")
    
    def create_task(
        self,
        title: str,
        description: str,
        assignee: Optional[str] = None,
        priority: str = "Medium",
        due_date: Optional[str] = None,
        meeting_date: Optional[str] = None,
        source: str = "AI Meeting Analysis"
    ) -> Dict:
        """
        Create a new task in Notion database using direct HTTP
        """
        try:
            # Build properties
            properties = {
                "Name": {
                    "title": [
                        {
                            "text": {
                                "content": title
                            }
                        }
                    ]
                }
            }
            
            # Add Description
            if description:
                properties["Description"] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": description[:2000]
                            }
                        }
                    ]
                }
            
            # Add Priority
            if priority:
                properties["Priority"] = {
                    "select": {
                        "name": str(priority)
                    }
                }
            
            # Add Status
            properties["Status"] = {
                "select": {
                    "name": "To Do"
                }
            }
            
            # Add Source
            if source:
                properties["Source"] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": source[:2000]
                            }
                        }
                    ]
                }
            
            # Add Assignee
            if assignee:
                properties["Assignee"] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": str(assignee)
                            }
                        }
                    ]
                }
            
            # Add Due Date
            if due_date:
                try:
                    datetime.strptime(due_date, "%Y-%m-%d")
                    properties["Due Date"] = {
                        "date": {
                            "start": due_date
                        }
                    }
                except ValueError:
                    print(f"[WARNING] Invalid due_date format: {due_date}, skipping")
            
            # Add Meeting Date
            if meeting_date:
                try:
                    datetime.strptime(meeting_date, "%Y-%m-%d")
                    properties["Meeting Date"] = {
                        "date": {
                            "start": meeting_date
                        }
                    }
                except ValueError:
                    print(f"[WARNING] Invalid meeting_date format: {meeting_date}, skipping")
            
            # Create page via API
            url = "https://api.notion.com/v1/pages"
            payload = {
                "parent": {"database_id": self.database_id},
                "properties": properties
            }
            
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                print(f"[INFO] Created Notion task: {title}")
                return {
                    "success": True,
                    "task_id": data["id"],
                    "url": data["url"]
                }
            else:
                error_msg = response.json().get("message", response.text)
                print(f"[ERROR] Failed to create task: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
        
        except Exception as e:
            print(f"[ERROR] Failed to create Notion task: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def create_tasks_from_meeting(
        self,
        action_items: List[Dict],
        meeting_summary: str,
        meeting_date: Optional[str] = None
    ) -> List[Dict]:
        """
        Create multiple tasks from a meeting analysis
        """
        results = []
        
        if not meeting_date:
            meeting_date = datetime.now().strftime("%Y-%m-%d")
        
        for item in action_items:
            result = self.create_task(
                title=item.get("title", "Untitled Task"),
                description=item.get("description", ""),
                assignee=item.get("assignee"),
                priority=item.get("priority", "Medium"),
                due_date=item.get("due_date"),
                meeting_date=meeting_date,
                source=f"Meeting: {meeting_summary[:50]}..." if meeting_summary else "AI Meeting Analysis"
            )
            results.append(result)
        
        return results