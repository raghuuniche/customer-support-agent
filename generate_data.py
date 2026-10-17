"""Generates synthetic Tesla style support data. All content is fictional."""
import json
import os
import random
import sqlite3
from pathlib import Path
from xml.sax.saxutils import escape

from dotenv import load_dotenv
from openai import OpenAI
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

load_dotenv()
client = OpenAI(
    base_url=os.getenv("NEBIUS_BASE_URL"),
    api_key=os.getenv("NEBIUS_API_KEY"),
)
MODEL = os.getenv("NEBIUS_CHAT_MODEL")

PDF_DIR = Path("data/pdfs")
DB_PATH = Path("data/tickets.db")
PDF_DIR.mkdir(parents=True, exist_ok=True)

MODELS = ["Model 3", "Model Y", "Model S", "Model X", "Cybertruck"]
CATEGORIES = ["Charging", "Tires and service", "Autopilot", "Warranty", "App and connectivity"]

# Topics kept out of the PDFs so the answers exist only in tickets.
AVOID = "the vehicle asleep error in the app, tire sensor relearn after a rotation, overnight range loss in winter, Sentry Mode drain, preconditioning"

DOCS = {
    "charging_basics": "Charging basics. Cover home charging, Supercharger use, a charge port that will not open, charging that stops early, setting a charge limit, and charging speed.",
    "tire_and_service_guide": "Tire care and service guide. Cover recommended tire pressure, rotation interval, how to schedule service in the app, mobile service, service center visits, and wiper and filter replacement.",
    "autopilot_faq": "Autopilot and driver assistance FAQ. Cover what Autopilot does, the driver supervision requirement, common warnings, camera cleaning, and known limits.",
    "warranty_summary": "Warranty summary. Cover the basic vehicle limited warranty, battery and drive unit warranty, what is not covered, and how to start a claim.",
    "app_and_connectivity": "Mobile app and connectivity help. Cover phone key setup, Bluetooth pairing, Wi-Fi and cellular connection, software updates, and Premium Connectivity.",
}

# Hand written tickets so we are sure some answers live only in ticket history.
SEED = [
    ("Model 3", "App and connectivity",
     "The app says my vehicle is asleep and will not unlock. What do I do?",
     "Wake the car by pressing the brake pedal or opening a door, wait 30 seconds, then retry in the app. If it still fails, sign out of the app, sign back in, and confirm Bluetooth is on. Book service only if it fails after both steps."),
    ("Model Y", "Tires and service",
     "Tire pressure warning came on right after my tire rotation. Is something wrong?",
     "This is common after a rotation because the sensors need to relearn their positions. Drive above 25 mph for 10 to 15 minutes and the warning should clear. If it stays on after two days, book a service visit for a sensor reset."),
    ("Model Y", "Charging",
     "My range drops a lot overnight in winter even when parked. Is the battery failing?",
     "Cold weather and Sentry Mode both cause overnight drain. Turn off Sentry Mode at home and use Scheduled Departure so the car preconditions while plugged in. Losing about 1 percent per day in the cold is normal."),
]


def ask_llm(prompt, max_tokens=3000):
    r = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=max_tokens,
    )
    return r.choices[0].message.content.strip()


def make_pdf(name, text):
    styles = getSampleStyleSheet()
    title = name.replace("_", " ").title()
    story = [Paragraph(escape(title), styles["Title"]), Spacer(1, 12)]
    for line in text.replace("**", "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("## "):
            story.append(Spacer(1, 8))
            story.append(Paragraph(escape(line[3:]), styles["Heading2"]))
        elif line.startswith("- "):
            story.append(Paragraph("&bull; " + escape(line[2:]), styles["BodyText"]))
        else:
            story.append(Paragraph(escape(line), styles["BodyText"]))
    SimpleDocTemplate(str(PDF_DIR / f"{name}.pdf"), pagesize=letter).build(story)


def build_pdfs():
    for name, topic in DOCS.items():
        print(f"Writing {name}.pdf ...")
        prompt = f"""Write a realistic owner support document for a fictional electric car company in the style of Tesla.
Subject. {topic}
Do not mention these topics. {AVOID}
Rules.
- 600 to 800 words.
- Start directly with the first section. No title line.
- Section headings are lines that begin with "## ".
- Use short numbered steps or lines starting with "- " where helpful.
- Include specific numbers such as times, distances and percentages where natural.
- Plain text only. No bold, no tables, no other markdown."""
        make_pdf(name, ask_llm(prompt))


def gen_tickets(category, n=20):
    prompt = f"""Create {n} realistic resolved customer support tickets for electric cars in the category "{category}".
Return only a JSON array. Each item has the keys "model", "question", "resolution".
"model" must be one of {MODELS}.
"question" is what the customer wrote, in one or two casual sentences.
"resolution" is what the support agent advised, in two or three sentences with concrete steps.
Do not write about these topics. {AVOID}
Do not wrap the JSON in markdown."""
    for attempt in range(3):
        raw = ask_llm(prompt, max_tokens=4000)
        try:
            data = json.loads(raw[raw.index("["): raw.rindex("]") + 1])
            return [t for t in data if {"model", "question", "resolution"} <= set(t)]
        except Exception:
            print(f"  retrying {category} (attempt {attempt + 1})")
    return []


def build_db():
    rows = []
    for cat in CATEGORIES:
        print(f"Generating tickets for {cat} ...")
        for t in gen_tickets(cat):
            rows.append((t["model"], cat, t["question"].strip(), t["resolution"].strip(), "resolved"))

    # Mark about one in seven as still open with no resolution.
    random.seed(7)
    for i in random.sample(range(len(rows)), k=max(1, len(rows) // 7)):
        m, c, q, _, _ = rows[i]
        rows[i] = (m, c, q, "", "open")

    for m, c, q, r in SEED:
        rows.append((m, c, q, r, "resolved"))

    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.execute(
        """CREATE TABLE tickets (
            ticket_id TEXT PRIMARY KEY, model TEXT, category TEXT,
            question TEXT, resolution TEXT, status TEXT)"""
    )
    con.executemany(
        "INSERT INTO tickets VALUES (?,?,?,?,?,?)",
        [(f"T-{1001 + i}", *row) for i, row in enumerate(rows)],
    )
    con.commit()
    print("Tickets by status", con.execute("SELECT status, COUNT(*) FROM tickets GROUP BY status").fetchall())
    con.close()


if __name__ == "__main__":
    build_pdfs()
    build_db()
    print("Done.")