// Constitution Principle VII: the frontend consumes generated types from the
// backend's OpenAPI schema, no hand-maintained duplicates. lib/api-types.ts
// is generated (`npm run fetch:openapi && npm run gen:types`, see
// quickstart.md); this file re-exports the specific schemas the app uses
// under shorter, stable names so components don't reach into the generated
// `components["schemas"][...]` path directly.

import type { components } from "./api-types";

export type WardrobeItem = components["schemas"]["WardrobeItem"];
export type ExtractedAttributes = components["schemas"]["ExtractedAttributes"];
export type PhotoExtractionResponse = components["schemas"]["PhotoExtractionResponse"];
export type CreateWardrobeItemFromUploadRequest = components["schemas"]["CreateWardrobeItemFromUploadRequest"];
export type DimensionScore = components["schemas"]["DimensionScore"];
export type ScoredOutfit = components["schemas"]["ScoredOutfit"];
export type SuggestResult = components["schemas"]["SuggestResult"];

// The `done` SSE event's payload (contracts/suggest.md) -- constructed as a
// plain dict in api.py, not a Pydantic response_model (the endpoint's actual
// return is a stream), so it has no generated schema of its own to import.
export interface SuggestDonePayload {
  thread_id: string;
  result: SuggestResult;
  note: string | null;
}
