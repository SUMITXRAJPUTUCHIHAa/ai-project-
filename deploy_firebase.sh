#!/usr/bin/env bash
# Deploy: Cloud Run (API + UI + AI Engine) behind Firebase Hosting with Firestore rules & indexes.
# Prereqs: gcloud + firebase CLIs logged in, billing enabled.
set -euo pipefail

PROJECT_ID="${1:-${PROJECT_ID:-}}"
REGION="${REGION:-asia-south1}"
SERVICE="lpu-admission-intelligence"
if [ -z "$PROJECT_ID" ]; then
    echo "Usage: ./deploy_firebase.sh <firebase-project-id>"
    echo "Example: ./deploy_firebase.sh my-lpu-admissions-app"
    exit 1
fi

echo "==> Configuring Google Cloud project: $PROJECT_ID"
gcloud config set project "$PROJECT_ID"

echo "==> Enabling required Cloud APIs..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com firestore.googleapis.com

echo "==> Deploying backend container to Cloud Run ($REGION)..."
gcloud run deploy "$SERVICE" --source . --region "$REGION" --allow-unauthenticated \
  --set-env-vars "USE_FIREBASE=1,FIREBASE_PROJECT_ID=$PROJECT_ID,AUTO_SEED=1" \
  --memory 512Mi --cpu 1 --max-instances 5

echo "==> Updating .firebaserc & firebase.json..."
sed -i.bak "s/YOUR_FIREBASE_PROJECT_ID/$PROJECT_ID/" .firebaserc && rm -f .firebaserc.bak
sed -i.bak "s/\"region\": \"[a-z0-9-]*\"/\"region\": \"$REGION\"/g" firebase.json && rm -f firebase.json.bak

echo "==> Deploying Firebase Hosting and Firestore security rules..."
firebase deploy --only hosting,firestore:rules,firestore:indexes --project "$PROJECT_ID"

echo "=========================================================="
echo "Deployment Complete!"
echo "Live Web URL: https://$PROJECT_ID.web.app"
echo "=========================================================="
