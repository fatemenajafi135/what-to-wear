# Internal Interface Contract: Scoring & Retrieval

No external/network API changes in this feature. This documents the internal
Python function signatures that other modules (the graph, `eval/harness.py`,
and future work — WP2 Engine explicitly imports `score_outfits`/
`DIMENSION_SCORERS`) depend on staying stable across this fix.

## `whattowear.colors`

```python
def hex_to_hsl(hex_color: str) -> tuple[float, float, float]:
    """Returns (hue in [0,360), saturation in [0,1], lightness in [0,1])."""

def contrast_ratio(hex_a: str, hex_b: str) -> float:
    """Unchanged — WCAG contrast ratio 1.0-21.0. No longer called by
    color_harmony.py (the value-contrast bonus uses HSL lightness instead,
    a different axis) but remains a valid public utility."""

def nearest_name(hex_color: str) -> str
def nearest_names(hex_colors: list[str]) -> list[str]
    # Unchanged signatures; FASHION_COLOR_PALETTE gains 8 entries, which can
    # only ever change *which* name a hex resolves to for colors near one of
    # the new entries — never breaks an existing call site's return type.
```

## `whattowear.scoring.color_harmony`

```python
def score(items: list[WardrobeItem], ctx: Context) -> DimensionScore:
    """Unchanged signature and return shape. Only the value/reason computed
    for a given input changes."""
```

## `whattowear.scoring.combine`

```python
Strategy = Callable[[list[DimensionScore]], float]  # unchanged

def rank_outfits(
    outfits: list[ScoredOutfit],
    strategy: Strategy = fit_first_lexicographic,  # was EQUAL_WEIGHTED_AVERAGE
) -> list[ScoredOutfit]:
    """Signature unchanged; default parameter value changes. Any caller
    passing an explicit strategy (none currently do in production code) is
    unaffected."""
```

## `whattowear.pipeline.graph`

```python
def wardrobe_retrieval(state: GraphState) -> dict:
    """Unchanged signature and return shape ({"candidates": dict[str,
    list[WardrobeItem]]}). Internal change only: candidates are sorted by
    fitness before the existing _CANDIDATES_PER_SLOT slice, so which items
    survive the cap can change, but the shape of the output does not."""
```

## Consumers relying on these signatures (verified stable across this change)

- `whattowear.scoring.score_outfits` (`scoring/__init__.py`) — calls
  `color_harmony.score(...)` as one of `DIMENSION_SCORERS`, then
  `combine.rank_outfits(...)` with no explicit strategy arg (so it picks up
  the new default automatically — this is the intended behavior change).
- `whattowear.eval.harness` — imports `scoring.score_outfits` unchanged
  (constitution Principle V: same call site, no fork).
- `whattowear.pipeline.graph`'s own `score_and_rank` node — same
  `score_outfits` call site.
