# Deploying Pub Hedge

**Live now:** app at https://pubhedge.vercel.app (Vercel project `pubhedge`, team Finance Trackers), API at
https://pubhedge-agents-493974186765.europe-west2.run.app (Cloud Run service `pubhedge-agents`, project
`uclagentverse26lon-5545`, `europe-west2`). Keys are in that project's Secret Manager; the access key and API URL
are in Vercel's production environment.

To redeploy the app after a change, from `app/`: `vercel deploy --prod`. To redeploy the API, build the image with
Cloud Build and run `gcloud run deploy pubhedge-agents --image <new image> --region europe-west2` (the secrets and
settings carry over), or use `scripts/deploy.sh`.

Two services, each on the host that suits it:

| Part | Host | Why |
|---|---|---|
| Front end (`app/`, Next.js) | **Vercel** (free Hobby plan) | Made for Next.js: connect the repo and it builds on every push |
| Agent API (`services/agents/`, FastAPI) | **Google Cloud Run** | Runs the existing Dockerfile, streams the 40-second agent run without a timeout, scales to zero, and sits next to Gemini |

The API can't run on Vercel: an agent run streams for about 40 seconds and the audit log is a SQLite file,
which serverless functions don't keep.

**Password protection** is built into the app, so it works on the free plan. Vercel's own password
protection is a paid add-on.

- `SITE_PASSWORD` turns on a browser password prompt for every page and every script file.
- `PUBHEDGE_ACCESS_KEY` makes the API refuse any call that doesn't carry the key. The app sends it
  automatically, and only people past the password prompt ever receive the app's code.

Both are off when unset, so local development is unchanged.

## 1. Pick the shared secrets

Make up two values and keep them in a password manager:

- **Site password:** what you give judges.
- **Access key:** a long random string (`openssl rand -hex 32`). Nobody types it.

## 2. API on Cloud Run

Once, in a Google Cloud project with billing on:

```bash
gcloud services enable run.googleapis.com artifactregistry.googleapis.com secretmanager.googleapis.com
gcloud artifacts repositories create pubhedge --repository-format=docker --location=europe-west2
```

Store each key in Secret Manager. Each command asks for the value on the prompt, so nothing lands in your shell
history:

```bash
for s in gemini-api-key companies-house-key metoffice-key stripe-test-key pubhedge-access-key; do
  read -rsp "$s: " v && printf %s "$v" | gcloud secrets create "$s" --data-file=- && echo
done
```

Then deploy (the Vercel URL can be a placeholder the first time and updated after step 3):

```bash
GCP_PROJECT=your-project APP_ORIGIN=https://your-app.vercel.app scripts/deploy.sh
```

The script builds the image, deploys it with the keys from Secret Manager, `--max-instances 1` (the SQLite
audit log lives in one instance) and the app's origin for CORS. Then it deploys the front end with the CLI.
To use the Vercel dashboard instead, do step 3.

## 3. Front end on Vercel (dashboard route)

1. On vercel.com: **Add New → Project**, import the GitHub repo, and set **Root Directory** to `app`.
2. Under **Environment Variables**, add:

   | Name | Value |
   |---|---|
   | `NEXT_PUBLIC_API_URL` | the Cloud Run URL from step 2 |
   | `NEXT_PUBLIC_PUBHEDGE_ACCESS_KEY` | the access key |
   | `SITE_PASSWORD` | the site password |
   | `SITE_USER` | optional, default `pubhedge` |

3. Deploy. Put the resulting URL into Cloud Run's `PUBHEDGE_APP_ORIGIN` if it differs from what you used.

Check it: the site should ask for a password; the API's `/api/health` should answer, and `/api/state` should
return 401 without the key.

## Where the keys live

Keys go into the platform that runs the code: Secret Manager for the API, Vercel's environment variables for
the front end. They never go into the repo or the image.

**GitHub Actions secrets** are only needed if a GitHub workflow uses them; this repo has none (checks run
locally with `scripts/check.sh`). If you later want GitHub to deploy for you, add them like this (the repo owner
has to do it, because it needs admin rights on the repo):

```bash
gh secret set -f .env.local --repo emirhanemre/agentverse_finance   # every line of the file becomes a secret
gh secret list --repo emirhanemre/agentverse_finance                # names only; values are never shown again
```

Or one at a time: **Settings → Secrets and variables → Actions → New repository secret**.

## Costs and limits

- Cloud Run and Vercel Hobby are free at demo traffic. Gemini spend stops at `PUBHEDGE_SPEND_CAP_USD`
  (default $8).
- The audit log and proposals live in the container's `/tmp` and reset when Cloud Run starts a fresh instance.
  Use **Replay** or a fresh run after a cold start.
- Execution stays paper only. Nothing in a deployment can place a real order.
