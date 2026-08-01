-- Feature 006: photo upload + vision. No new table — the bucket itself is
-- declared in infra/supabase/config.toml ([storage.buckets.wardrobe-photos],
-- private), since `supabase db reset` provisions config.toml buckets
-- automatically and that's the only way a bucket survives a reset
-- reproducibly (specs/006-photo-upload-vision/handoff §5.1). This migration
-- is only the RLS policy + grant on storage.objects, the table Supabase's
-- Storage extension already owns.
--
-- Unlike wardrobe_items (0002), this backend's own pooler connection never
-- touches storage.objects directly — every upload and signed-URL request
-- goes through Supabase Storage's own HTTP API, authenticated with the
-- caller's JWT, which evaluates this policy for real on every call. This is
-- the actual isolation guarantee here, not just documented convention (see
-- specs/006-photo-upload-vision/research.md §2 and handoff trap 1: uploads
-- and signing always use the caller's own bearer token, never a
-- service-role key, or this policy would be silently bypassed).

create policy "wardrobe_photos_owner_rw" on storage.objects
  for all
  using (
    bucket_id = 'wardrobe-photos'
    and (storage.foldername(name))[1] = auth.uid()::text
  )
  with check (
    bucket_id = 'wardrobe-photos'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

-- Table-level GRANT, matching 0002's own precedent — required or the policy
-- above is unreachable ("permission denied for table objects") regardless
-- of what it says (handoff §5.1, trap 4; 004/013 found the same class of
-- gap on wardrobe_items/other tables).
grant select, insert, update, delete on storage.objects to authenticated;
