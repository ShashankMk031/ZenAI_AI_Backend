from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from io import BytesIO

def generate_pdf(report_title: str, report_content: str) -> bytes:
    """Generate a simple PDF file in memory."""
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setTitle(report_title)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(50, height - 80, report_title)

    pdf.setFont("Helvetica", 11)
    y = height - 120
    for line in report_content.split("\n"):
        if y < 60:
            pdf.showPage()
            y = height - 60
            pdf.setFont("Helvetica", 11)
        pdf.drawString(50, y, line[:110])
        y -= 18

    pdf.save()
    buffer.seek(0)
    return buffer.getvalue()
