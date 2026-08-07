# Data Model: Auth

This feature adds no database tables or migrations. All entities below are owned and
persisted by Supabase Auth itself (`auth.users`, its refresh-token store); the app never
reads or writes them directly except through the Supabase Auth client/API.

## Account

Represents a registered user identity, entirely managed by Supabase Auth.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Supabase's user id. This is the JWT's `sub` claim — the only piece of this entity the backend ever sees directly. |
| `email` | string | Unique per project. Used for sign-in and as the reset-email destination. |
| `password` | — | Never held by the app; Supabase Auth stores and verifies it. Client-side minimum: 8 characters (design-decisions §1.7). Server-enforced via `minimum_password_length = 8` in `infra/supabase/config.toml`. |
| Google identity | — | Linked automatically by Supabase Auth on first successful Google sign-in for a given email; the app does not model this link itself. |

**Validation rules** (client-side, mirrored by Supabase server-side config):
- Email: standard email format (`field.email.invalid` on failure).
- Password: minimum 8 characters (`field.password.tooShort` on failure); sign-up's
  confirm-password field must match (`field.password.mismatch`).

**Lifecycle**: created on sign-up (email+password or first Google sign-in) → authenticates
via sign-in → password may be replaced via the reset flow → account itself is never deleted
or exported by this feature (out of scope, `known-gaps.md` §0.6).

## Session

Represents a currently-authenticated browser context. Fully owned by Supabase Auth /
`@supabase/ssr`; the app never constructs, stores, or validates one directly on the frontend
— it only asks "is there a session?" and reacts.

| Field | Type | Notes |
|---|---|---|
| Access token | JWT | Short-lived (`jwt_expiry`, default 3600s per `config.toml`). Signed with the project's asymmetric signing key (ES256, per research.md §2). Carries `sub` (Account id) and `aud` (`authenticated`). |
| Refresh token | opaque string | Rotates on use (`enable_refresh_token_rotation = true`). Used by `@supabase/ssr` to silently mint a new access token, which is what makes FR-009 (session survives reload) work without a re-login prompt. |

**State transitions**: none (signed out) → active (sign-up, sign-in, or completed OAuth
callback) → active, refreshed (silent, on expiry) → none (explicit sign-out, or refresh
token itself expires/is revoked).

**Backend's view**: the backend never sees or stores a Session. Each request either carries
a currently-valid access token (verified per-request, statelessly, via JWKS) or it doesn't —
there is no server-side session table.

## Password reset request

A one-time, time-limited capability tied to an Account's email, entirely managed by Supabase
Auth's recovery-link mechanism.

| Field | Type | Notes |
|---|---|---|
| Token | opaque, in the emailed link's URL | Consumed exactly once by `/reset-password/:token`. Expiry governed by Supabase Auth's own link-expiry setting (not overridden by this feature). |

**State transitions**: requested (`/forgot-password` submission) → valid until first use or
expiry → consumed (password updated, token now invalid) or expired (error state, per FR-007).

**Note on enumeration**: `/forgot-password`'s confirmation state is identical whether or not
the email is registered (FR-006), so from the frontend's perspective this entity's existence
is never observable except through the emailed link itself.
