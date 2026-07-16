"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { apiFetch, ApiError } from "@/lib/api-client";
import type { WardrobeItem } from "@/lib/types";
import { ClosetItemCard } from "@/components/ClosetItemCard";
import { CATEGORY_GROUPS } from "@/lib/taxonomy";

const FILTERS = ["all", ...CATEGORY_GROUPS] as const;

export default function ClosetPage() {
  const [items, setItems] = useState<WardrobeItem[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [activeFilter, setActiveFilter] = useState<(typeof FILTERS)[number]>("all");

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

  const visibleItems = useMemo(() => {
    if (!items) return [];
    if (activeFilter === "all") return items;
    return items.filter((item) => item.category === activeFilter);
  }, [items, activeFilter]);

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
        <>
          <div className="closet-filters">
            {FILTERS.map((f) => (
              <button
                key={f}
                type="button"
                className={f === activeFilter ? "chip chip-selected" : "chip"}
                onClick={() => setActiveFilter(f)}
              >
                {f === "all" ? "All" : f.replace("_", " ")}
              </button>
            ))}
          </div>
          <div className="closet-grid">
            {visibleItems.map((item) => (
              <ClosetItemCard key={item.id} item={item} />
            ))}
          </div>
          <Link href="/closet/add" className="fab" aria-label="Add item">
            +
          </Link>
        </>
      )}
    </div>
  );
}
