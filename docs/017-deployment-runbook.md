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

Migrations live in `backend/migrations/` (numbered `0001.sql` through `0012.sql`). Run them in order:

**Option A: Via psql (direct connection)**

```bash
# Get the direct connection string from Supabase Settings → Database
# (port 5432, not 6543; session mode, not transaction pooler)
DIRECT_URL="postgresql://postgres:YOUR_PASSWORD@db.xxxxx.supabase.co:5432/postgres"

for i in {1..12}; do
  psql "$DIRECT_URL" -f backend/migrations/$(printf "%04d" $i).sql
done
```

**Option B: Via Supabase's SQL editor (safer if you don't have psql)**

1. In the Supabase dashboard, go to **SQL Editor**.
2. Create a new query.
3. Copy the contents of `backend/migrations/0001.sql`, paste it, and run it.
4. Repeat for `0002.sql` through `0012.sql` in order.
5. (Copy-paste is tedious; psql is faster, but both work.)

### Step 4: Create the storage bucket

1. In Supabase, go to **Storage** (left sidebar).
2. Click **"New bucket"**.
3. **Bucket name:** `photos`
4. **Public bucket:** Leave unchecked (we'll use signed URLs).
5. Click **"Create bucket"**.

### Step 5: Apply RLS policies to the bucket

The photos bucket needs row-level security so users can only see their own photos.

1. Go to **Settings** → **Database** → **Edit policies**.
2. Look for the `photos` bucket in the storage section.
3. Create two policies (or paste the SQL from `backend/migrations/0013_storage_rls.sql` if it exists):

   **Policy 1: SELECT (read your own photos)**
   ```sql
   SELECT auth.uid()::text = (storage.foldername(name))[1]
   ```

   **Policy 2: INSERT (upload to your folder)**
   ```sql
   auth.uid()::text = (storage.foldername(name))[1]
   ```

If these policies don't exist, users won't be able to upload or download photos.

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

Render will automatically detect `render.yaml` at the repo root and read:
- **Service name:** `w2w-backend-staging`
- **Dockerfile path:** `./backend/Dockerfile`
- **Build context:** `backend/` directory
- **Health check path:** `/health`
- **Environment variables:** Defined in `render.yaml` (but you'll fill in secrets below)

Click **"Create Web Service"** — Render will build and deploy.

### Step 3: Add secrets

Render won't start the app until all secret env vars are set:

1. Once the service is created, go to its **Environment** section.
2. For each secret var in `render.yaml` marked `scope: "secret"`, click **"Add secret"** and fill in:

   | Variable | Value | Where to get it |
   |---|---|---|
   | `DATABASE_URL` | `postgresql://postgres.pooler-dev:PASSWORD@db.SUPABASE_ID.supabase.co:6543/postgres` | Supabase Settings → Database (use transaction-pooler port 6543, not direct 5432) |
   | `DATABASE_URL_DIRECT` | `postgresql://postgres:PASSWORD@db.SUPABASE_ID.supabase.co:5432/postgres` | Same, but port 5432 (session mode) |
   | `SUPABASE_URL` | From Supabase Settings → API | Copy "Project URL" |
   | `AI_GATEWAY_API_KEY` | Your Vercel AI Gateway key or leave blank if not available | https://vercel.com/ai (optional; set later if needed) |
   | `WTW_QDRANT_URL` | Your Qdrant cluster URL | From Qdrant Cloud settings |
   | `WTW_QDRANT_API_KEY` | Your Qdrant API key | From Qdrant Cloud settings |

3. Click **"Save"** and Render will redeploy with the new secrets.

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

**Solution:** Make sure both point to the same Supabase instance:
- Frontend: `https://w2w-staging.supabase.co`
- Backend (via Render env var `SUPABASE_URL` or `DATABASE_URL` connection string): same URL or direct connection to the same database

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

**Backend (Render):**
```
DATABASE_URL=postgresql://postgres.pooler-dev:PASSWORD@db.SUPABASE_ID.supabase.co:6543/postgres
DATABASE_URL_DIRECT=postgresql://postgres:PASSWORD@db.SUPABASE_ID.supabase.co:5432/postgres
SUPABASE_URL=https://SUPABASE_ID.supabase.co
SUPABASE_JWT_AUD=authenticated
WTW_CHECKPOINTER_MODE=postgres
WTW_CORS_ORIGINS=https://w2w-staging.vercel.app
WTW_QDRANT_URL=https://QDRANT_CLUSTER.eu-0.qdrant.io:6333
WTW_QDRANT_API_KEY=YOUR_QDRANT_KEY
AI_GATEWAY_API_KEY=(optional) your Vercel AI Gateway key
LOG_LEVEL=INFO
ENVIRONMENT=staging
```

**Frontend (Vercel):**
```
NEXT_PUBLIC_SUPABASE_URL=https://SUPABASE_ID.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=YOUR_ANON_KEY
NEXT_PUBLIC_API_URL=https://w2w-backend-staging.onrender.com
```

---

**Last updated:** Feature 017  
**Branch:** feat/017-deployment-readiness
