<%*
// ── Movie Note Template ────────────────────────────────────────────────
// Requires: Templater plugin
// Save to: Templates/Movie Template.md
// Usage:   New note → "Movie Template" → fills prompts → note created
// ──────────────────────────────────────────────────────────────────────

// ── 1. Collect inputs ─────────────────────────────────────────────────
const title       = await tp.system.prompt("Title", "", true);
const year        = await tp.system.prompt("Year (blank if unknown)", "");
const director    = await tp.system.prompt("Director (blank if unknown)", "");
const genresRaw   = await tp.system.prompt("Genres (comma-separated)", "Drama");
const runtime     = await tp.system.prompt("Runtime (min, blank if unknown)", "");
const imdbRating  = await tp.system.prompt("IMDb rating (blank if unknown)", "");
const provenance  = await tp.system.suggester(["NAS", "Apple", "Both"], ["NAS", "Apple", "Both"], true, "Provenance?");
const description = await tp.system.prompt("Short description (1–2 sentences)", "");

// ── 2. Derive computed fields ─────────────────────────────────────────
// Slug: lowercase, collapse non-alphanum to hyphens, trim ends
const slugify = s => s.toLowerCase()
  .replace(/['']/g, "")
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-|-$/g, "");

const titleSlug  = slugify(title);
const yearSuffix = year ? `-${year}` : "";
const id         = `mov-${titleSlug}${yearSuffix}`;

// Genres array
const genres = genresRaw.split(",").map(g => g.trim()).filter(Boolean);
const genre1 = genres[0] ?? "uncategorised";
const genre2 = genres[1] ?? null;

// Quality flags based on provenance
const qualityApple = (provenance === "Apple" || provenance === "Both") ? "HD" : "null";
const qualityNas   = (provenance === "NAS"   || provenance === "Both") ? "unknown" : "null";

// Rename the note file to the movie title
await tp.file.rename(title);
-%>
---
id: mov-<% titleSlug %><% yearSuffix %>
kind: movie
title: "<% title %>"
year: <% year || "null" %>
imdb_id: null
tmdb_id: null
directors:
  - <% director || "null" %>
cast: []
genres:
<%* for (const g of genres) { tR += `  - ${g}\n`; } %>
runtime_min: <% runtime || "null" %>
content_rating: null
imdb_rating: <% imdbRating || "null" %>
your_rating: null
watched: false
last_watched: null
watched_dates: []
provenance: <% provenance %>
collection: null
quality_apple: <% qualityApple %>
quality_nas: <% qualityNas %>
top_250: false
imdb_top_250_rank: null
match_status: unresolved
version_notes: null
streaming_ca: "Check JustWatch CA"
poster:
  source: null
  path: null
description: >-
  <% description || "No description yet." %>
created: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - movie
<%* for (const g of genres) { tR += `  - genre/${slugify(g)}\n`; } %>
---

## Notes

<!-- User notes — preserved across pipeline reruns -->

<%* if (!description) { -%>
> ⚠️ No description yet — add one manually or run the enrichment pipeline.
<%* } %>
