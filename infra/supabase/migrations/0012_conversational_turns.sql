-- Feature 016: Conversational styling turns. Widens the check constraint 011 already
-- anticipated (0011_chat_history.sql's own comment: "016 widens this exact constraint") — no
-- table reshape, no backfill.
--
-- See docs/design-decisions.md §47 (where accumulated slots live — the pipeline's own
-- checkpointer, not a new column, so no other schema change is needed here) and §50 (why
-- `POST /recommend/messages` stops writing `user_message` itself, unrelated to this constraint
-- but the reason both new kinds are actually used starting from this migration).

alter table messages drop constraint messages_kind_check;

alter table messages add constraint messages_kind_check
  check (kind in ('user_message', 'styling_reply', 'conversational_turn', 'wrap_up'));
