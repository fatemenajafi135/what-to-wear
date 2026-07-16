"use client";

import { useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { SubmitFeedbackRequest, SuggestionFeedback } from "@/lib/types";

type Verdict = "liked" | "rejected";

/** Reaction affordance for a single outfit card (US1: react to a
 * suggestion). item_ids identify the outfit for the backend's upsert
 * dedup key -- reacting again to the same outfit replaces this component's
 * local state too, matching the API's replace-not-accumulate behavior. */
export function OutfitReaction({ itemIds }: { itemIds: string[] }) {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [showReasonField, setShowReasonField] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(nextVerdict: Verdict, nextReason?: string) {
    setSubmitting(true);
    setError(null);
    try {
      const body: SubmitFeedbackRequest = {
        verdict: nextVerdict,
        reason: nextReason || undefined,
        item_ids: itemIds,
      };
      await apiFetch<SuggestionFeedback>("/preferences/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      setVerdict(nextVerdict);
      setShowReasonField(false);
    } catch (err) {
      setError(err instanceof ApiError ? `Couldn't save your reaction (${err.status}).` : "Couldn't save your reaction.");
    } finally {
      setSubmitting(false);
    }
  }

  if (verdict) {
    return (
      <p className="text-muted outfit-reaction-confirmed">
        {verdict === "liked" ? "You liked this outfit." : "You rejected this outfit."}
      </p>
    );
  }

  return (
    <div className="outfit-reaction">
      <div className="outfit-reaction-buttons">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={submitting}
          onClick={() => submit("liked")}
        >
          Like
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={submitting}
          onClick={() => setShowReasonField((v) => !v)}
        >
          Reject
        </button>
      </div>

      {showReasonField && (
        <div className="field outfit-reaction-reason">
          <label htmlFor={`reject-reason-${itemIds.join(",")}`}>Why? (optional)</label>
          <input
            id={`reject-reason-${itemIds.join(",")}`}
            className="input"
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="e.g. don't like this color"
          />
          <button
            type="button"
            className="btn btn-primary btn-block"
            disabled={submitting}
            onClick={() => submit("rejected", reason)}
          >
            Confirm reject
          </button>
        </div>
      )}

      {error && <p className="page-error">{error}</p>}
    </div>
  );
}
