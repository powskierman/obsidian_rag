"""
prompt_overrides.py — vault-specific prompt tuning for LightRAG indexing.

Overrides the stock HKUDS/LightRAG extraction prompts for two purposes:

  1. Fit a smaller local model — Gemma-4-26B-A4B (4-bit MLX) served via
     LMStudio on an M4 Max with 36 GB. Smaller models do better with
     short, direct system prompts and compact few-shot examples.

  2. Fit THIS vault's topic mix — software/AI engineering, home-automation
     hardware (ESP32, HomeKit), medical self-tracking (lymphoma, CT scans,
     CAR-T), reading notes, and recipes. Default LightRAG entity types
     (organization, person, geo, event) bleed everything into "concept"
     or "event" on a personal KB — we need concrete types.

---------------------------------------------------------------
Deployment (3 steps)
---------------------------------------------------------------

1. Add a COPY line to Dockerfile.lightrag (alongside the other override
   COPYs), so this module lands inside the LightRAG package tree:

     COPY src/lightrag_overrides/lightrag/prompt_overrides.py \\
          ./LightRAG/lightrag/prompt_overrides.py

2. In src/lightrag_overrides/lightrag/operate.py, AFTER the existing
   `from lightrag.constants import (...)` block (i.e. after line 74),
   insert:

     # --- Vault-specific prompt + entity-type overrides (idempotent) ---
     try:
         from lightrag import prompt_overrides as _vault_overrides
         _vault_overrides.apply_overrides(PROMPTS)
         DEFAULT_ENTITY_TYPES = _vault_overrides.VAULT_ENTITY_TYPES
     except ImportError:
         pass  # Overrides not deployed; fall back to upstream defaults.

3. Rebuild + force-recreate the service:

     cd /Users/michel/dev/obsidian_rag
     docker compose up -d --build --force-recreate lightrag-service

---------------------------------------------------------------
Tuning notes
---------------------------------------------------------------

* `entity_types` trimmed to 10 concrete types. Gemma-scale models pick
  the wrong type less often with a short, non-overlapping list.
* System prompt adds explicit SKIP rules for YAML frontmatter, dataview
  blocks, tag tokens, and raw URLs — the big noise sources on MD notes.
* Three short few-shot examples span three of the vault's actual
  domains (tech, medical, recipe). Upstream ships five long examples
  that balloon the prompt past 2 K tokens.
* The output format — `("entity"<|#|>name<|#|>type<|#|>description)` with
  `<|COMPLETE|>` terminator — matches what operate.py's parser expects
  (see `_handle_single_entity_extraction` and
  `_handle_single_relationship_extraction`). Do NOT change it without
  also adjusting the parser.
* Temperature 0.1 at inference is a good match: with these terse
  examples and rules, the model doesn't need to improvise — it just
  fills the template.
"""

from __future__ import annotations

# =====================================================================
# 1. Entity types — curated for this vault
# =====================================================================

VAULT_ENTITY_TYPES = [
    "person",          # doctors, authors, colleagues, friends, family
    "organization",    # companies, hospitals, publishers, research groups
    "location",        # geographic places, physical venues
    "technology",      # software, frameworks, protocols, models, algorithms
    "device",          # specific hardware (ESP32, router, sensor, appliance)
    "medical_term",    # conditions, treatments, medications, procedures
    "concept",         # abstract ideas, theories, methodologies, patterns
    "creative_work",   # books, articles, papers, movies, podcasts, shows
    "recipe_or_food",  # recipes, dishes, ingredients, techniques
    "project",         # named projects (Mempalace, obsidian_rag, Cresnet)
]

# =====================================================================
# 2. System prompt — sets the role, rules, output format
# =====================================================================

VAULT_ENTITY_EXTRACTION_SYSTEM_PROMPT = """---Role---
You extract entities and relationships from Obsidian markdown notes so they can be indexed in a local knowledge graph. The notes come from a single person's personal knowledge base spanning software/AI engineering, home-automation hardware, medical self-tracking, reading notes, and recipes.

---Goal---
Identify concrete entities and the explicit relationships among them. Output records in the exact format defined below. Do not add commentary, preambles, or explanations.

---Entity Types---
Restrict extractions to these types (use the type string verbatim):
{entity_types}

---Extraction Rules---
1. Extract ONLY named, concrete entities that appear in the text. Skip pronouns, hedges ("the thing", "something"), and generic category words unless they name a specific referent.
2. SKIP content that is:
   - YAML frontmatter between `---` fences at the top of a note
   - Auto-generated tables of contents, dataview code blocks, and bare `[[wikilink]]` dumps without surrounding prose
   - Raw URLs, file paths, and code imports — unless the referent itself is the subject of discussion
   - Tag tokens such as `#projects/mempalace` — extract what the tag categorizes, not the literal tag string
3. Use the most specific name available ("Gemma-4-26B-A4B" over "LLM"; "ESP32-S3" over "microcontroller"; "CAR-T therapy" over "cancer treatment").
4. If an acronym is expanded once in the text, record the expanded form; otherwise use the acronym as written.
5. ALWAYS extract relationships between entities that you extract. A relationship is warranted whenever the text establishes a connection between two entities — whether stated directly ("X uses Y"), implied by the sentence structure ("X, built on Y,..."), or implied by the document structure (a heading followed by a list of related items, a bulleted spec list under a component name, an ingredients list under a recipe name). Favor emitting a relationship over dropping one; downstream merging will deduplicate. Aim for at least one relationship per two entities whenever the text plausibly supports it.
6. All output text MUST be in {language}.

---Output Format (CRITICAL)---
Emit records in this exact format. EACH RECORD MUST APPEAR ON ITS OWN LINE, terminated with `)` followed by a newline. Do NOT concatenate multiple records on the same line. Do NOT omit the newline between records.

Entity record (one per line):
("entity"{tuple_delimiter}<entity_name>{tuple_delimiter}<entity_type>{tuple_delimiter}<one-sentence description drawn from the text>)

Relationship record (one per line):
("relationship"{tuple_delimiter}<source_entity_name>{tuple_delimiter}<target_entity_name>{tuple_delimiter}<short keyword phrase for the relation type>{tuple_delimiter}<one-sentence description of how they relate>)

Ordering: emit all entity records first, then all relationship records, each on its own line. After the final record, emit {completion_delimiter} alone on its own line. If the text yields no extractable entities, emit only {completion_delimiter}.

---Few-Shot Examples---
{examples}
"""

# =====================================================================
# 3. User prompt — injects the actual chunk content
# =====================================================================

VAULT_ENTITY_EXTRACTION_USER_PROMPT = """---Text---
{input_text}

---Reminders---
- Emit every entity record and every relationship record on its own line, terminated by `)` and a newline.
- Extract BOTH entities and relationships. If you extracted N entities, you should typically emit at least N/2 relationships among them whenever the text supports it.
- End with {completion_delimiter} on its own line.

---Output---
"""

# =====================================================================
# 4. Continue-extraction prompt — used when the first pass looks truncated
# =====================================================================

VAULT_ENTITY_CONTINUE_EXTRACTION_USER_PROMPT = """The previous extraction likely missed some entities and — especially — relationships between the entities you already emitted. Re-read the text and emit ONLY records that were NOT already produced, in the identical format, each on its own line.

Focus this pass on:
- Relationships connecting entities that appeared in the previous output but without a relationship record linking them.
- Entities mentioned in the text but absent from the previous output.

Do not repeat records you already emitted. End with {completion_delimiter} on its own line.

---Text (unchanged)---
{input_text}

---Additional Output---
"""

# =====================================================================
# 5. Few-shot examples — compact, pulled from three of the vault's domains
#    Each string is .format()ed with the same context vars as the system
#    prompt (tuple_delimiter, completion_delimiter, entity_types, language).
# =====================================================================

_EXAMPLE_TECH = """Example 1 — tech note:
Text:
"Installed LightRAG on Canmore for the obsidian_rag project. LightRAG is a Retrieval-Augmented Generation framework from HKUDS that builds a knowledge graph from plain text. Pinned to commit 324242ac in the repo."

Output:
("entity"{tuple_delimiter}LightRAG{tuple_delimiter}technology{tuple_delimiter}Retrieval-Augmented Generation framework from HKUDS that builds a knowledge graph from plain text.)
("entity"{tuple_delimiter}Canmore{tuple_delimiter}device{tuple_delimiter}The machine on which LightRAG was installed for the obsidian_rag project.)
("entity"{tuple_delimiter}obsidian_rag{tuple_delimiter}project{tuple_delimiter}Personal project that indexes an Obsidian vault using LightRAG.)
("entity"{tuple_delimiter}HKUDS{tuple_delimiter}organization{tuple_delimiter}Research group that publishes LightRAG.)
("relationship"{tuple_delimiter}LightRAG{tuple_delimiter}obsidian_rag{tuple_delimiter}dependency-of{tuple_delimiter}LightRAG is the RAG framework the obsidian_rag project is built on.)
("relationship"{tuple_delimiter}LightRAG{tuple_delimiter}HKUDS{tuple_delimiter}published-by{tuple_delimiter}LightRAG is developed and published by HKUDS.)
("relationship"{tuple_delimiter}LightRAG{tuple_delimiter}Canmore{tuple_delimiter}installed-on{tuple_delimiter}LightRAG was installed on the Canmore machine.)
{completion_delimiter}
"""

_EXAMPLE_MEDICAL = """Example 2 — medical note:
Text:
"Saw Dr. Tremblay on March 14 about the CT scan follow-up. He recommended a CAR-T consultation at the Princess Margaret Cancer Centre given the lymphoma recurrence. Started tracking bone density monthly."

Output:
("entity"{tuple_delimiter}Dr. Tremblay{tuple_delimiter}person{tuple_delimiter}Treating physician consulted on March 14 regarding CT scan follow-up.)
("entity"{tuple_delimiter}CAR-T therapy{tuple_delimiter}medical_term{tuple_delimiter}Cancer treatment under consideration because of the lymphoma recurrence.)
("entity"{tuple_delimiter}Princess Margaret Cancer Centre{tuple_delimiter}organization{tuple_delimiter}Hospital recommended for a CAR-T consultation.)
("entity"{tuple_delimiter}lymphoma{tuple_delimiter}medical_term{tuple_delimiter}Diagnosed condition with a documented recurrence.)
("entity"{tuple_delimiter}bone density{tuple_delimiter}medical_term{tuple_delimiter}Health metric the author is tracking monthly.)
("relationship"{tuple_delimiter}Dr. Tremblay{tuple_delimiter}CAR-T therapy{tuple_delimiter}recommended{tuple_delimiter}Dr. Tremblay recommended evaluating CAR-T therapy for the patient.)
("relationship"{tuple_delimiter}CAR-T therapy{tuple_delimiter}Princess Margaret Cancer Centre{tuple_delimiter}delivered-at{tuple_delimiter}The recommended CAR-T consultation would happen at the Princess Margaret Cancer Centre.)
("relationship"{tuple_delimiter}lymphoma{tuple_delimiter}CAR-T therapy{tuple_delimiter}treated-by{tuple_delimiter}CAR-T therapy is being considered to treat the lymphoma recurrence.)
{completion_delimiter}
"""

_EXAMPLE_RECIPE = """Example 3 — recipe note:
Text:
"Coq-au-Vin — Julia Child's version. Braise chicken thighs in Burgundy with pearl onions, lardons, and cremini mushrooms. Serves four. Pairs well with a Pinot Noir."

Output:
("entity"{tuple_delimiter}Coq-au-Vin{tuple_delimiter}recipe_or_food{tuple_delimiter}Classic French chicken braise using Burgundy wine, pearl onions, lardons, and cremini mushrooms; serves four.)
("entity"{tuple_delimiter}Julia Child{tuple_delimiter}person{tuple_delimiter}Author of the specific Coq-au-Vin recipe being followed.)
("entity"{tuple_delimiter}Burgundy{tuple_delimiter}recipe_or_food{tuple_delimiter}Red wine used as the braising liquid in this recipe.)
("entity"{tuple_delimiter}Pinot Noir{tuple_delimiter}recipe_or_food{tuple_delimiter}Wine suggested as the pairing for the dish.)
("relationship"{tuple_delimiter}Coq-au-Vin{tuple_delimiter}Julia Child{tuple_delimiter}authored-by{tuple_delimiter}The recipe followed is Julia Child's version of Coq-au-Vin.)
("relationship"{tuple_delimiter}Coq-au-Vin{tuple_delimiter}Burgundy{tuple_delimiter}ingredient-of{tuple_delimiter}Burgundy wine is one of the braising liquids in the recipe.)
("relationship"{tuple_delimiter}Coq-au-Vin{tuple_delimiter}Pinot Noir{tuple_delimiter}paired-with{tuple_delimiter}Pinot Noir is the suggested wine pairing.)
{completion_delimiter}
"""

VAULT_ENTITY_EXTRACTION_EXAMPLES = [_EXAMPLE_TECH, _EXAMPLE_MEDICAL, _EXAMPLE_RECIPE]

# =====================================================================
# 6. Summarization prompt — merging multiple descriptions of one entity
# =====================================================================

VAULT_SUMMARIZE_ENTITY_DESCRIPTIONS = """You are merging multiple descriptions of the same knowledge-graph {description_type} into a single coherent one.

---{description_type}---
{description_name}

---Existing descriptions---
{description_list}

---Instructions---
1. Produce ONE concise description of roughly {summary_length} words (1-3 sentences) that preserves every distinct fact across the inputs.
2. When inputs contradict, keep the more specific or more recent claim and drop vaguer phrasing.
3. Do NOT add information that is not in the inputs.
4. Do NOT use bullet points, headers, or markdown formatting. Return plain prose.
5. Output MUST be in {language}.

---Merged description---
"""

# =====================================================================
# 7. Application helper — call from operate.py
# =====================================================================

def apply_overrides(prompts: dict) -> None:
    """Mutate the given PROMPTS dict in place with vault-specific overrides.

    Only the indexing-time prompts are replaced. Query-time prompts
    (rag_response, naive_rag_response, keywords_extraction, etc.) are left
    at their upstream values so general-purpose retrieval behavior is
    unchanged.
    """
    prompts["entity_extraction_system_prompt"] = VAULT_ENTITY_EXTRACTION_SYSTEM_PROMPT
    prompts["entity_extraction_user_prompt"] = VAULT_ENTITY_EXTRACTION_USER_PROMPT
    prompts["entity_continue_extraction_user_prompt"] = VAULT_ENTITY_CONTINUE_EXTRACTION_USER_PROMPT
    prompts["entity_extraction_examples"] = VAULT_ENTITY_EXTRACTION_EXAMPLES
    prompts["summarize_entity_descriptions"] = VAULT_SUMMARIZE_ENTITY_DESCRIPTIONS
