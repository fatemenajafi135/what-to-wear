"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { apiClient } from "@/lib/api/client";
import type { components } from "@/lib/api/schema";
import { OutfitCard } from "./OutfitCard";
import { PagerControls } from "./PagerControls";
import styles from "./SuggestionPager.module.css";

type StylingOutfit = components["schemas"]["StylingOutfit"];

const DESKTOP_QUERY = "(min-width: 768px)";

export interface SuggestionPagerProps {
  outfits: StylingOutfit[];
  /** design-decisions.md §38 — sent on every save so the backend can
   * capture citations/dimension scores from this thread's own checkpointed
   * pipeline result. Every outfits-bearing reply carries a real thread_id
   * (`RecommendChat.tsx` always sets it from `SendMessageResponse.thread_id`
   * before this component ever mounts), so it's required here, not
   * defensively optional. */
  threadId: string;
}

interface SavedState {
  id: string;
  favorite: boolean;
}

/**
 * design/design-system.md § Outfit suggestion pager. Owns paging `index`,
 * per-card saved-id and feedback state (data-model.md — none of it
 * persisted beyond this mounted card group, per design-decisions.md §32
 * for saves and FR-012 for feedback). Genuinely different mechanics per
 * tier (research.md §5): mobile is transform-slide, arrow-only, no native
 * scroll at all; tablet/desktop is a native scroll-snap track kept in sync
 * with the arrows via a `scroll` listener.
 */
export function SuggestionPager({ outfits, threadId }: SuggestionPagerProps) {
  const router = useRouter();
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [isDesktop, setIsDesktop] = useState(false);
  // Keyed by card index. `id` is permanent once a card is first saved this
  // session; `favorite` is what the heart's second tap onward flips —
  // keeping them separate (rather than clearing the id on unfavorite) is
  // what lets a later re-tap toggle the same row back on instead of
  // creating a duplicate (design-decisions.md §32: unsaving flips, never
  // deletes).
  const [saved, setSaved] = useState<Record<number, SavedState>>({});
  const [feedback, setFeedback] = useState<Record<number, "up" | "down" | null>>({});

  useLayoutEffect(() => {
    const mql = window.matchMedia(DESKTOP_QUERY);
    setIsDesktop(mql.matches);
    const onChange = (e: MediaQueryListEvent) => setIsDesktop(e.matches);
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  const reducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const goTo = useCallback(
    (nextIndex: number) => {
      const clamped = Math.max(0, Math.min(outfits.length - 1, nextIndex));
      setIndex(clamped);
      if (isDesktop && trackRef.current) {
        const card = trackRef.current.children[clamped] as HTMLElement | undefined;
        card?.scrollIntoView({
          behavior: reducedMotion() ? "auto" : "smooth",
          inline: "center",
          block: "nearest",
        });
      }
    },
    [outfits.length, isDesktop],
  );

  useEffect(() => {
    if (!isDesktop) return;
    const track = trackRef.current;
    if (!track) return;

    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const cardWidth = track.children[0]?.clientWidth || 1;
        const next = Math.round(track.scrollLeft / cardWidth);
        setIndex((prev) => (prev === next ? prev : Math.max(0, Math.min(outfits.length - 1, next))));
      });
    };
    track.addEventListener("scroll", onScroll);
    return () => {
      track.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, [isDesktop, outfits.length]);

  async function handleToggleHeart(cardIndex: number) {
    const outfit = outfits[cardIndex];
    if (!outfit) return;
    const existing = saved[cardIndex] ?? (outfit.id ? { id: outfit.id, favorite: true } : undefined);

    if (existing) {
      const { data } = await apiClient.POST("/api/v1/recommend/outfits/{outfit_id}/favorite", {
        params: { path: { outfit_id: existing.id } },
      });
      if (data) setSaved((prev) => ({ ...prev, [cardIndex]: { id: existing.id, favorite: data.favorite } }));
      return;
    }

    const { data } = await apiClient.POST("/api/v1/recommend/outfits", {
      body: {
        occasion: outfit.occasion,
        meta_line: outfit.meta_line,
        rationale_text: outfit.rationale_text,
        match_label: outfit.match_label,
        item_ids: outfit.items.map((item) => item.id),
        thread_id: threadId,
      },
    });
    if (data) setSaved((prev) => ({ ...prev, [cardIndex]: { id: data.id, favorite: data.favorite } }));
  }

  function handleFeedback(cardIndex: number, value: "up" | "down") {
    setFeedback((prev) => ({ ...prev, [cardIndex]: prev[cardIndex] === value ? null : value }));
  }

  function handleCardTap(cardIndex: number) {
    const id = saved[cardIndex]?.id ?? outfits[cardIndex]?.id;
    if (id) router.push(`/outfits/${id}`);
  }

  if (outfits.length === 0) return null;

  return (
    <div className={styles.group}>
      <div ref={trackRef} className={isDesktop ? styles.trackDesktop : styles.trackMobile} data-testid="pager-track">
        {isDesktop ? (
          outfits.map((outfit, i) => (
            <div key={i} className={styles.slideDesktop}>
              <OutfitCard
                outfit={outfit}
                saved={saved[i]?.favorite ?? Boolean(outfit.id)}
                feedback={feedback[i] ?? null}
                onToggleHeart={() => handleToggleHeart(i)}
                onFeedback={(value) => handleFeedback(i, value)}
                onCardTap={() => handleCardTap(i)}
              />
            </div>
          ))
        ) : (
          <div className={styles.slideMobileInner} style={{ transform: `translateX(-${index * 100}%)` }}>
            {outfits.map((outfit, i) => (
              <div key={i} className={styles.slideMobile}>
                <OutfitCard
                  outfit={outfit}
                  saved={saved[i]?.favorite ?? Boolean(outfit.id)}
                  feedback={feedback[i] ?? null}
                  onToggleHeart={() => handleToggleHeart(i)}
                  onFeedback={(value) => handleFeedback(i, value)}
                  onCardTap={() => handleCardTap(i)}
                />
              </div>
            ))}
          </div>
        )}
      </div>
      <PagerControls
        index={index}
        count={outfits.length}
        onPrev={() => goTo(index - 1)}
        onNext={() => goTo(index + 1)}
      />
    </div>
  );
}
