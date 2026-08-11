# Contract: Calendar pick → navigation (defect 1)

No new endpoint — `PUT /api/v1/calendar/picked-event` is unchanged
(`PickedEventRequest` in, `PickedEventView` out, both already in `schema.d.ts`). This
documents the client-side handling contract around that existing call.

## `handlePick(event)` behavioral contract

1. On tap, the tapped event's request is sent (`PUT /api/v1/calendar/picked-event`). No
   client state changes before the response arrives — no row is marked picked, no navigation
   happens yet.
2. While the request is in flight, every row is disabled (reusing the existing
   `disabled={...}` prop / `design-system.md` §"Connected, has events" dimming) to prevent a
   duplicate tap — this is a transient "request in flight" state, not yet the confirmed-pick
   state, and is trivially reversible.
3. **On success** (`error` absent, `data` present): `pickedEventStore.set(data.event)` is
   called with the confirmed server response, then the client navigates to `/recommend` via
   `useRouter().push("/recommend")`. No separate "picked" boolean is set locally — the store
   *is* the picked state from this point forward, read the same way on both Calendar and
   Recommend.
4. **On failure** (`error` present, or the request throws): no state is written, no
   navigation happens, rows re-enable, and a `Banner` (`variant="error"`) renders above the
   list with a retry action that re-attempts the same event.

## Why this replaces rather than extends the current implementation

Current code sets `pickedEventId` (local `useState`) **before** awaiting the `PUT`, and never
reads the response. That is the literal bug (issue #41, defect 1): a failed save and a
successful save are indistinguishable to the user. This contract's ordering — request, then
react to the checked result — is the fix; there is no partial/incremental version of it that
preserves the bug's shape.
