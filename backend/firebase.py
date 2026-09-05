import json
import os
import sys

import firebase_admin
from dotenv import load_dotenv
from firebase_admin import auth as firebase_auth
from firebase_admin import credentials, firestore

load_dotenv()

service_account_env = os.environ.get("FIREBASE_SERVICE_ACCOUNT")

if service_account_env:
    try:
        cred = credentials.Certificate(json.loads(service_account_env))
        print("🔥 Firebase initialized via secure cloud environment variable.")
    except Exception as error:
        print(
            "CRITICAL: Failed to parse FIREBASE_SERVICE_ACCOUNT environment variable.",
            error,
        )
        sys.exit(1)
else:
    try:
        cred = credentials.Certificate("firebase-service-account.json")
        print("🔥 Firebase initialized via local service account file.")
    except Exception as error:
        print("CRITICAL: Local firebase-service-account.json not found.", error)
        sys.exit(1)

firebase_admin.initialize_app(cred)

db = firestore.client()
auth = firebase_auth
