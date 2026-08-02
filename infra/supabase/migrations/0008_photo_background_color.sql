-- Feature 006 follow-up: the photo's own background colour, so a non-square
-- photo can be padded to 1:1 with a colour that continues its backdrop rather
-- than a grey letterbox (docs/design-decisions.md §31).
--
-- Deliberately NOT part of `colors`: that column is the GARMENT's colours and
-- feeds the styling pipeline's colour-harmony scorer. A backdrop colour in
-- there would be scored as if the user were wearing the wall. This is a
-- presentation attribute of the photo, stored beside `photo_path` and never
-- surfaced as an attribute of the item.
--
-- Nullable with no default: the VLM leaves it null on a busy or unreadable
-- background, and every item added before this migration has none. The
-- frontend falls back to a neutral surface token in both cases — there is no
-- correct value to invent here.

alter table wardrobe_items
  add column photo_background_color text
    check (photo_background_color is null or photo_background_color ~ '^#[0-9a-f]{6}$');

comment on column wardrobe_items.photo_background_color is
  'Hex colour of the photo backdrop, used to pad non-square photos to 1:1. Not a garment colour.';
