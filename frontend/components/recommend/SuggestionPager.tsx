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
}

/**
 * design/design-system.md § Outfit suggestion pager. Owns paging `index`
 * and per-card feedback state (data-model.md — feedback isn't persisted
 * beyond this mounted card group, FR-012). Per design-decisions.md §42,
 * every outfit here is already saved (favorited by default) by the time
 * this component ever renders — the heart only ever toggles `favorite`
 * via a local override keyed by card index; there is no "not yet saved"
 * state to track anymore. Genuinely different mechanics per tier
 * (research.md §5): mobile is transform-slide, arrow-only, no native
 * scroll at all; tablet/desktop is a native scroll-snap track kept in sync
 * with the arrows via a `scroll` listener.
 */
export function SuggestionPager({ outfits }: SuggestionPagerProps) {
  const router = useRouter();
  const trackRef = useRef<HTMLDivElement>(null);
  const [index, setIndex] = useState(0);
  const [isDesktop, setIsDesktop] = useState(false);
  // Keyed by card index. Only ever set once the heart has been tapped this
  // session — before that, `outfit.favorite` (from the response) is the
  // source of truth.
  const [favorites, setFavorites] = useState<Record<number, boolean>>({});
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
    const { data } = await apiClient.POST("/api/v1/recommend/outfits/{outfit_id}/favorite", {
      params: { path: { outfit_id: outfit.id } },
    });
    if (data) setFavorites((prev) => ({ ...prev, [cardIndex]: data.favorite }));
  }

  function handleFeedback(cardIndex: number, value: "up" | "down") {
    setFeedback((prev) => ({ ...prev, [cardIndex]: prev[cardIndex] === value ? null : value }));
  }

  function handleCardTap(cardIndex: number) {
    const id = outfits[cardIndex]?.id;
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
                saved={favorites[i] ?? outfit.favorite}
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
                  saved={favorites[i] ?? outfit.favorite}
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
