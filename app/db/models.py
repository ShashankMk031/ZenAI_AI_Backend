from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, func
from app.db.database import Base


class Report(Base):
    """
    ORM model for storing ZenAI-generated project reports.
    Each record represents one summarized Notion project snapshot.
    """

    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    user = Column(String(100), nullable=False)
    summary_text = Column(Text, nullable=True)
    report_markdown = Column(Text, nullable=True)
    task_summary = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    def __repr__(self):
        return f"<Report id={self.id} user={self.user} created_at={self.created_at}>"
