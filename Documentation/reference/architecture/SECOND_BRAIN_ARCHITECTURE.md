# Second Brain Architecture for Obsidian RAG

## Overview
This document outlines the architecture for a "Second Brain" system within the Obsidian RAG environment, inspired by Nate Jones's "Active vs. Passive Systems" concept. The goal is to move from a passive storage system to an active "AI Loop" that processes frictionless inputs into structured, valuable knowledge.

## Core Philosophy
1.  **Frictionless Capture:** Capture thoughts, web clips, and data without deciding where they go or how to format them.
2.  **AI Loop (The Factory):** An automated process that runs in the background to:
    *   **Summarize:** Create a point-form TL;DR.
    *   **Format:** Apply the standard "New Note Template".
    *   **Classify:** Route to the appropriate folder.
    *   **Tag:** Apply relevant tags and backlinks.
3.  **Review:** The user only sees the final, polished output.

## Architecture

### 1. The Inputs (Frictionless Capture)
All inputs are directed to a single `00_Inbox` folder in the Vault.

*   **Quick Capture (Web App):** A simple text area in the WebApp for brain dumps.
*   **Web Clipper:** Browser extension saving Markdown to `00_Inbox`.
*   **Mobile App:** Obsidian Mobile saving to `00_Inbox`.
*   **Voice:** Audio recordings transcribed (via Whisper/Apple Intelligence) and saved to `00_Inbox`.
*   **File Drop:** Simply dropping PDFs or images into `00_Inbox`.

### 2. The Processor (The AI Loop)
A background service (Python script) monitors `00_Inbox`. When a new file is detected:

1.  **Read & Analyze:**
    *   Read content.
    *   **LLM Step (Claude/GPT):**
        *   Generate **Main Idea** (TL;DR).
        *   Extract **Metadata** (Tags, ContentType, Suggested Folder).
        *   Format content into the **New Note Template** structure.
2.  **Enrich (Existing Scripts):**
    *   *Optional:* Run `generate_tags.py` logic for deeper semantic tagging (using Knowledge Graph/ChromaDB).
    *   *Optional:* Run `classify_folders.py` logic for validation or fallback if LLM is unsure.
3.  **Execute:**
    *   **Rename:** Ensure filename is descriptive (LLM can suggest title).
    *   **Write:** Overwrite with formatted content.
    *   **Move:** Move from `00_Inbox` to the target folder (e.g., `Tech/AI`, `Medical`, `Reference`).

### 3. The Output (Storage)
*   **Formatted Note:** Clean Markdown with YAML frontmatter, headers, and bullet points.
*   **Location:** Correctly filed in the Vault hierarchy.
*   **Connection:** Linked to related notes (via extracted wikilinks) and tagged.

## Implementation Specifications

### 1. Folder Structure
Ensure the following exists:
```
Vault/
├── 00_Inbox/          <-- The Catch-all
├── Templates/
│   └── New Note Template.md
├── Tech/
├── Medical/
├── Reference/
└── ...
```

### 2. The `process_inbox.py` Script
A new script responsible for the AI Loop.

**Logic:**
```python
def process_file(file_path):
    content = read_file(file_path)
    
    # AI Processing
    analysis = llm.analyze(content) # Returns JSON with summary, tags, folder, formatted_body
    
    # Construct New Content
    new_content = apply_template(analysis, template_path)
    
    # Move
    target_path = validate_path(analysis['folder'], analysis['filename'])
    move_file(file_path, target_path, new_content)
```

### 3. Web App Quick Capture
Add a "Capture" tab/page to the `webapp` (Next.js).
*   **UI:** Text Area + "Capture" Button.
*   **Action:** POST to a local API endpoint that writes text to `Vault/00_Inbox/Timestamp_Note.md`.

## Implementation Plan

1.  **Setup:**
    *   Create `00_Inbox` folder.
    *   Verify `New Note Template.md` availability.

2.  **Develop `process_inbox.py`:**
    *   Implement `InboxWatcher` class.
    *   Implement `LLMProcessor` using existing `src/services` or direct API calls.
    *   Integrate logic from `apply_new_note_template.py` (formatting) and `classify_folders.py` (routing).

3.  **Integration:**
    *   Update `start_watcher.sh` to run `process_inbox.py` in the background.
    *   Add "Quick Capture" page to the WebApp.

4.  **Testing:**
    *   Test with raw text (brain dump).
    *   Test with a pasted article.
    *   Verify formatting, tagging, and folder placement.
