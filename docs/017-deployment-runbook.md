# Feature 017: Deployment Runbook

Deploy the What to Wear staging environment from scratch. This runbook walks you through creating cloud infrastructure, configuring the backend, and deploying both backend and frontend.

**Time estimate:** 30–60 minutes (mostly waiting for services to boot).

**Prerequisites:**
- A Supabase account (https://supabase.com)
- A Qdrant Cloud account (https://cloud.qdrant.io)
- A Render account (https://render.com)
- A Vercel account with the repo connected (https://vercel.com)
- This repo cloned locally and on the feat/017-deployment-readiness branch

---

## Part 1: Supabase — Database and Auth

### Step 1: Create a new Supabase project

1. Go to https://supabase.com and sign in.
2. Click **"New project"** (or **"New"** → **"PostgreSQL database"**).
3. **Project name:** `w2w-staging` (or your preference; use this name in env vars below).
4. **Region:** Choose closest to your users (or default).
5. **Database password:** Generate a strong password. **Save it** — you'll need it in a moment and Supabase won't show it again.
6. Click **"Create new project"** and wait for it to boot (~2 min).

### Step 2: Get Supabase credentials

Once the project is ready:

1. Go to **Settings** → **API** (left sidebar).
2. Copy and save these three values:
   - **Project URL** (looks like `https://xxxxx.supabase.co`)
   - **Anon key** (public, safe to commit in frontend code)
   - **Service role key** (secret; treat like a password)

You'll use these to configure the backend and frontend.

### Step 3: Run database migrations

Migrations live in **`infra/supabase/migrations/`** — twelve files, `0001_init.sql`
through `0012_conversational_turns.sql`. They are named `NNNN_slug.sql`, not `NNNN.sql`.

**Option A — the Supabase CLI (recommended).** This is what the repo is set up for:
`infra/supabase/` already contains the `config.toml` and migration history the CLI
expects, and `db push` applies them in order and records which have run, so re-running
it later is safe.

```bash
cd infra
npx supabase login                       # opens a browser once
npx supabase link --project-ref <your-project-ref>   # from the project URL
npx supabase db push
```

`<your-project-ref>` is the subdomain in your project URL —
`https://abcdefgh.supabase.co` → `abcdefgh`. The CLI will ask for the database
password you saved in Step 1.

**Option B — psql**, if you'd rather not use the CLI. Note the glob: the filenames
have slugs, so a `printf "%04d"` loop finds nothing.

```bash
# Direct connection: port 5432, session mode — NOT the 6543 transaction pooler.
DIRECT_URL="postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres"

for f in infra/supabase/migrations/[0-9][0-9][0-9][0-9]_*.sql; do
  echo "applying $f"
  psql "$DIRECT_URL" -v ON_ERROR_STOP=1 -f "$f" || break
done
```

`ON_ERROR_STOP=1` and the `break` matter — later migrations assume earlier ones
succeeded, and without these psql would carry on past a failure and leave the schema
half-applied.

**Option C — the SQL editor**, if you have neither. Open each file in
`infra/supabase/migrations/` in ascending order, paste into Supabase's **SQL Editor**,
and run. Tedious but it works. Do not skip or reorder.

Verify all twelve applied:

```sql
-- In the SQL Editor:
select tablename from pg_tables where schemaname = 'public' order by tablename;
```

You should see `wardrobe_items`, `catalog_items`, `user_profile`, `outfits`,
`chat_sessions` and others — plus four `checkpoint*` tables, which LangGraph creates
itself at backend startup rather than by migration, so those appear later.

### Step 4: Create the storage bucket

⚠️ **The bucket must be named exactly `wardrobe-photos`.** That name is hardcoded in
the RLS policy created by `0006_wardrobe_photos.sql` and in every photo URL the backend
signs. A bucket called anything else leaves uploads failing with a 404 while everything
else looks fine.

The bucket is declared in `infra/supabase/config.toml`, which provisions it
automatically for **local** development only — `db push` does not create buckets on a
hosted project, so this one step is manual.

1. In Supabase, go to **Storage** → **New bucket**.
2. **Name:** `wardrobe-photos`
3. **Public bucket:** leave **unchecked**. The app serves photos through short-lived
   signed URLs; a public bucket would make every user's photos readable by URL alone.
4. **File size limit:** `10 MiB` — matches `wtw_max_upload_bytes` in the backend.
5. **Allowed MIME types:** `image/jpeg`, `image/png`, `image/webp`
6. Create it.

### Step 5: Storage RLS — already done, just verify

**There is nothing to create here.** Migration `0006_wardrobe_photos.sql` already
creates the `wardrobe_photos_owner_rw` policy on `storage.objects` and the matching
grant, so Step 3 applied it. Writing the policies by hand risks a second, subtly
different policy sitting alongside the real one.

Confirm it landed:

```sql
select policyname from pg_policies
where schemaname = 'storage' and tablename = 'objects';
```

You should see `wardrobe_photos_owner_rw`. If it's missing, Step 3 didn't fully apply —
fix that rather than adding policies here.

### Step 6: Configure Supabase auth for the deployed frontend

Once the frontend is deployed to Vercel, Supabase auth links (email confirmation, OAuth) will point to the deployed URL. Configure this now:

1. Go to **Settings** → **Auth** → **URL Configuration**.
2. **Site URL:** Set to your Vercel staging URL (you'll know this after deploying the frontend).
   - Example: `https://w2w-staging.vercel.app`
3. **Redirect URLs:** Add your Vercel URL and any redirect paths, e.g.:
   - `https://w2w-staging.vercel.app/auth/callback`
4. Save.

(You can update this after the frontend deploys if you don't know the URL yet.)

---

## Part 2: Qdrant Vector Database

### Step 1: Create a Qdrant Cloud collection

1. Go to https://cloud.qdrant.io and sign in.
2. Click **"Create collection"** (or **"New Collection"** if you don't see that button).
3. **Collection name:** `w2w-staging` (match Supabase naming for clarity).
4. **Vector size:** `384` (the embedding model uses 384-dimensional vectors).
5. **Distance metric:** `Cosine`.
6. Click **"Create"** and wait for it to boot (~30 seconds).

### Step 2: Get Qdrant credentials

Once created:

1. Click on the collection to open it.
2. In the sidebar, find **API Keys** or similar.
3. Create an API key (or copy the default one).
4. Save:
   - **Cluster URL** (looks like `https://xxxxx-w2w-staging.eu-0.qdrant.io:6333`)
   - **API Key** (long string, treat like a password)

### Step 3: Populate the knowledge base

The knowledge base is a separate task (not part of 017's runbook; see `docs/deferred-work.md` if you need to ingest documents). For now, the collection is empty, and the app will still boot (it just won't have fashion recommendations until data is added).

---

## Part 3: Render Backend Deployment

### Step 1: Connect your GitHub repo to Render

1. Go to https://render.com and sign in.
2. Click **"New +"** → **"Web Service"** (or **"GitHub"** if you see that).
3. Select this repo (`w2w/rebuild` or your fork).
4. Choose the `feat/017-deployment-readiness` branch (or whichever has your code).

### Step 2: Let Render detect the render.yaml

Render reads `render.yaml` from the **repository root** and configures:
- **Service name:** `w2w-backend-staging`
- **Branch:** `rebuild` — pinned in the blueprint. Without it Render would deploy this
  repo's default branch, which is still `main`, i.e. the **legacy** prototype.
- **Build context:** `backend/` (`rootDir`)
- **Dockerfile:** `./Dockerfile`, resolved relative to that root
- **Health check path:** `/health`

Click **"Create Web Service"**. The first build takes a few minutes.

### Step 3: Add secrets

Variables marked `sync: false` in `render.yaml` are deliberately not stored in git —
Render prompts for them instead. The service won't run correctly until they're set.

1. Go to the service's **Environment** section.
2. Fill in each one:

   | Variable | Where to get it |
   |---|---|
   | `DATABASE_URL` | Supabase → **Connect** (or Settings → Database) → copy the **Transaction pooler** string verbatim, then substitute your password |
   | `SUPABASE_URL` | Supabase → Settings → API → "Project URL" |
   | `AI_GATEWAY_API_KEY` | Your Vercel AI Gateway key |
   | `LANGSMITH_API_KEY` | **Required.** smith.langchain.com → Settings → API Keys. Tracing is mandatory in this project, and the check runs *before* every gateway call — see the warning below. |
   | `WTW_TOKEN_ENCRYPTION_KEY` | Required for the calendar feature. Generate: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` |
   | `WTW_QDRANT_URL` | Qdrant Cloud → cluster details |
   | `WTW_QDRANT_API_KEY` | Qdrant Cloud → API keys |
   | `WTW_CORS_ORIGINS` | Your Vercel URL — **you won't have this until Part 4.** Leave it blank now and come back. |

   ⚠️ **`LANGSMITH_API_KEY` is not optional, and its absence is invisible.**
   `_require_langsmith()` runs before every gateway call, so without it *every*
   LLM, embedding, vision and rerank call raises — while `/health` still returns
   200 and the service looks completely fine. The symptoms are indirect: adding a
   photo appears to work but the scan pre-fills nothing and you have to type every
   attribute by hand, and styling requests never produce an outfit. If you see
   either, check this key before anything else.

   Optional, and safe to leave unset for now: `COHERE_API_KEY` (improves retrieval
   reranking) and `TAVILY_API_KEY` (trend lookups). Both degrade gracefully.

   ⚠️ **Copy the connection string from the dashboard; do not hand-write it.** A hosted
   project's pooler host and username are not the same shape as the local stack's — the
   local `postgres.pooler-dev@127.0.0.1:54329` form is the Supabase CLI's own emulation
   and will not work against a hosted project. Supabase shows the exact string, per mode.

   `DATABASE_URL_DIRECT` is **optional and best left unset here.** Supabase's direct
   connection (port 5432) is IPv6-only unless you've bought the IPv4 add-on, and it may
   simply be unreachable from Render. The backend probes it and falls back to
   `DATABASE_URL` when it isn't available, so leaving it out avoids a pointless
   connection attempt on every boot.

3. Save. Render redeploys automatically.

Because `WTW_CHECKPOINTER_MODE=postgres` is set in the blueprint, a missing or
unreachable `DATABASE_URL` will **fail startup loudly** rather than silently falling
back to in-memory storage. That's intentional — see the troubleshooting section.

### Step 4: Verify the backend is running

Once Render finishes deploying:

1. Click on your service in Render.
2. Look for a public URL (e.g., `https://w2w-backend-staging.onrender.com`).
3. In your browser, visit `https://w2w-backend-staging.onrender.com/health` (replace with your URL).
4. You should get a JSON response: `{"status": "ok"}` or `{"status": "unhealthy", "failed_dependencies": ["database"]}`.

If you see `{"status": "ok"}`, the database connection works. If unhealthy, check the Render logs for errors (usually DATABASE_URL misconfiguration).

---

## Part 4: Vercel Frontend Deployment

### Step 1: Create a Vercel project

1. Go to https://vercel.com/new.
2. Import this repo (`w2w/rebuild`).
3. Select the **feat/017-deployment-readiness** branch.
4. **Framework:** Next.js (auto-detected).
5. **Build command:** Leave as default (npm run build).
6. Click **"Deploy"**.

Vercel will attempt to build, but it will **fail** until you add environment variables — this is expected and intentional (design-decisions.md §52).

### Step 2: Add frontend environment variables

1. Once the build fails, go to the Vercel project **Settings** → **Environment Variables**.
2. Add:

   | Variable | Value | Public? |
   |---|---|---|
   | `NEXT_PUBLIC_SUPABASE_URL` | Your Supabase project URL | Yes |
   | `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Your Supabase anon key | Yes |
   | `NEXT_PUBLIC_API_URL` | Your Render backend URL | Yes |

3. Click **"Save"** and redeploy (click the deploy button or wait for Vercel to auto-redeploy).

### Step 3: Critical: NEXT_PUBLIC_SUPABASE_URL must match backend SUPABASE_URL

**This is a load-bearing constraint.** The backend stamps its own `SUPABASE_URL` into every signed photo URL. The service worker's photo cache rule matches on exact origin string.

If you set:
- Frontend: `NEXT_PUBLIC_SUPABASE_URL=https://xxxxxx.supabase.co`
- Backend: `SUPABASE_URL=http://localhost:54321` (wrong!)

Then photos will fetch successfully (Supabase will redirect both URLs), but the service worker's cache rule won't match, photos won't be cached, and offline mode will have no images.

**Solution:** set both to the *identical string* — same scheme, same host, no trailing
slash:

- Vercel `NEXT_PUBLIC_SUPABASE_URL` = `https://<your-ref>.supabase.co`
- Render `SUPABASE_URL` = `https://<your-ref>.supabase.co`

Copy-paste one into the other rather than typing each. This is exact string matching,
not "the same instance" — `https://x.supabase.co` and `https://x.supabase.co/` are
different origins to the cache rule.

**Verify after deploying:** open the closet on the deployed site, then DevTools →
Application → Cache Storage. There should be a `wtw-photos` cache with entries in it.
Empty, while photos display fine on screen, means the origins don't match.

### Step 4: Verify the frontend is running

Once Vercel finishes building and deploying:

1. Click the deployment link (Vercel gives you a URL).
2. You should see the What to Wear sign-in page.
3. Try to sign up with a test email — you should receive a confirmation email from Supabase.
4. Sign in and try to add a wardrobe item.

If the app loads but photos don't upload/display:
- Check `NEXT_PUBLIC_SUPABASE_URL` matches the backend's Supabase URL (see step 3 above).
- Check storage bucket RLS policies (Part 1, Step 5).
- Check backend logs in Render for Storage errors.

---

## Verification Checklist

Before declaring deployment successful:

- [ ] **Backend health:** `curl https://YOUR_BACKEND_URL/health` returns `{"status": "ok"}`
- [ ] **Frontend loads:** `https://YOUR_FRONTEND_URL` displays the sign-in page
- [ ] **Auth works:** Sign up with a test email, receive confirmation, sign in successfully
- [ ] **Add item works:** Add a wardrobe item; it appears in the closet
- [ ] **Photo upload works (optional):** Upload a photo to an item; it displays
- [ ] **Photos are cached offline (optional):** Airplane mode on → pull-to-refresh → airplane mode off → photos still display (service worker served them from cache)

---

## Troubleshooting

### "Failed to initialize PostgresSaver. Check your database URL"

**Cause:** Backend can't reach Supabase.

**Fix:**
1. Verify `DATABASE_URL` and `DATABASE_URL_DIRECT` are set in Render.
2. Use port 6543 for transaction pooler, 5432 for direct (you set this in the env var, not Render's picker).
3. Check Supabase **Connection Pooler** is enabled (Settings → Database).
4. Test locally: `psql <your-connection-string>` — if that works, the issue is Render's egress/firewall (rare; contact Render support).

### "Photos won't upload" or "No such bucket"

**Cause:** Storage bucket not created or RLS policies wrong.

**Fix:** See Part 1, Steps 4–5. Re-check policies via Supabase SQL editor:

```sql
SELECT * FROM storage.objects WHERE bucket_id = 'photos' LIMIT 1;
```

If that query fails, RLS is denying your auth role access.

### "Photo URLs won't load" or "Photos cached as status 0"

**Cause:** Usually `NEXT_PUBLIC_SUPABASE_URL` doesn't match backend's `SUPABASE_URL`.

**Fix:** See Part 4, Step 3. Print both URLs and compare character-for-character.

---

## Next Steps (Post-Deployment)

Once staging is running:

1. **Test offline mode** — see docs/design-decisions.md §52 for the expected behavior.
2. **Load the knowledge base** — ingest fashion recommendations into Qdrant (separate task).
3. **Invite collaborators** — give them the Vercel URL and Supabase sign-in.
4. **Monitor cold starts** — if latency becomes a problem, upgrade Render's plan (see design-decisions.md §57).
5. **Production checklist** — if ready to launch, create a prod variant of this runbook and upgrade to paid Render/Vercel plans.

---

## Reference: Environment Variables by Service

**Backend (Render).** `SUPABASE_JWT_AUD`, `WTW_CHECKPOINTER_MODE`, `LOG_LEVEL` and
`ENVIRONMENT` are already set by `render.yaml`; the rest you enter in the dashboard.

```
# Copy this from Supabase → Connect → Transaction pooler. Do NOT hand-write it:
# the hosted pooler's host and username differ from the local CLI's emulation.
DATABASE_URL=<paste from the Supabase dashboard>

# Optional, and usually best left UNSET on Render — Supabase's direct connection
# is IPv6-only without the IPv4 add-on. The backend falls back to DATABASE_URL.
# DATABASE_URL_DIRECT=

SUPABASE_URL=https://SUPABASE_REF.supabase.co
WTW_CORS_ORIGINS=https://YOUR-APP.vercel.app
WTW_QDRANT_URL=https://QDRANT_CLUSTER.eu-0.qdrant.io:6333
WTW_QDRANT_API_KEY=YOUR_QDRANT_KEY
AI_GATEWAY_API_KEY=YOUR_GATEWAY_KEY
```

`AI_GATEWAY_API_KEY` is optional only in the sense that the app boots without it —
every styling request fails until it's set, so treat it as required for a usable
deployment.

**Frontend (Vercel):**
```
NEXT_PUBLIC_SUPABASE_URL=https://SUPABASE_ID.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
NEXT_PUBLIC_API_URL=https://w2w-backend-staging.onrender.com
```

---

**Last updated:** Feature 017  
**Branch:** feat/017-deployment-readiness
