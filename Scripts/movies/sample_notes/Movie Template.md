<%*
const title = await tp.system.prompt("Title", "", true);
const year = await tp.system.prompt("Year (blank if unknown)", "");
const director = await tp.system.prompt("Director (blank if unknown)", "");
const genresRaw = await tp.system.prompt("Genres (comma-separated)", "");
const provenance = await tp.system.suggester(["NAS", "Apple", "Apple + NAS"], ["NAS", "Apple", "Apple + NAS"], true, "Provenance?");
const mood = await tp.system.prompt("Mood (optional)", "");
const energy = await tp.system.suggester(["", "low", "medium", "high"], ["", "low", "medium", "high"], false, "Energy?");
const watchContext = await tp.system.prompt("Watch context (optional)", "");

const slugify = s => s.toLowerCase()
  .replace(/['']/g, "")
  .replace(/[^a-z0-9]+/g, "-")
  .replace(/^-|-$/g, "");

const titleSlug = slugify(title);
const yearSuffix = year ? `-${year}` : "";
const id = `mov-${titleSlug}${yearSuffix}`;
const genres = genresRaw.split(",").map(g => g.trim()).filter(Boolean);
const qualityApple = (provenance === "Apple" || provenance === "Apple + NAS") ? "HD" : "null";
const qualityNas = (provenance === "NAS" || provenance === "Apple + NAS") ? "unknown" : "null";

await tp.file.rename(title);
-%>
---
id: <% id %>
kind: movie
title: "<% title %>"
year: <% year || "null" %>
imdb_id: null
tmdb_id: null
jellyfin_item_id: null
jellyfin_path: null
jellyfin_url: null
director: <% director ? `"${director}"` : "null" %>
genre:
<%* if (genres.length) { for (const g of genres) { tR += `  - ${g}\n`; } } else { tR += "  - Unknown\n"; } %>
runtime_min: null
content_rating: null
imdb_rating: null
description: null
poster_url: null
your_rating: null
watched: null
shortlist: false
mood: <% mood ? `"${mood}"` : "null" %>
energy: <% energy ? `"${energy}"` : "null" %>
watch_context: <% watchContext ? `"${watchContext}"` : "null" %>
rewatchable: false
avoid_if: null
provenance: <% provenance %>
collection: null
quality_apple: <% qualityApple %>
quality_nas: <% qualityNas %>
top_250: false
imdb_top_250_rank: null
match_status: unresolved
version_notes: null
streaming_ca: "Check JustWatch CA"
created: <% tp.date.now("YYYY-MM-DD") %>
tags:
  - movie
<%* for (const g of genres) { tR += `  - ${slugify(g)}\n`; } %>
---

## Why Watch

- 

## Best For

- Mood: <% mood || "" %>
- Company: <% watchContext || "" %>
- Time/Energy: <% energy || "" %>

## Avoid If

- 

## Notes

- 
