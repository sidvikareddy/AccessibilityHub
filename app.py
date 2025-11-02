import os
import uuid
from flask import Flask, request, jsonify
from dotenv import load_dotenv
from firebase_setup import init_firebase
from helpers import extract_text_from_pdf, extract_text_from_docx
from firebase_admin import storage as fb_storage
from google.cloud import vision, texttospeech
load_dotenv()
app = Flask(__name__)

# ✅ Use correct environment variable name
PROJECT_ID = os.getenv("FIREBASE_PROJECT_ID")

# Initialize Firebase
BUCKET, DB = init_firebase(project_id=PROJECT_ID)

# Initialize Google Cloud clients
vision_client = vision.ImageAnnotatorClient()
tts_client = texttospeech.TextToSpeechClient()


def upload_file_to_firebase(path, blob_path, content_type=None):
    """Uploads a file to Firebase Storage and returns the public URL."""
    bucket = fb_storage.bucket()
    blob = bucket.blob(blob_path)
    blob.upload_from_filename(path, content_type=content_type)
    blob.make_public()
    return blob.public_url


@app.route('/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'error': 'no file'}), 400

    f = request.files['file']
    filename = f.filename

    if not filename:
        return jsonify({'error': 'file has no filename'}), 400

    ext = filename.split('.')[-1].lower()
    tmp = f"/tmp/{uuid.uuid4().hex}_{filename}"
    f.save(tmp)

    text = ""
    if ext == 'pdf':
        text = extract_text_from_pdf(tmp)
    elif ext in ('docx', 'doc'):
        text = extract_text_from_docx(tmp)

    blob_path = f"uploads/{uuid.uuid4().hex}/{filename}"
    public_url = upload_file_to_firebase(tmp, blob_path, content_type=f.mimetype)

    # Save metadata in Firestore
    doc = DB.collection('documents').document()
    doc.set({
        "title": filename,
        "storage_path": blob_path,
        "public_url": public_url,
        "extracted_snippet": text[:300]
    })

    return jsonify({
        "id": doc.id,
        "url": public_url,
        "text_len": len(text)
    })


@app.route('/generate-alt-text', methods=['POST'])
def alt_text():
    if 'file' in request.files:
        image = vision.Image(content=request.files['file'].read())
    else:
        data = request.get_json() or {}
        if not data.get('image_url'):
            return jsonify({'error': 'provide image_url or file'}), 400
        image = vision.Image()
        image.source.image_uri = data['image_url']

    response = vision_client.annotate_image({
        'image': image,
        'features': [{'type': vision.Feature.Type.LABEL_DETECTION}]
    })
    labels = [l.description for l in response.label_annotations[:5]]

    return jsonify({"alt_text": "Image of: " + ", ".join(labels)})


@app.route('/generate-tts', methods=['POST'])
def tts():
    data = request.get_json() or {}
    text = data.get('text')
    if not text:
        return jsonify({'error': 'text required'}), 400

    input_text = texttospeech.SynthesisInput(text=text[:5000])
    voice = texttospeech.VoiceSelectionParams(language_code="en-US")
    audio_config = texttospeech.AudioConfig(audio_encoding=texttospeech.AudioEncoding.MP3)
    response = tts_client.synthesize_speech(
        input=input_text, voice=voice, audio_config=audio_config
    )

    blob_path = f"tts/{uuid.uuid4().hex}.mp3"
    bucket = fb_storage.bucket()
    blob = bucket.blob(blob_path)
    blob.upload_from_string(response.audio_content, content_type='audio/mpeg')
    blob.make_public()

    return jsonify({"tts_url": blob.public_url})
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)