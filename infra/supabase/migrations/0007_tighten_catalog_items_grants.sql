-- Follow-up fix: bring `catalog_items`' privileges back in line with what
-- 0002 actually intends.
--
-- 0002 grants exactly `select` on this table (it is shared, read-only
-- reference data; catalog population happens only through a
-- bypass-privileged connection, per specs/004-closet-read/research.md §3).
-- But Postgres' default ACL for objects created in `public` had ALSO handed
-- `authenticated` INSERT/UPDATE/DELETE/TRUNCATE/REFERENCES/TRIGGER, so the
-- effective grant was all seven privileges rather than the one 0002 asks
-- for. Measured on the live stack after a reset: `wardrobe_items` and
-- `catalog_items` carried identical privilege sets, despite 0002 granting
-- them deliberately different ones.
--
-- Nothing was exploitable: the table's only policy is a SELECT policy, and
-- RLS denies every command it has no policy for, so INSERT was already
-- rejected outright and UPDATE/DELETE matched zero rows. This is
-- defense-in-depth being quietly thinner than the migration that documents
-- it claims — exactly the drift 0002's own comment about GRANTs exists to
-- prevent. Fixing it here keeps the grant and the policy telling the same
-- story.
--
-- `anon` is untouched: it never had SELECT here and still doesn't.

revoke insert, update, delete, truncate on catalog_items from authenticated;

-- Re-assert the one privilege 0002 does intend, so this file is
-- self-contained and safe to read on its own.
grant select on catalog_items to authenticated;
