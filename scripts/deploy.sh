#!/usr/bin/env bash
# Prepared deployment, NOT run for the hackathon. Requires gcloud and vercel CLIs, logged in.
# Agent service -> Cloud Run (keys from Secret Manager); front end -> Vercel with NEXT_PUBLIC_API_URL.
set -euo pipefail
: "${GCP_PROJECT:?set GCP_PROJECT}" "${REGION:=europe-west2}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="$REGION-docker.pkg.dev/$GCP_PROJECT/pubhedge/agents:$(git -C "$ROOT" rev-parse --short HEAD)"
docker build -f "$ROOT/services/agents/Dockerfile" -t "$IMAGE" "$ROOT"
docker push "$IMAGE"
gcloud run deploy pubhedge-agents --image "$IMAGE" --region "$REGION" --project "$GCP_PROJECT" \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,COMPANIES_HOUSE_KEY=companies-house-key:latest,METOFFICE_DATAHUB_KEY=metoffice-key:latest,STRIPE_SECRET_KEY=stripe-test-key:latest \
  --allow-unauthenticated
API_URL="$(gcloud run services describe pubhedge-agents --region "$REGION" --project "$GCP_PROJECT" --format 'value(status.url)')"
(cd "$ROOT/app" && vercel deploy --prod --build-env NEXT_PUBLIC_API_URL="$API_URL")
