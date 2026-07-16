"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { WardrobeItem } from "@/lib/types";
import { ClosetItemCard } from "@/components/ClosetItemCard";

export default function ClosetPage() {
  const [items, setItems] = useState<WardrobeItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<WardrobeItem[]>("/wardrobe/items")
      .then((result) => {
        if (!cancelled) setItems(result);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError) {
          setError(`Couldn't load your closet (${err.status}).`);
        } else {
          setError("Couldn't load your closet.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="closet-page">
      <h1>Your closet</h1>

      {error && <p className="page-error">{error}</p>}

      {items === null && !error && <p className="text-muted">Loading your closet…</p>}

      {items !== null && items.length === 0 && (
        <div className="closet-empty-state">
          <p className="text-muted">Your closet is empty — nothing here yet.</p>
          <Link href="/closet/add" className="btn btn-primary">
            Add your first item by photo
          </Link>
        </div>
      )}

      {items !== null && items.length > 0 && (
        <div className="closet-grid">
          {items.map((item) => (
            <ClosetItemCard key={item.id} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}
