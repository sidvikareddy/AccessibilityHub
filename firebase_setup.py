import os
import firebase_admin
from firebase_admin import credentials, storage, firestore

def init_firebase(service_account_path=None, project_id=None):
    if service_account_path is None:
        service_account_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if project_id is None:
        project_id = os.getenv("accessibility-platform")

    cred = credentials.Certificate(service_account_path)
    firebase_admin.initialize_app(cred, {
        'storageBucket': f"{project_id}.appspot.com"
    })
    bucket = storage.bucket()
    db = firestore.client()
    return bucket, db
