#!/usr/bin/env python
"""Generate Pegasos Email Marketing user guide PDF."""
from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "Pegasos_Email_Marketing_Guide.pdf"


class GuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "Pegasos Email Marketing Software", align="R", new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")

    def section_title(self, title):
        self.ln(4)
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(30, 60, 120)
        self.multi_cell(self.epw, 8, title)
        self.ln(2)

    def sub_title(self, title):
        self.ln(2)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(40, 40, 40)
        self.multi_cell(self.epw, 7, title)
        self.ln(1)

    def body(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(self.epw, 5.5, text)
        self.ln(1)

    def bullet(self, text):
        self.set_font("Helvetica", "", 10)
        self.set_text_color(20, 20, 20)
        self.multi_cell(self.epw, 5.5, f"  - {text}")


def build_pdf():
    pdf = GuidePDF()
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(20, 40, 90)
    pdf.multi_cell(pdf.epw, 10, "Pegasos Email Marketing Software")
    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(60, 60, 60)
    pdf.multi_cell(pdf.epw, 7, "Testing, Sharing and Deployment Guide")
    pdf.ln(4)
    pdf.body(
        "This guide covers how to test the application locally, share it with remote "
        "testers using ngrok, and deploy to production on Hostinger VPS when ready."
    )

    pdf.section_title("1. Local setup (your PC)")
    pdf.body("Requirements: Python 3.12+, Node.js 18+, SendGrid API key.")
    pdf.sub_title("First-time install")
    pdf.bullet("Open PowerShell in the project folder")
    pdf.bullet("Run: scripts\\windows\\install.bat")
    pdf.bullet("Edit .env with EMAIL_ENCRYPTION_KEY, SENDGRID_API_KEY, and other settings")
    pdf.sub_title("Start the app")
    pdf.bullet("Run: scripts\\windows\\start.bat")
    pdf.bullet("Backend: http://localhost:8000")
    pdf.bullet("Frontend: http://localhost:3000")
    pdf.bullet("Register or log in, then configure Settings (SendGrid, from email, domain)")

    pdf.section_title("2. Remote testing with ngrok (no deploy)")
    pdf.body(
        "Use this when someone far away should test in their browser without installing "
        "anything. Your PC must stay on while they test."
    )
    pdf.sub_title("One-time ngrok setup")
    pdf.bullet("Sign up at https://ngrok.com and download ngrok for Windows")
    pdf.bullet("Run: ngrok config add-authtoken YOUR_NGROK_TOKEN")
    pdf.sub_title("Prepare .env for ngrok")
    pdf.body(
        "Add to .env:\n"
        "DEBUG=True\n"
        "ALLOWED_HOSTS=localhost,127.0.0.1,.ngrok-free.app,.ngrok.io\n"
        "SITE_URL=http://localhost:8000"
    )
    pdf.sub_title("Steps each time you share")
    pdf.bullet("Run scripts\\windows\\start.bat (wait for backend + frontend)")
    pdf.bullet("Run scripts\\windows\\ngrok-start.bat (opens tunnels for ports 8000 and 3000)")
    pdf.bullet("Copy the https URL from ngrok API window (port 8000)")
    pdf.bullet("Create email-marketing-frontend\\.env.local with:")
    pdf.body("REACT_APP_API_BASE_URL=https://YOUR-API-NGROK-URL/api")
    pdf.bullet("Restart frontend (Ctrl+C, then npm start in email-marketing-frontend)")
    pdf.bullet("Share the ngrok UI URL (port 3000) with your tester")
    pdf.body("Tester opens the link, registers, and tests. They may need to click ngrok Visit Site once.")

    pdf.section_title("3. Portable ZIP (tester installs on their PC)")
    pdf.bullet("Zip project excluding .venv, node_modules, db.sqlite3")
    pdf.bullet("Send .env secrets separately (never in public zip)")
    pdf.bullet("Tester installs Python 3.12+ and Node.js 18+")
    pdf.bullet("Tester runs install.bat then start.bat")
    pdf.bullet("Best when ngrok is not suitable or long independent testing is needed")

    pdf.section_title("4. Email deliverability checklist")
    pdf.bullet("SendGrid: verify domain (pegasos.in) and sender gunaseelan@pegasos.in")
    pdf.bullet("Hostinger DNS: SPF/DKIM via SendGrid domain auth; add DMARC TXT on _dmarc")
    pdf.bullet("Use Inbox Priority ON for personal-style plain text campaigns")
    pdf.bullet("Warm-up: send 50 emails/day (DAILY_CAMPAIGN_SEND_LIMIT in .env)")
    pdf.bullet("Primary inbox is not guaranteed for bulk cold email; Promotions/All Mail is still delivered")
    pdf.body(
        "Recommended .env values:\n"
        "GMAIL_SEND_DELAY_SECONDS=5\n"
        "GMAIL_SEND_DELAY_JITTER_SECONDS=3\n"
        "INBOX_PRIORITY_PLAIN_ONLY=True\n"
        "CAMPAIGN_WARMUP_ENABLED=True"
    )

    pdf.section_title("5. Deploy on Hostinger VPS (when ready)")
    pdf.bullet("Buy Hostinger VPS with Ubuntu 22.04 or 24.04 (Plain OS, not shared hosting)")
    pdf.bullet("Install Docker: curl -fsSL https://get.docker.com | sh")
    pdf.bullet("Upload project to /opt/email-marketing and create production .env")
    pdf.bullet("Run: docker compose up -d --build")
    pdf.bullet("Run: docker compose exec backend python manage.py createsuperuser")
    pdf.bullet("DNS in Hostinger: A records app and api pointing to VPS IP")
    pdf.bullet("HTTPS: use Caddy or nginx + Let's Encrypt")
    pdf.bullet("SendGrid webhook: https://api.pegasos.in/sendgrid/webhook/")
    pdf.body(
        "Production .env essentials:\n"
        "DEBUG=False\n"
        "SECRET_KEY=long-random-string\n"
        "ALLOWED_HOSTS=api.pegasos.in,app.pegasos.in\n"
        "CORS_ALLOWED_ORIGINS=https://app.pegasos.in\n"
        "SITE_URL=https://api.pegasos.in\n"
        "REACT_APP_API_BASE_URL=https://api.pegasos.in/api"
    )

    pdf.section_title("6. Troubleshooting")
    pdf.bullet("ngrok login fails remotely: set REACT_APP_API_BASE_URL in .env.local, restart frontend")
    pdf.bullet("Django 400 with ngrok: add .ngrok-free.app to ALLOWED_HOSTS")
    pdf.bullet("SendGrid 403 after ~80 sends: daily quota limit; wait or upgrade plan")
    pdf.bullet("Campaign delete error: fixed in latest code; restart backend")
    pdf.bullet("Emails in Promotions not spam: normal for bulk outreach; improve engagement over time")

    pdf.section_title("7. Security reminders")
    pdf.bullet("Never commit .env or share API keys publicly")
    pdf.bullet("Use a test SendGrid key for remote testers when possible")
    pdf.bullet("Rotate keys if accidentally exposed")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"PDF created: {path}")
