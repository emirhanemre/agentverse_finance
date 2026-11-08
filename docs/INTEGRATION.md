# Integration record

Fetched 7 November 2026 from `https://github.com/emirhanemre/agentverse_finance`:

- `luke-dev`: `86b44a5c7c51b2875667e32f56e35fcb442d5353`
- `nick-demo`: `93a8f12ed52f4717d52bf7f49fe3762e0ace2d70`

Integration remains on `luke-dev`. No remote branches are changed.

Before editing, the complete working tree (excluding dependencies, build caches and Git internals) was archived to `/private/tmp/agentverse-checkpoint-20261107/worktree.tar.gz`. All Git refs were bundled to `repository.bundle` in that directory. This includes the user's untracked frontend and screenshots. Keep this directory until the changes are accepted. Original frontend source matched `nick-demo`, except the existing local `package-lock.json`.

The untouched baseline runs from `/private/tmp/agentverse-nick-baseline/app`. Current captures use `scripts/capture_baseline.cjs`; pre-existing screenshots are preserved in `docs/screenshots/baseline-nick-demo`.

Backend review: reusable frozen synthetic-revenue model, weather provenance, Decimal order-book calculations, candidate schemas and risk controls. The previous deterministic agent runtime embeds a default London business, so the application orchestration calls the reusable inference/calculation/control functions with the persisted profile directly. The original Streamlit tool remains a development reference. No existing provider cards supplied actual company verification or OAuth integrations.

Follow-up implementation adds bounded live contract verification/revalidation, per-business chronological training, authoritative paper settlement, opt-in monitoring and persistent in-app alerts. Toast, Monzo, Xero and Companies House are visual demo connections by the user's explicit request; no provider credentials or OAuth flows are needed. A second pre-change checkpoint is `/private/tmp/agentverse-implementation-checkpoint-20261108/worktree.tar.gz`.

See `docs/VERIFICATION.md` for final checks and evidence. No commit, push or deployment was performed; changes remain available for review in the `luke-dev` working tree.
