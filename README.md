# Customer Support Agent

A support chatbot that answers customer questions from your own documents and ticket history. Every answer shows which document each fact came from. When the bot is not confident, or the topic is out of scope, it hands the question to a human and records the handoff.

This is a learning project and a starting point. It is not a finished product. See Known limits at the end.

## What it does

- Reads PDF manuals and FAQs, and a database of resolved support tickets.
- Answers in plain language and cites its sources.
- Checks its own draft against the cited sources before replying.
- Hands the question to a human when it cannot answer, and saves a record with a reference number.
- Reads the organization's context, tone, scope and branding from one file called intent.yaml.

The included demo uses fictional Tesla owner support content.

## How it works

Ingest runs once, and again whenever your data changes.

```
PDFs and resolved tickets -> split into chunks -> embed -> Pinecone
                                              \-> saved locally for keyword search
```

Each customer question goes through these steps.

```
1. Scope check      Reads only the question. Out of scope topics go straight to a human.
2. Hybrid search    Vector search and BM25 keyword search, merged with Reciprocal Rank Fusion.
3. Confidence       The best cosine score decides. Borderline scores go to a YES or NO judge.
4. Answer           Written from the retrieved documents, with numbered citations.
5. Fact check       A second call confirms every claim appears in the cited documents.
6. Reply or handoff The customer gets a cited answer, or a handoff with a reference number.
```

Every step is traced in LangSmith.

## Services you need

| Service | Used for |
|---|---|
| Nebius | The chat model and the embedding model, through an OpenAI compatible API |
| Pinecone | Storing the vectors |
| LangSmith | Tracing every question. Optional but strongly recommended. |
| Tavily | Not used in this version. The key is optional. |

## Setup

You need Python 3.10 or newer.

**1. Create a virtual environment and install packages.**

Windows PowerShell

```
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

macOS or Linux

```
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

If PowerShell blocks the activation, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once and try again.

If a fresh install behaves differently from the original, install from `requirements.lock.txt` instead. It lists the exact versions that were tested.

**2. Create your .env file.**

Windows

```
Copy-Item .env.example .env
```

macOS or Linux

```
cp .env.example .env
```

Open `.env` and add your keys. Do not use quotes or spaces around the equals sign. Never commit this file.

**3. Choose your models.**

Leave the two model lines empty for now and run this.

```
python check_setup.py
```

It prints the models your Nebius account offers. Pick one instruction tuned chat model and one embedding model. Paste their exact names into `NEBIUS_CHAT_MODEL` and `NEBIUS_EMBED_MODEL`. Run the script again until every line says OK.

**4. A note on the embedding model.**

The Pinecone index is created automatically with the vector size of your embedding model. If you switch embedding models later, delete the index in Pinecone, or use a new name in `PINECONE_INDEX`, and run ingest again. A size mismatch is the most common setup error.

## Try the demo

```
python generate_data.py
python src/ingest.py
streamlit run app.py
```

`generate_data.py` asks the chat model to write five synthetic PDFs and about 100 tickets. The content is fictional and is not official guidance from any company.

It rebuilds `data/tickets.db` every time it runs. Do not run it again once you have added real tickets or resolved escalations.

## Use it for your organization

1. Put your PDFs in `data/pdfs`.
2. Provide resolved tickets as a SQLite file at `data/tickets.db`. It needs a table called `tickets` with these columns.

   ```
   ticket_id, model, category, question, resolution, status
   ```

   Only rows with status `resolved` are used. The file path and table name live in `intent.yaml`.
3. Edit `intent.yaml`. The table below explains each section.
4. Optional. Add images to the `assets` folder and point to them under `branding`.
5. Run `python src/ingest.py`, then `streamlit run app.py`.
6. Write at least 15 of your own questions in `tests/questions.csv` and run the scorecard.

### What intent.yaml controls

| Section | What it does |
|---|---|
| org | Organization name, business case and a note shown in the sidebar |
| bot | The assistant's name, tagline and emoji icon |
| branding | Brand color, optional logo, optional background photo and its position |
| starters | Example questions shown on the home screen and in the sidebar |
| tone | How the assistant should sound |
| in_scope | Topics the assistant helps with |
| out_of_scope | Topics it must hand off. See the warning below. |
| escalation | Team name, email, hours and the message shown on a handoff |
| sources | Where the PDFs and the ticket database are |
| retrieval | Chunk size, number of chunks, and the two confidence thresholds |

**Write out of scope topics precisely.** The scope check reads each line literally. In testing, "Pricing and financing" did not stop questions about service costs. A longer line that named prices, fees and costs of any product, service or subscription did. Test your wording with real questions.

**The confidence thresholds are starting values.** The numbers 0.55 and 0.35 depend on the embedding model. Calibrate them on your own data with the scorecard.

### Branding

Put a photo at `assets/org_background.jpg` and set the path under `branding`. It appears softly behind the header. A logo at `assets/org_logo.png` replaces the organization name chip. The bot mark takes its color from `primary_color`. For the page chrome to match, set the same color as `primaryColor` in `.streamlit/config.toml`. Use brand assets you have permission to use.

## Running

```
streamlit run app.py
```

Branding changes in `intent.yaml` appear when you reload the page. Search, scope and prompt settings load at startup, so restart the app after changing them or after running ingest.

A terminal version is also available.

```
python src/chat.py
```

## Handoffs and the learning loop

Every handoff is saved in `data/escalations.db` with a reference such as E-0001. The customer sees the reference on screen. Handoffs made while running the scorecard are not saved.

```
python src/escalations.py list
python src/escalations.py show E-0001
python src/escalations.py resolve E-0001 "What the human told the customer" "Category"
```

The `resolve` command records the human answer as a new resolved ticket. After that, run `python src/ingest.py` and restart the app. The bot can then answer the same question itself and cite the new ticket.

Treat the resolve step as a review. Anything saved there becomes searchable by every future customer, so remove personal details first.

## Testing

```
python src/evaluate.py
```

The scorecard runs every question in `tests/questions.csv` and writes `tests/results.csv`. Each row has these columns.

| Column | Meaning |
|---|---|
| expected_decision | `answer`, `escalate`, `either` or `safe` |
| expected_source | The file name or ticket id the answer must cite |
| must_not_contain | Text separated by pipes that must never appear in a reply |

`either` rows are marked for manual review. `safe` rows pass when nothing from `must_not_contain` leaks, whatever the decision.

Include questions that reach each layer. Questions about out of scope topics test the scope check. On topic questions that your documents do not answer test the confidence check and the judge. Prompt injection attempts test the leak check.

Passing 15 questions is a smoke test, not a quality score. Add questions from real conversations, keep some aside that you never tune on, and rerun everything after any change to the model, prompts, chunking, thresholds or documents.

## Project layout

```
support-agent/
  README.md
  intent.yaml          Everything specific to the organization
  .env.example         Template for your keys
  requirements.txt
  check_setup.py       Tests keys and lists models
  generate_data.py     Writes the synthetic demo data
  app.py               The Streamlit page
  assets/              Optional logo and background photo
  data/pdfs/           Your PDFs
  data/tickets.db      Your resolved tickets
  src/common.py        Shared helpers
  src/ingest.py        Parse, chunk, embed and store
  src/graph.py         The LangGraph flow
  src/escalations.py   Handoff records and the resolve command
  src/evaluate.py      The scorecard
  src/chat.py          Terminal chat
  src/peek.py          Shows vector and keyword results side by side
  tests/questions.csv  Your test questions
  .streamlit/config.toml  Theme settings
```

## Known limits

- It treats every question on its own. A follow up such as "and for the Model S?" will not work.
- Chunks are cut page by page, so a section that crosses a page break can be split.
- The same model writes and checks answers. A model grading its own work leans toward approving it.
- The fact check can reject good answers or miss subtle overreach. Calibrate it on a larger set.
- The scope check depends on the exact wording of the out of scope list.
- Results can vary slightly between runs, even at temperature zero.
- Handoff records contain customer text that may include personal data. Add redaction and retention rules before real use.
- There is no login, rate limiting or CRM connection. The escalations table is where an integration would plug in.
- Prices and other fast changing facts should come from a live system, not from documents.

## Troubleshooting

| Problem | What to try |
|---|---|
| A file is not found although it exists | Windows may hide extensions. Turn on file name extensions in File Explorer and check for `.txt.txt` or `.env.txt`. |
| Keys are not picked up | The file must be named exactly `.env`, saved, and in the project folder. Run commands from that folder. |
| The app says it could not start the agent | Run `python src/ingest.py` first. |
| Answers do not reflect new data | Restart the app after running ingest. |
| Pinecone reports a dimension mismatch | The embedding model changed. See the note on the embedding model. |
| A tool fails with a model not found error | Run `python check_setup.py` and choose a model from the current list. |
