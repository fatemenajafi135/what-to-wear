import { notFound } from "next/navigation";
import { ComponentCatalog } from "./ComponentCatalog";

/**
 * Dev-only component catalog — spec.md FR-005a / research.md "Dev-only
 * catalog route gating". Excluded from the production build's discoverable
 * surface (never linked from nav chrome; renders the not-found UI instead
 * of the real catalog when built for production) while staying part of the
 * same Next.js codebase — no second build target, per Principle IX.
 *
 * Known platform quirk (Next.js 16.2.12 + Turbopack, verified): `notFound()`
 * correctly swaps the response body for the not-found UI under `next
 * start`, but the raw HTTP status stays 200 instead of 404. The catalog's
 * real content never reaches a production visitor either way — flagged
 * here rather than silently accepted.
 */
export default function DevComponentsPage() {
  if (process.env.NODE_ENV === "production") {
    notFound();
  }

  return <ComponentCatalog />;
}
