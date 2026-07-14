"""Wikipedia HTML -> clean Markdown refiner.

Workflow: save a Wikipedia page complete (HTML + assets folder) from a browser,
then run this script to produce a clean `.md` file next to it. The `.md` is
what gets ingested (via the `wiki_md` loader) — no live network dependency,
fully reviewable/diffable, reproducible.

Kept: body prose, headings, lists, images (path preserved, pointing at the
saved assets folder) with their captions, in their original position.
Dropped: "See also", "Notes", "References", "Citations", "External links",
"Further reading", "Bibliography" sections (and their [edit] links); navboxes,
infoboxes, hatnotes, category footers, citation footnote markers — chrome that
isn't part of the running text.

Verified against real Wikipedia (Vector 2022 skin) HTML: headings are wrapped
`<div class="mw-heading mw-heading2"><h2>...<span class="mw-editsection">`,
images are `<figure typeof="mw:File/Thumb"><img><figcaption>` (or the older
`<div class="thumb">...<div class="thumbcaption">` form for multi-image thumbs).
"""

from __future__ import annotations

import re
from pathlib import Path

from bs4 import BeautifulSoup
from markdownify import markdownify

from ..logging_utils import get_logger

log = get_logger(__name__)

SKIP_SECTION_TITLES = {
    "see also", "notes", "references", "notes and references", "citations",
    "notes and citations", "external links", "further reading", "bibliography",
    "sources", "footnotes", "gallery", "works cited", "explanatory notes",
    "notes and sources", "further information",
}

# chrome selectors removed wholesale before conversion (not part of the running text)
_STRIP_SELECTORS = [
    "script", "style", ".mw-editsection", ".hatnote", ".navbox", ".vertical-navbox",
    ".infobox", ".ambox", ".dmbox", ".tmbox", ".ombox", ".cmbox", ".metadata",
    ".reflist", ".catlinks", ".printfooter", ".mw-jump-link", ".noprint",
    ".sistersitebox", "table.metadata",
]


_HEADING_RE = re.compile(r"^h[1-6]$")


def _own_section_heading_text(section) -> str:
    """The heading title belonging directly to this <section> — NOT a nested
    subsection's. MediaWiki (Vector 2022) nests subsections as <section>
    children of their parent section, each wrapped
    <div class="mw-heading mw-headingN"><hN>...— so `recursive=False` on the
    heading-wrapper search is what keeps this scoped to the section's own
    heading instead of diving into its children."""
    # NOTE: bs4 calls a `class_` callable once PER individual class string, not
    # once with the full class list — so this must check a single string, not
    # iterate `c` as if it were the whole list (that was a real bug: iterating
    # over a string yields its characters, so the old `any(... for cl in c)`
    # never matched anything).
    wrap = section.find("div", class_=lambda c: c and c.startswith("mw-heading"), recursive=False)
    if wrap:
        h = wrap.find(_HEADING_RE)
        if h:
            return h.get_text(strip=True)
    h = section.find(_HEADING_RE, recursive=False)  # fallback: bare heading, older skin
    return h.get_text(strip=True) if h else ""


def _strip_chrome(root) -> None:
    for sel in _STRIP_SELECTORS:
        for el in root.select(sel):
            el.decompose()
    for sup in root.find_all("sup", class_=lambda c: c == "reference"):
        sup.decompose()


def _clean_text_no_magnify(el) -> str:
    """get_text(separator=' ') is needed for correctly spaced word boundaries
    across tags (e.g. a linked name immediately followed by more prose), but it
    over-inserts a space before a directly-attached possessive/punctuation
    (e.g. "Goethe 's", "Dujon ,") — collapse just those artifacts back out."""
    copy = BeautifulSoup(str(el), "html.parser")
    for m in copy.select(".magnify"):
        m.decompose()
    text = copy.get_text(" ", strip=True)
    return re.sub(r"\s+('s\b|[,.;:!?)])", r"\1", text)


def _replace_image_blocks(root) -> None:
    """Collapse each image block (figure/thumb, possibly multi-image) into a
    plain <p><img></p><p><em>caption</em></p> pair, in place — guarantees
    correct, predictable markdown regardless of Wikipedia's wrapper markup, and
    keeps the image positioned exactly where it appeared in the prose."""
    candidates = root.select("figure, div.thumb")
    # drop nodes nested inside another candidate (avoid double-processing e.g.
    # a <figure> inside a multi-image <div class="thumb">). Uses `is` (identity)
    # deliberately — BeautifulSoup elements compare by structural equality, so
    # `in o.descendants` would misfire on duplicate-looking sibling figures.
    top_level = [
        c for c in candidates
        if not any(c is not o and any(c is d for d in o.descendants) for o in candidates)
    ]
    for node in top_level:
        imgs = node.find_all("img")
        if not imgs:
            node.decompose()
            continue
        captions = [_clean_text_no_magnify(c) for c in node.find_all("figcaption")]
        if not captions:
            captions = [_clean_text_no_magnify(c) for c in node.find_all(class_="thumbcaption")]
        parts = []
        for i, img in enumerate(imgs):
            src = img.get("src") or img.get("data-src") or ""
            if not src:
                continue
            src = src[2:] if src.startswith("./") else src
            cap = captions[i] if i < len(captions) else (captions[0] if len(captions) == 1 else "")
            alt = (img.get("alt") or "").strip() or cap or "image"
            parts.append(f'<p><img src="{src}" alt="{alt}"></p>')
            if cap:
                parts.append(f"<p><em>{cap}</em></p>")
        node.replace_with(BeautifulSoup("".join(parts), "html.parser"))


def _drop_skip_sections(root) -> None:
    """Drop every <section> whose OWN heading is skip-listed ('See also',
    'References', 'Notes', 'External links', ...).

    Verified against real saved pages: MediaWiki's Vector 2022 output wraps
    each heading's content in a <section>, and nests subsections as <section>
    children of their parent section (a tree, not flat heading/paragraph
    siblings). Decomposing a section removes everything nested inside it too,
    so this naturally also drops any (rare) skip-listed subsection."""
    for section in root.find_all("section"):
        if getattr(section, "decomposed", False):
            continue  # already removed as part of an ancestor section
        title = _own_section_heading_text(section).lower()
        if title in SKIP_SECTION_TITLES:
            section.decompose()


def _get_title(soup: BeautifulSoup) -> str:
    h1 = soup.select_one("#firstHeading")
    if h1:
        return h1.get_text(strip=True)
    if soup.title:
        return soup.title.get_text(strip=True).removesuffix(" - Wikipedia")
    return "Untitled"


def refine_html(html_path: Path) -> tuple[str, str]:
    """Returns (title, markdown)."""
    raw = html_path.read_text(encoding="utf-8", errors="ignore")
    soup = BeautifulSoup(raw, "html.parser")
    title = _get_title(soup)

    content = soup.select_one("#mw-content-text .mw-parser-output") or soup.select_one(".mw-parser-output")
    if content is None:
        log.warning("no .mw-parser-output found in %s; falling back to <body>", html_path.name)
        content = soup.body or soup

    _strip_chrome(content)
    _replace_image_blocks(content)
    _drop_skip_sections(content)

    # strip=["a"]: drop inline hyperlinks to plain text — cross-reference URLs
    # are retrieval noise, not part of the running prose (citations/provenance
    # are tracked separately via chunk metadata, not embedded links).
    md = markdownify(str(content), heading_style="ATX", bullets="-", strip=["span", "a"])
    md = re.sub(r"\n{3,}", "\n\n", md).strip()
    md = f"<!-- refined from: {html_path.name} -->\n\n# {title}\n\n{md}\n"
    return title, md


def refine_file(html_path: Path, output_path: Path | None = None) -> Path:
    output_path = output_path or html_path.with_suffix(".md")
    title, md = refine_html(html_path)
    output_path.write_text(md, encoding="utf-8")
    log.info("refined %r -> %s (%d chars)", title, output_path, len(md))
    return output_path


if __name__ == "__main__":
    import argparse

    from ..logging_utils import configure_logging

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("html", nargs="+", type=Path, help="saved Wikipedia .html file(s)")
    ap.add_argument("-o", "--output", type=Path, help="output .md path (only valid for a single input file)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()
    configure_logging(args.verbose)

    if args.output and len(args.html) > 1:
        raise SystemExit("--output only supported for a single input file")
    for html_path in args.html:
        refine_file(html_path, args.output)
