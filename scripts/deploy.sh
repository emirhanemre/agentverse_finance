#!/usr/bin/env bash
# Prepared deployment, NOT run for the hackathon. Requires gcloud and vercel CLIs, logged in.
# Agent service -> Cloud Run (keys from Secret Manager); front end -> Vercel with NEXT_PUBLIC_API_URL.
set -euo pipefail
: "${GCP_PROJECT:?set GCP_PROJECT}" "${REGION:=europe-west2}" "${APP_ORIGIN:?set APP_ORIGIN, the Vercel URL}"
# Secret Manager must already hold: gemini-api-key, companies-house-key, metoffice-key, stripe-test-key,
# pubhedge-access-key. Vercel must already hold SITE_PASSWORD (see docs/DEPLOY.md).
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="$REGION-docker.pkg.dev/$GCP_PROJECT/pubhedge/agents:$(git -C "$ROOT" rev-parse --short HEAD)"
docker build -f "$ROOT/services/agents/Dockerfile" -t "$IMAGE" "$ROOT"
docker push "$IMAGE"
gcloud run deploy pubhedge-agents --image "$IMAGE" --region "$REGION" --project "$GCP_PROJECT" \
  --set-secrets GEMINI_API_KEY=gemini-api-key:latest,COMPANIES_HOUSE_KEY=companies-house-key:latest,METOFFICE_DATAHUB_KEY=metoffice-key:latest,STRIPE_SECRET_KEY=stripe-test-key:latest,PUBHEDGE_ACCESS_KEY=pubhedge-access-key:latest \
  --set-env-vars PUBHEDGE_APP_ORIGIN="$APP_ORIGIN" \
  --max-instances 1 --timeout 300 \
  --allow-unauthenticated  # the access key, not IAM, guards the API; max one instance keeps SQLite consistent
API_URL="$(gcloud run services describe pubhedge-agents --region "$REGION" --project "$GCP_PROJECT" --format 'value(status.url)')"
ACCESS_KEY="$(gcloud secrets versions access latest --secret pubhedge-access-key --project "$GCP_PROJECT")"
(cd "$ROOT/app" && vercel deploy --prod --build-env NEXT_PUBLIC_API_URL="$API_URL" \
  --build-env NEXT_PUBLIC_PUBHEDGE_ACCESS_KEY="$ACCESS_KEY")
