# Student Helper API (Flask + MongoDB + Gemini)

Flask backend for a student assistant: store notes, summarize/explain text, summarize YouTube videos via transcripts, and answer queries using Gemini. Files are stored locally; note metadata lives in MongoDB.

Structure:
- `app.py` Flask app (MongoDB + Gemini) with `/` rendering `templates/index.html`
- `templates/` landing page template
- `static/style.css` and `static/script.js` assets
- `uploads/` created at runtime for uploaded files

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env   # set MONGO_URI, MONGO_DB, GEMINI_API_KEY
```

## Environment

- `MONGO_URI` (required) e.g., `mongodb://localhost:27017`
- `MONGO_DB` (default `b60`)
- `GEMINI_API_KEY` (required)
- `GEMINI_MODEL` (optional, default `gemini-1.5-flash`)
- `FLASK_RUN_HOST`/`FLASK_RUN_PORT` optional

## Run

```powershell
python app.py
```

## API

- `POST /api/notes` — form-data `file` (pdf/doc/docx) or JSON `{ "title", "content" }`; stores note in MongoDB; returns `id` and snippet.
- `POST /api/notes/<id>/explain` — summarizes a stored note via Gemini.
- `POST /api/explain-text` — JSON `{ "text" }`; returns Gemini summary.
- `POST /api/youtube-explain` — JSON `{ "url" }`; fetches transcript (if available) and summarizes.
- `POST /api/chat` — JSON `{ "query", "context"? }`; general Q&A via Gemini.
- `GET /files/<path>` — serves uploaded files.

## Notes

- Ensure MongoDB is running and accessible at `MONGO_URI`.
- YouTube summaries need public transcripts; otherwise the API returns an error.
