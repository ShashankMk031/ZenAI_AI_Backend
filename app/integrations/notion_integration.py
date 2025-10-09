import os 
from notion_client import Client 
from typing import List, Dict, Optional 
from datetime import datetime 

class NotionIntegration: 
    def __init__(self):
        self.client = Client(auth = os.getenv("NOTION_API_Key ")) 
        self.database_id = os.getenv("NOTION_DATABASE_ID ") 
        print(f"[INFO] Notion integration initialized with database: {self.database_id}") 
        
    def create_task(
        self, 
        title: str, 
        description : str,  
        assignee : Optional[str] = None, 
        priority : str = "Medium" , 
        due_date : Optional[str] = None,
        meeting_date : Optional[str] = None ,
        source :str = "Meeting Analysis" 
    ) -> Dict:
        """Create a new task in the Notion database. """
        try: 
            # Build properties object 
            properties = { 
                    "Name": { 
                        title: [
                            {
                                "text": { 
                                    "content" : title 
                                }
                            }
                        ]
                }
            } 
            # Description is added only if it exits and is not empty 
            if description : 
                properties['Description'] = { 
                        "rich_text" : [ 
                            { 
                                "text" : { 
                                    "content" : description 
                                }
                            }
                        ]
                } 
                # Priority is added only if it exits and is not empty 
            if priority : 
                properties['Priority'] = { 
                        "select" : { 
                            "name" : str(priority) 
                        } 
                } 
                # Add status - default to "To Do" 
            properties['Status'] = { 
                    "select" : { 
                        "name" : "To Do" 
                    } 
            } 
            
            # Add source only if not empty 
            if source : 
                properties['Source'] = { 
                        "rich_text" : [
                            {
                            "text" : { 
                                "content" : source[:2000] 
                            }
                        }
                    ]
                } 
                
            # add assignee - if provided 
            if assignee : 
                properties['Assignee'] = { 
                        "rich_text" : [ 
                            { 
                                "text" : { 
                                    "content" : str(assignee)
                                }
                            }
                        ] 
                }
            # Add due date - if provided and shougle be in YYYY-MM-DD format
            if due_date :
                try : 
                    datatime.strptime(due_date, "%Y-%m-%d") 
                    properties["Due Date"] = { 
                            "date" : { 
                                "start" : due_date 
                            }
                    } 
                except ValueError :
                    print(f"[WARNING] Invalid due date format: {due_date}. Skipping" )
            
            # Add meeting date 
            if meeting_date: 
                try : 
                    datetime.strptime(meeting_date, "%Y-%m-%d") 
                    properties["Meeting Date"] = { 
                            "date" : { 
                                "start" : meeting_date 
                            }
                    } 
                except ValueError :
                    print(f"[WARNING] Invalid meeting date format: {meeting_date}. Skipping" )
            
            # Create the page in Notion 
            response = self.client.pages.create( 
                 parent = {"database_id" : self.database_id} , 
                 properties = properties
            ) 
            
            print(f"[INFO] Created Notion task: {title }") 
            return { 
                    "success" : True, 
                    'task_id' : response["id"], 
                    "url" : response['url'] 
                } 
        except Exception as e: 
            print(f"[ERROR] Failed to create Notion task: {e}") 
            return { 
                    "success" : False, 
                    "error" : str(e) 
                } 
    
    def create_tasks_from_meeting( 
            self, 
            action_items : List[Dict] , 
            meeting_summary : str, 
            meeting_date : Optional[str] = None 
        ) -> List[Dict]: 
        """Create multiple tasks from meeting action items. """ 
        results = [] 
        
        if not meeting_date : 
            meeting_date = datetime.now().strftime("%Y-%m-%d") 
        
        for item in action_items : 
            result = self.create_task(
                title = item.get("title", "Untitled Task"),
                description= item.get("description", ""), 
                assignee= item.get("assignee"),
                priority= item.get("priority", "Medium"),
                due_date= item.get("due_date"),
                meeting_date= meeting_date,
                source= f"Meeting : {meeting_summary[:100]}..." if meeting_summary else "Meeting Analysis"
            ) 
            results.append(result) 
        return results 