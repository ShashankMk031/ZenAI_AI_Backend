import os
from groq import Groq


class GroqAgent:
    """
    Handles AI summarization and report generation using Groq's LLM API.
    Provides both single-shot and streaming modes for task summarization.
    """

    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("Missing GROQ_API_KEY in environment variables.")
        self.client = Groq(api_key=api_key)

    def summarize_tasks(self, tasks):
        """
        Summarizes a list of tasks into a concise, structured project report.
        Used for standard (non-streaming) API requests.
        """
        if not tasks:
            return "No tasks found in the Notion database."

        prompt = (
            "You are ZenAI, a project management assistant. "
            "Summarize the following Notion tasks into a professional, structured status report.\n\n"
            f"{tasks}\n\n"
            "Highlight task progress, blockers, upcoming goals, and next steps."
        )

        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[Groq Error] {e}")
            return "AI summarization failed. Please verify your Groq API credentials or network connection."

    def stream_summary(self, tasks):
        """
        Streams AI-generated summary tokens for real-time WebSocket output.
        Each yielded token can be sent progressively to the frontend.
        """
        if not tasks:
            yield "No tasks found in Notion database."
            return

        prompt = (
            "You are ZenAI, a project manager assistant. "
            "Generate a daily summary for these tasks:\n\n"
            f"{tasks}\n\n"
            "Respond in short, coherent sentences suitable for live display."
        )

        try:
            stream = self.client.chat.completions.create(
                model="llama-3.1-70b-versatile",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                stream=True,
            )

            for chunk in stream:
                token = chunk.choices[0].delta.content or ""
                if token:
                    yield token
        except Exception as e:
            yield f"[Stream Error] {e}"
