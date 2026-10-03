#!/usr/bin/env python
"""Generate Pegasos Email Marketing production deployment PDF."""
from pathlib import Path

from fpdf import FPDF

OUTPUT = Path(__file__).resolve().parent.parent / "docs" / "Pegasos_Production_Deployment_Guide.pdf"


class GuidePDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 8, "Pegasos Production Deployment Guide", align="R", new_x="LMARGIN", new_y="NEXT")
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

    def code_block(self, text):
        self.set_font("Courier", "", 9)
        self.set_fill_color(245, 245, 245)
        self.multi_cell(self.epw, 5, text, fill=True)
        self.ln(2)


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
    pdf.multi_cell(pdf.epw, 7, "Live Production Deployment Guide")
    pdf.ln(2)
    pdf.body(
        "Step-by-step guide to deploy on Hostinger VPS with domain pegasos.in. "
        "Includes costs, DNS, HTTPS, SendGrid, and production checklist."
    )

    pdf.section_title("Architecture")
    pdf.body(
        "https://app.pegasos.in  -> React UI (port 3000)\n"
        "https://api.pegasos.in  -> Django API (port 8000)\n"
        "PostgreSQL runs inside VPS via Docker\n"
        "SendGrid sends outbound email"
    )

    pdf.section_title("Part 1 - What you need to pay")
    pdf.sub_title("Required (must pay)")
    pdf.bullet("Hostinger VPS (Ubuntu, 2 GB RAM): about Rs 399-799/month")
    pdf.bullet("Domain pegasos.in: Rs 0 if you already own it; renewal about Rs 800-1500/year")
    pdf.bullet("SendGrid: free tier (about 100 emails/day) or paid plan for higher volume")
    pdf.body("Minimum monthly cost to go live: about Rs 500-900 (VPS + domain renewal amortized).")

    pdf.sub_title("Optional (not required to start)")
    pdf.bullet("SendGrid paid plan: about $15-20/month for more than 100 emails/day")
    pdf.bullet("Hostinger daily auto-backups: paid add-on")
    pdf.bullet("Malware scanner on VPS: often free")
    pdf.bullet("VPS upgrade to 4 GB RAM when traffic grows: +Rs 200-400/month")

    pdf.sub_title("Free (no payment)")
    pdf.bullet("Docker, PostgreSQL (in Docker), SSL/HTTPS (Caddy or Let's Encrypt)")
    pdf.bullet("SPF, DKIM, DMARC DNS records in Hostinger")
    pdf.bullet("Google Postmaster Tools")

    pdf.section_title("Part 2 - Before you start")
    pdf.bullet("Domain pegasos.in in Hostinger")
    pdf.bullet("SendGrid account with API key")
    pdf.bullet("SendGrid domain verified (e.g. em7844.pegasos.in)")
    pdf.bullet("Sender gunaseelan@pegasos.in verified in SendGrid")
    pdf.bullet("Project code ready on your PC")
    pdf.bullet("VPS purchased with Ubuntu 22.04 or 24.04 Plain OS")

    pdf.section_title("Part 3 - Step-by-step deployment")

    pdf.sub_title("Phase A - Create VPS (Hostinger)")
    pdf.bullet("hPanel -> VPS -> Set up VPS")
    pdf.bullet("Choose Plain OS -> Ubuntu 22.04 or 24.04")
    pdf.bullet("Set and save root password")
    pdf.bullet("Optional: enable Docker manager (free)")
    pdf.bullet("Skip daily auto-backups to save money (optional)")
    pdf.bullet("Copy VPS IP address when status is Running")

    pdf.sub_title("Phase B - Connect and install Docker")
    pdf.body("From your PC (PowerShell):")
    pdf.code_block("ssh root@YOUR_VPS_IP")
    pdf.body("On the VPS:")
    pdf.code_block(
        "apt update && apt upgrade -y\n"
        "curl -fsSL https://get.docker.com | sh\n"
        "apt install -y git"
    )

    pdf.sub_title("Phase C - Upload project")
    pdf.bullet("Git: cd /opt && git clone YOUR_REPO email-marketing")
    pdf.bullet("Or zip project (exclude .venv, node_modules, db.sqlite3) and upload to /opt/email-marketing")

    pdf.sub_title("Phase D - Production .env file")
    pdf.body("On VPS: nano /opt/email-marketing/.env")
    pdf.code_block(
        "SECRET_KEY=paste-long-random-string\n"
        "DEBUG=False\n"
        "ALLOWED_HOSTS=api.pegasos.in,app.pegasos.in,localhost\n"
        "CORS_ALLOWED_ORIGINS=https://app.pegasos.in\n"
        "SITE_URL=https://api.pegasos.in\n"
        "REACT_APP_API_BASE_URL=https://api.pegasos.in/api\n"
        "SECURE_SSL_REDIRECT=True\n"
        "SECURE_HSTS_SECONDS=31536000\n"
        "EMAIL_ENCRYPTION_KEY=your-existing-key\n"
        "SENDGRID_API_KEY=your-sendgrid-key\n"
        "CAMPAIGN_WARMUP_ENABLED=True\n"
        "DAILY_CAMPAIGN_SEND_LIMIT=50\n"
        "GMAIL_SEND_DELAY_SECONDS=5\n"
        "GMAIL_SEND_DELAY_JITTER_SECONDS=3\n"
        "INBOX_PRIORITY_PLAIN_ONLY=True"
    )
    pdf.body("Generate SECRET_KEY: python3 -c \"import secrets; print(secrets.token_urlsafe(64))\"")

    pdf.sub_title("Phase E - Start application")
    pdf.code_block(
        "cd /opt/email-marketing\n"
        "docker compose up -d --build\n"
        "docker compose ps\n"
        "docker compose exec backend python manage.py createsuperuser"
    )

    pdf.sub_title("Phase F - DNS in Hostinger")
    pdf.body("Domains -> pegasos.in -> DNS Zone. Add A records:")
    pdf.bullet("Name: app  ->  Points to: YOUR_VPS_IP")
    pdf.bullet("Name: api  ->  Points to: YOUR_VPS_IP")
    pdf.body("Wait 15-60 minutes for DNS propagation.")

    pdf.sub_title("Phase G - HTTPS with Caddy (free SSL)")
    pdf.code_block(
        "apt update && apt install -y caddy\n"
        "nano /etc/caddy/Caddyfile"
    )
    pdf.body("Paste into Caddyfile:")
    pdf.code_block(
        "app.pegasos.in {\n"
        "    reverse_proxy localhost:3000\n"
        "}\n"
        "\n"
        "api.pegasos.in {\n"
        "    reverse_proxy localhost:8000\n"
        "}"
    )
    pdf.code_block("systemctl reload caddy")
    pdf.body("Open https://app.pegasos.in in browser.")

    pdf.sub_title("Phase H - Email and SendGrid")
    pdf.bullet("Add DMARC TXT on _dmarc in Hostinger DNS if not done")
    pdf.bullet("SendGrid Event Webhook URL: https://api.pegasos.in/sendgrid/webhook/")
    pdf.bullet("Enable: delivered, bounce, open, click, spam, unsubscribe")
    pdf.bullet("In app Settings: SendGrid key, From gunaseelan@pegasos.in, domain pegasos.in")
    pdf.bullet("Click Check verification status and send test email")

    pdf.sub_title("Phase I - Firewall")
    pdf.bullet("Allow ports 22 (SSH), 80 (HTTP), 443 (HTTPS)")
    pdf.bullet("Do NOT expose port 5432 (database) publicly")

    pdf.sub_title("Phase J - Verify production")
    pdf.bullet("https://app.pegasos.in loads and login works")
    pdf.bullet("Settings test email delivers")
    pdf.bullet("Campaign send and analytics work")
    pdf.bullet("https://api.pegasos.in/admin/ accessible")

    pdf.section_title("Part 4 - Monthly cost summary")
    pdf.sub_title("Starter production")
    pdf.bullet("Hostinger VPS 2 GB: Rs 499-799/month")
    pdf.bullet("Domain pegasos.in: about Rs 70-125/month (yearly renewal amortized)")
    pdf.bullet("SendGrid free tier: Rs 0")
    pdf.bullet("SSL: Rs 0")
    pdf.body("Total: about Rs 500-900/month")

    pdf.sub_title("When you scale (100+ emails/day regularly)")
    pdf.bullet("SendGrid Essentials: about Rs 1200-1700/month")
    pdf.bullet("VPS upgrade 4 GB: +Rs 200-400/month")

    pdf.section_title("Part 5 - Maintenance")
    pdf.sub_title("Deploy updates")
    pdf.code_block(
        "cd /opt/email-marketing\n"
        "git pull\n"
        "docker compose up -d --build"
    )
    pdf.sub_title("View logs")
    pdf.code_block("docker compose logs -f backend")
    pdf.sub_title("Backup database")
    pdf.code_block(
        "docker compose exec db pg_dump -U email_user email_marketing > backup.sql"
    )

    pdf.section_title("Part 6 - Production checklist")
    pdf.bullet("VPS running Ubuntu + Docker")
    pdf.bullet(".env: DEBUG=False, SECRET_KEY, ALLOWED_HOSTS, CORS set")
    pdf.bullet("docker compose up -d --build completed")
    pdf.bullet("createsuperuser done")
    pdf.bullet("DNS: app and api point to VPS IP")
    pdf.bullet("Caddy HTTPS working")
    pdf.bullet("SendGrid domain and sender verified")
    pdf.bullet("DMARC TXT added")
    pdf.bullet("SendGrid webhook configured")
    pdf.bullet("Test email sent successfully")
    pdf.bullet("Firewall: only 22, 80, 443 open")

    pdf.section_title("Part 7 - Timeline")
    pdf.bullet("Day 1: Buy VPS, install Docker, deploy app, DNS, HTTPS")
    pdf.bullet("Day 1: Configure SendGrid and Settings, send test email")
    pdf.bullet("Day 2+: Send campaigns with warm-up (50 emails/day)")

    pdf.ln(4)
    pdf.body(
        "Summary: You must pay for VPS (about Rs 500/month). Domain renewal and SendGrid "
        "paid plan are the other main costs. SSL, Docker, PostgreSQL, and DNS are free."
    )

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(OUTPUT))
    return OUTPUT


if __name__ == "__main__":
    path = build_pdf()
    print(f"PDF created: {path}")
