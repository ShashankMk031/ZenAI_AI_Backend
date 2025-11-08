from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.future import select
from sqlalchemy.exc import SQLAlchemyError
from app.db.database import get_db
from app.db.models import Report
from app.utils.pdf_generator import generate_pdf
from app.utils.email_sender import send_email_with_attachment

router = APIRouter()


@router.get("/reports")
async def list_reports(db=Depends(get_db)):
    """
    Returns all AI-generated project reports stored in the database,
    sorted by most recent first.
    """
    try:
        result = await db.execute(select(Report).order_by(Report.created_at.desc()))
        reports = result.scalars().all()

        return [
            {
                "id": r.id,
                "user": r.user,
                "summary_text": r.summary_text,
                "report_markdown": r.report_markdown,
                "task_summary": r.task_summary,
                "created_at": r.created_at.isoformat(),
            }
            for r in reports
        ]

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch reports: {e}")


@router.post("/reports/{report_id}/email")
async def email_report(
    report_id: int,
    recipient: str = Query(..., description="Email address to send the report to"),
    db=Depends(get_db),
):
    """
    Generate a PDF for a specific report and email it to a recipient.
    """
    try:
        result = await db.execute(select(Report).where(Report.id == report_id))
        report = result.scalar_one_or_none()

        if not report:
            raise HTTPException(status_code=404, detail="Report not found")

        pdf_bytes = generate_pdf("ZenAI Project Report", report.report_markdown)

        email_body = (
            f"Hello,\n\nAttached is the latest ZenAI report for {report.user}.\n\n"
            f"Summary:\n{report.summary_text[:250]}...\n\n"
            "Best,\nZenAI Automated System"
        )

        success = await send_email_with_attachment(
            to_email=recipient,
            subject=f"ZenAI Report for {report.user}",
            body=email_body,
            pdf_bytes=pdf_bytes,
            filename=f"zenai_report_{report.id}.pdf",
        )

        if not success:
            raise HTTPException(status_code=500, detail="Failed to send email")

        return {
            "status": "Email sent successfully",
            "report_id": report.id,
            "recipient": recipient,
        }

    except SQLAlchemyError as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error sending email: {e}")
