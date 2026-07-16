"use client";

import { useState } from "react";
import { apiFetch, ApiError, postSSE } from "@/lib/api-client";
import type { SuggestDonePayload, WardrobeItem } from "@/lib/types";
import { SuggestionResult } from "@/components/SuggestionResult";

export default function SuggestPage() {
  const [occasion, setOccasion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<SuggestDonePayload | null>(null);
  const [closetById, setClosetById] = useState<Map<string, WardrobeItem>>(new Map());

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!occasion.trim()) return;

    setSubmitting(true);
    setError(null);
    setResponse(null);

    try {
      const closetPromise = apiFetch<WardrobeItem[]>("/wardrobe/items");

      // Consume the `done` event only -- progressive per-outfit streaming UI
      // is unscoped new product work, not part of this endpoint cutover.
      let done: SuggestDonePayload | null = null;
      for await (const evt of postSSE("/suggest", { occasion })) {
        if (evt.event === "done") {
          done = JSON.parse(evt.data) as SuggestDonePayload;
        }
      }
      if (!done) {
        throw new Error("stream ended without a done event");
      }

      const closet = await closetPromise;
      setResponse(done);
      setClosetById(new Map(closet.map((item) => [item.id, item])));
    } catch (err) {
      if (err instanceof ApiError) {
        setError(`Couldn't get a suggestion right now (${err.status}). Please try again.`);
      } else {
        setError("Couldn't get a suggestion right now. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="suggest-page">
      <h1>What should I wear?</h1>
      <form className="suggest-form" onSubmit={handleSubmit}>
        <div className="field">
          <label htmlFor="occasion">Describe what you need</label>
          <textarea
            id="occasion"
            className="input"
            value={occasion}
            onChange={(e) => setOccasion(e.target.value)}
            placeholder="e.g. something for a casual dinner tonight, it's cold out"
            rows={3}
            required
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={submitting}>
          {submitting ? "Thinking…" : "Get a suggestion"}
        </button>
      </form>

      {error && <p className="page-error">{error}</p>}
      {response?.note && <p className="page-note">{response.note}</p>}

      {response && <SuggestionResult result={response.result} closetById={closetById} />}
    </div>
  );
}
