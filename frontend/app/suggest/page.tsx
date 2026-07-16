"use client";

import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { RecommendResponse, WardrobeItem } from "@/lib/types";
import { SuggestionResult } from "@/components/SuggestionResult";

export default function SuggestPage() {
  const [occasion, setOccasion] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [response, setResponse] = useState<RecommendResponse | null>(null);
  const [closetById, setClosetById] = useState<Map<string, WardrobeItem>>(new Map());

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!occasion.trim()) return;

    setSubmitting(true);
    setError(null);
    setResponse(null);

    try {
      const [result, closet] = await Promise.all([
        apiFetch<RecommendResponse>("/recommend", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ occasion }),
        }),
        apiFetch<WardrobeItem[]>("/wardrobe/items"),
      ]);
      setResponse(result);
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
        <label>
          Describe what you need
          <textarea
            value={occasion}
            onChange={(e) => setOccasion(e.target.value)}
            placeholder="e.g. something for a casual dinner tonight, it's cold out"
            rows={3}
            required
          />
        </label>
        <button type="submit" disabled={submitting}>
          {submitting ? "Thinking…" : "Get a suggestion"}
        </button>
      </form>

      {error && <p className="page-error">{error}</p>}

      {response && (
        <SuggestionResult result={response.result} rendered={response.rendered} closetById={closetById} />
      )}
    </div>
  );
}
