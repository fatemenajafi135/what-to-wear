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
export type Outfit = components["schemas"]["Outfit"];
export type OutfitResult = components["schemas"]["OutfitResult"];
export type RecommendResponse = components["schemas"]["RecommendResponse"];
