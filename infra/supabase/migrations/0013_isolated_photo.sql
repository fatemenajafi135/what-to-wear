-- Feature 018: each detection's isolated (background-removed) image is its
-- own Storage object under the same {user_id}/ prefix photo_path already
-- uses — infra/supabase/migrations/0006_wardrobe_photos.sql's RLS policy
-- matches on that prefix alone, so no policy change is needed here, only
-- the pointer column. Additive, not a taxonomy change (Constitution VI is
-- not implicated — spec.md says so explicitly).
--
-- Nullable with no default: isolation is best-effort (FR-013) and every
-- item saved before this migration has none. Both ClosetGrid and the item
-- detail hero already fall back to the original photo when this is null
-- (ItemPhoto's existing behavior, unchanged).

alter table wardrobe_items
  add column isolated_photo_path text;

comment on column wardrobe_items.isolated_photo_path is
  'Storage object path of the background-removed image, when isolation succeeded. NULL falls back to photo_path.';
