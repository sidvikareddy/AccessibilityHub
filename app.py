import os
import re
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, render_template
from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId
from helpers import extract_text_from_pdf, extract_text_from_docx
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
import google.generativeai as genai

load_dotenv()
app = Flask(__name__)

# Paths for local storage
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "b60")
if not MONGO_URI:
    raise RuntimeError("MONGO_URI is required (e.g., mongodb://localhost:27017)")

mongo_client = MongoClient(MONGO_URI)
db = mongo_client[MONGO_DB]
documents = db["documents"]

# Gemini setup
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is required for Gemini responses")
genai.configure(api_key=GEMINI_API_KEY)
gemini_model = genai.GenerativeModel(GEMINI_MODEL)


def run_gemini(prompt: str) -> str:
    """Generate text from Gemini model and return plain text."""
    resp = gemini_model.generate_content(prompt)
    return resp.text.strip() if resp and resp.text else ""


def summarize_text(text: str, context_note: str = "") -> str:
    prompt = (
        "You are a concise study assistant. Summarize the content clearly and list 3-5 key points.\n"
        f"Context: {context_note}\n\n"
        f"Content:\n{text}\n"
    )
    return run_gemini(prompt)


def extract_video_id(url: str) -> str | None:
    match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
    return match.group(1) if match else None


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/notes', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'provide file or JSON body'}), 400

    text = ""
    title = None
    if 'file' in request.files:
        f = request.files['file']
        filename = f.filename
        if not filename:
            return jsonify({'error': 'file has no filename'}), 400
        ext = filename.split('.')[-1].lower()
        tmp = UPLOAD_DIR / f"{uuid.uuid4().hex}_{filename}"
        f.save(tmp)
        title = filename
        if ext == 'pdf':
            text = extract_text_from_pdf(tmp)
        elif ext in ('docx', 'doc'):
            text = extract_text_from_docx(tmp)
        relative_path = tmp.relative_to(BASE_DIR)
        file_url = request.host_url.rstrip('/') + "/files/" + str(relative_path).replace('\\', '/')
    else:
        data = request.get_json() or {}
        text = data.get('content', '')
        title = data.get('title', 'Note')
        file_url = None

    doc = {
        "title": title or 'Note',
        "content": text,
        "public_url": file_url,
        "snippet": (text or '')[:500],
    }
    result = documents.insert_one(doc)
    return jsonify({"id": str(result.inserted_id), "snippet": doc["snippet"]})


@app.route('/api/notes/<note_id>/explain', methods=['POST'])
def explain_note(note_id):
    try:
        note = documents.find_one({"_id": ObjectId(note_id)})
    except Exception:
        note = None
    if not note:
        return jsonify({"error": "note not found"}), 404
    text = note.get("content") or note.get("snippet") or ""
    if not text:
        return jsonify({"error": "note has no content"}), 400
    summary = summarize_text(text, context_note=note.get("title", ""))
    return jsonify({"summary": summary})


@app.route('/api/explain-text', methods=['POST'])
def explain_text():
    data = request.get_json() or {}
    text = data.get('text', '')
    if not text:
        return jsonify({'error': 'text is required'}), 400
    summary = summarize_text(text)
    return jsonify({"summary": summary})


@app.route('/api/youtube-explain', methods=['POST'])
def youtube_explain():
    data = request.get_json() or {}
    url = data.get('url')
    if not url:
        return jsonify({'error': 'url is required'}), 400
    video_id = extract_video_id(url)
    if not video_id:
        return jsonify({'error': 'could not parse video id'}), 400
    try:
        transcript = YouTubeTranscriptApi.get_transcript(video_id, languages=['en'])
    except (TranscriptsDisabled, NoTranscriptFound):
        return jsonify({'error': 'no transcript available for this video'}), 400
    except Exception as e:
        return jsonify({'error': f'transcript fetch failed: {e}'}), 500

    text = " ".join([t['text'] for t in transcript])
    text = text[:8000]  # trim to keep prompt manageable
    prompt = (
        "Summarize this YouTube transcript and list key takeaways in bullets."
        " Keep it concise and student-friendly.\n\nTranscript:\n" + text
    )
    summary = run_gemini(prompt)
    return jsonify({"summary": summary})


@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json() or {}
    query = data.get('query')
    context = data.get('context', '')
    if not query:
        return jsonify({'error': 'query is required'}), 400
    prompt = (
        "You are a helpful study assistant. Answer clearly and concisely."
        f"\nContext: {context}\n\nQuestion: {query}"
    )
    answer = run_gemini(prompt)
    return jsonify({"answer": answer})


@app.route('/files/<path:filepath>')
def serve_file(filepath):
    # Serve files from uploads/ directory
    target = BASE_DIR / filepath
    if not target.exists():
        return jsonify({"error": "file not found"}), 404
    if target.is_dir():
        return jsonify({"error": "cannot serve directory"}), 400
    return send_from_directory(BASE_DIR, filepath)
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)