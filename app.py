import base64
import html
import io
import os
import re
import sys
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

# ---------- Branding comes from intent.yaml ----------
cfg = yaml.safe_load(Path("intent.yaml").read_text(encoding="utf-8"))
ORG = cfg["org"]
BOT = cfg.get("bot", {})
BRAND = cfg.get("branding", {})
STARTERS = cfg.get("starters", {})

BOT_NAME = BOT.get("name", "Assistant")
TAGLINE = BOT.get("tagline", "Answers from your documents, with sources.")
ICON = BOT.get("icon", "💬")
PRIMARY = BRAND.get("primary_color", "#0f766e")

st.set_page_config(
    page_title=f"{BOT_NAME} for {ORG['name']}",
    page_icon=ICON,
    layout="centered",
    initial_sidebar_state="auto",
)


# ---------- Small helpers ----------
def _rgb(hex_color):
    h = hex_color.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def mix(c1, c2, t):
    a, b = _rgb(c1), _rgb(c2)
    return "#%02x%02x%02x" % tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def b64(data):
    return base64.b64encode(data).decode()


@st.cache_data(show_spinner=False)
def image_uri(path, max_px, kind, stamp):
    """Turns an image file into a small data URI. Returns an empty string if the file is missing."""
    p = Path(path)
    if not path or not p.is_file():
        return ""
    if p.suffix.lower() == ".svg":
        return "data:image/svg+xml;base64," + b64(p.read_bytes())
    from PIL import Image

    im = Image.open(p)
    im.thumbnail((max_px, max_px))
    buf = io.BytesIO()
    if kind == "photo":
        im.convert("RGB").save(buf, "JPEG", quality=72, optimize=True)
        mime = "image/jpeg"
    else:
        im.convert("RGBA").save(buf, "PNG", optimize=True)
        mime = "image/png"
    return f"data:{mime};base64,{b64(buf.getvalue())}"


def load_image(path, max_px, kind):
    p = Path(path) if path else None
    stamp = p.stat().st_mtime if (p and p.is_file()) else 0
    return image_uri(path or "", max_px, kind, stamp)


def hesc(text):
    return html.escape(str(text)).replace("$", "&#36;")


def clean(text):
    # Streamlit treats paired dollar signs as math, so escape them.
    return text.replace("$", "\\$")


def bot_mark(c1, c2):
    """Original bot logo. A chat bubble with a check mark, tinted with the org brand color."""
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">'
        '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
        f'<stop offset="0" stop-color="{c1}"/><stop offset="1" stop-color="{c2}"/>'
        "</linearGradient></defs>"
        '<rect width="48" height="48" rx="14" fill="url(#g)"/>'
        '<rect x="9" y="9" width="30" height="23" rx="7" fill="#fff"/>'
        '<path d="M17 31h8l-8 8z" fill="#fff"/>'
        f'<path d="M17 20.5l5 5 9-10" fill="none" stroke="{c1}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round"/>'
        "</svg>"
    )
    return "data:image/svg+xml;base64," + b64(svg.encode())


# ---------- Colors and images ----------
brand = PRIMARY
brand_dark = mix(PRIMARY, "#000000", 0.38)
brand_tint = mix(PRIMARY, "#ffffff", 0.93)

custom_bot_logo = load_image(BRAND.get("bot_logo", ""), 256, "logo")
mark_uri = custom_bot_logo or bot_mark(brand, brand_dark)
logo_uri = load_image(BRAND.get("logo", ""), 400, "logo")
bg_uri = load_image(BRAND.get("background", ""), 1400, "photo")
bg_pos = BRAND.get("background_position", "center 55%")

if bg_uri:
    hero_bg = (
        "linear-gradient(90deg, #ffffff 0%, #ffffff 32%, rgba(255,255,255,.66) 66%, rgba(255,255,255,.30) 100%), "
        f'url("{bg_uri}") {bg_pos} / cover no-repeat'
    )
else:
    hero_bg = f"linear-gradient(110deg, #ffffff 0%, {brand_tint} 100%)"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@500;600;700;800&display=swap');
:root {
  --brand: __BRAND__;
  --brand-dark: __DARK__;
  --brand-tint: __TINT__;
  --ink: #16191d;
  --muted: #5b6470;
  --line: #e4e7eb;
}
footer {visibility: hidden;}
[data-testid="stMainBlockContainer"], .block-container {max-width: 860px; padding-top: 1.5rem;}

.hero {
  display: flex; align-items: center; justify-content: space-between; gap: 18px;
  min-height: 144px; padding: 22px 26px; margin-bottom: 1.2rem;
  border: 1px solid var(--line); border-radius: 22px; overflow: hidden;
  background: __HERO_BG__;
}
.hero-left {display: flex; align-items: center; gap: 16px; min-width: 0;}
.hero .mark {width: 56px; height: 56px; border-radius: 16px; flex: none; box-shadow: 0 10px 20px -10px var(--brand);}
.bot-name {font-family: 'Manrope', 'Segoe UI', system-ui, sans-serif; font-weight: 800; font-size: 1.9rem; line-height: 1.05; letter-spacing: -0.02em; color: var(--ink);}
.bot-tag {margin-top: 6px; color: var(--muted); font-size: 0.93rem; max-width: 34ch; line-height: 1.35;}
.org-chip {
  display: flex; align-items: center; gap: 10px; padding: 8px 16px; border-radius: 999px;
  background: rgba(255,255,255,.84); border: 1px solid rgba(255,255,255,.95);
  backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px);
  font-family: 'Manrope', 'Segoe UI', system-ui, sans-serif; font-weight: 700; font-size: 0.95rem;
  color: var(--ink); white-space: nowrap;
}
.org-chip img {height: 26px; width: auto; display: block;}
@media (max-width: 640px) {
  .hero {flex-direction: column; align-items: flex-start; padding: 18px;}
  .bot-name {font-size: 1.55rem;}
  [data-testid="stMainBlockContainer"], .block-container {padding-top: 3.8rem;}
}

.empty-title {font-family: 'Manrope', 'Segoe UI', system-ui, sans-serif; font-weight: 700; font-size: 1.25rem; color: var(--ink); margin: 0.6rem 0 0.15rem;}
.empty-sub {color: var(--muted); font-size: 0.95rem; margin-bottom: 0.9rem;}

.st-key-suggestions [data-testid="stElementContainer"], .st-key-suggestions [data-testid="stButton"], .st-key-suggestions .stButton {width: 100% !important;}
.st-key-suggestions button {
  width: 100% !important; min-height: 66px; padding: 14px 16px; justify-content: flex-start;
  border: 1px solid var(--line); border-radius: 14px; background: #ffffff; color: var(--ink);
  font-weight: 500; transition: border-color .15s ease, background .15s ease;
}
.st-key-suggestions button:hover {border-color: var(--brand); background: var(--brand-tint); color: var(--ink);}
.st-key-suggestions button > div, .st-key-suggestions button p {width: 100%; text-align: left;}

.pill {display: inline-flex; align-items: center; gap: 7px; padding: 3px 12px 3px 10px; border-radius: 999px; font-size: 0.8rem; font-weight: 600; margin-bottom: 8px;}
.pill::before {content: ""; width: 7px; height: 7px; border-radius: 50%; background: currentColor;}
.pill-ok {background: #e7f5ec; color: #17653a;}
.pill-esc {background: #fff2d9; color: #8a5300;}

.handoff {border: 1px solid #f0d9a8; border-left: 4px solid #e0a030; background: #fffaf0; border-radius: 12px; padding: 14px 18px; color: #3d2b00; line-height: 1.55;}
.handoff .sec {margin-top: 10px; padding-top: 10px; border-top: 1px solid #f3dfb5; font-size: 0.9rem; line-height: 1.7;}

section[data-testid="stSidebar"] .stButton > button {width: 100%; text-align: left; justify-content: flex-start;}
</style>
"""

st.markdown(
    CSS.replace("__BRAND__", brand)
    .replace("__DARK__", brand_dark)
    .replace("__TINT__", brand_tint)
    .replace("__HERO_BG__", hero_bg),
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner="Loading the knowledge base...")
def load_agent():
    import graph

    return graph


try:
    agent = load_agent()
except Exception as e:
    st.error(f"Could not start the agent. Did you run python src/ingest.py first? Details {e}")
    st.stop()


def queue(q):
    st.session_state.pending = q


# ---------- Sidebar ----------
with st.sidebar:
    st.markdown(f"### {ORG['name']}")
    st.caption(ORG["business_case"])

    chunks = agent.CHUNKS
    n_docs = len({c["meta"]["source"] for c in chunks if c["meta"]["doc_type"] == "pdf"})
    n_tickets = sum(1 for c in chunks if c["meta"]["doc_type"] == "ticket")
    st.markdown("**Knowledge base**")
    st.write(f"{n_docs} PDF documents")
    st.write(f"{n_tickets} resolved tickets")

    with st.expander("Topics I can help with"):
        for t in cfg["in_scope"]:
            st.write("• " + t)

    with st.expander("Example questions"):
        st.caption("These should get an answer")
        for i, q in enumerate(STARTERS.get("ask", [])):
            st.button(q, key=f"side_ask_{i}", on_click=queue, args=(q,))
        st.caption("These should be passed to the team")
        for i, q in enumerate(STARTERS.get("handoff", [])):
            st.button(q, key=f"side_handoff_{i}", on_click=queue, args=(q,))

    st.divider()
    debug = st.toggle("Show how the agent decided", value=False)
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()
    st.caption(ORG.get("data_note", ""))


# ---------- Rendering ----------
def number_citations(text, sources):
    order = {s["id"]: i for i, s in enumerate(sources, 1)}

    def repl(m):
        ids = [x.strip() for x in m.group(1).split(",")]
        nums = [str(order[i]) for i in ids if i in order]
        return f"**[{', '.join(nums)}]**" if nums else m.group(0)

    return re.sub(r"\[([^\[\]]+)\]", repl, text)


def show_sources(sources):
    st.caption("Sources")
    for n, s in enumerate(sources, 1):
        if s["doc_type"] == "pdf":
            label = f"[{n}] {s['title']}, page {s['page']}"
        else:
            label = f"[{n}] {s['title']}"
        with st.expander(label):
            st.markdown(clean(s["text"]))


def show_escalation(r):
    h = r["handoff"]
    closest = ""
    if h.get("closest_document"):
        closest = f"<br><b>Closest document</b> {hesc(h['closest_document'])}"
    ref = f"<b>Reference</b> {hesc(h['reference'])}<br>" if h.get("reference") else ""
    card = (
        '<div class="handoff">'
        f"<div>{hesc(r['answer'])}</div>"
        '<div class="sec">'
        f"{ref}<b>Team</b> {hesc(h['team'])}<br>"
        f"<b>Email</b> {hesc(h['email'])}<br>"
        f"<b>Hours</b> {hesc(h['hours'])}"
        "</div>"
        '<div class="sec">'
        "<b>Summary for the team</b><br>"
        f"Question. {hesc(h['question'])}<br>"
        f"Why it was passed on. {hesc(h['reason'])}{closest}"
        "</div></div>"
    )
    st.markdown(card, unsafe_allow_html=True)


def show_debug(r):
    with st.expander("How the agent decided"):
        c1, c2, c3, c4 = st.columns(4)
        skipped = r.get("escalation_reason") == "out_of_scope"
        c1.metric("Best similarity", "Skipped" if skipped else f"{r['top_sim']:.3f}")
        c2.metric("Judge", r.get("judge_verdict", "Not needed"))
        verified = r.get("verified")
        c3.metric("Fact check", "Passed" if verified is True else ("Failed" if verified is False else "Not run"))
        c4.metric("Decision", r["decision"].title())
        if r.get("escalation_reason"):
            st.write(f"Escalation reason code. {r['escalation_reason']}")
        rows = [
            {
                "id": c["id"],
                "dense cosine": round(c["dense"], 3) if c.get("dense") is not None else None,
                "RRF score": c["rrf"],
            }
            for c in r.get("candidates", [])
        ]
        st.dataframe(rows, hide_index=True)
        st.caption(f"The full trace is in your LangSmith project {os.getenv('LANGSMITH_PROJECT', '')}.")


def show_result(r, debug_on):
    if r["decision"] == "answer":
        st.markdown('<span class="pill pill-ok">Answered from your documents</span>', unsafe_allow_html=True)
        st.markdown(clean(number_citations(r["answer"], r["sources"])))
        show_sources(r["sources"])
    else:
        st.markdown('<span class="pill pill-esc">Passed to the team</span>', unsafe_allow_html=True)
        show_escalation(r)
    if debug_on:
        show_debug(r)


# ---------- Header ----------
if logo_uri:
    org_html = f'<div class="org-chip"><img src="{logo_uri}" alt="{hesc(ORG["name"])}"></div>'
else:
    org_html = f'<div class="org-chip"><span>{hesc(ORG["name"])}</span></div>'

st.markdown(
    '<div class="hero"><div class="hero-left">'
    f'<img class="mark" src="{mark_uri}" alt="{hesc(BOT_NAME)}">'
    f'<div><div class="bot-name">{hesc(BOT_NAME)}</div><div class="bot-tag">{hesc(TAGLINE)}</div></div>'
    f"</div>{org_html}</div>",
    unsafe_allow_html=True,
)

# ---------- Chat ----------
if "messages" not in st.session_state:
    st.session_state.messages = []

typed = st.chat_input(f"Ask {BOT_NAME} a question")
question = st.session_state.pop("pending", None) or typed

if not st.session_state.messages and not question:
    st.markdown(
        '<div class="empty-title">What can I help you with?</div>'
        '<div class="empty-sub">Choose a question or type your own below.</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="suggestions"):
        cols = st.columns(2)
        for i, q in enumerate(STARTERS.get("ask", [])[:4]):
            cols[i % 2].button(q, key=f"chip_{i}", on_click=queue, args=(q,))

for m in st.session_state.messages:
    if m["role"] == "user":
        with st.chat_message("user", avatar=":material/person:"):
            st.markdown(clean(m["content"]))
    else:
        with st.chat_message("assistant", avatar=ICON):
            show_result(m["result"], debug)

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar=":material/person:"):
        st.markdown(clean(question))
    with st.chat_message("assistant", avatar=ICON):
        try:
            with st.spinner("Checking the documents..."):
                result = agent.ask(question)
        except Exception as e:
            st.session_state.messages.pop()
            st.error(f"Something went wrong while answering. Details {e}")
            st.stop()
        show_result(result, debug)
    st.session_state.messages.append({"role": "assistant", "result": result})
