#!/usr/bin/env python3
"""
Process Inbox - The AI Loop for Second Brain.

Watches the Inbox folder for new files, processes them using LLM to:
1. Summarize (TL;DR)
2. Format (New Note Template)
3. Tag & Classify
4. Move to appropriate location
"""

import os
import sys
import time
import json
import shutil
import logging
from pathlib import Path
from typing import Dict, Optional
import yaml
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Import existing logic where possible
# from services.llm_service import LLMService  # Removed: Service does not exist yet
# Note: In a real implementation, we would import specific functions from 
# apply_new_note_template.py, classify_folders.py etc. to reuse code.
# For this script, we'll implement a consolidated flow.

# Configuration
VAULT_PATH = Path(os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'))
INBOX_PATH = VAULT_PATH / "00_Inbox"
TEMPLATE_PATH = VAULT_PATH / "Templates/New Note Template.md"
PROCESSED_LOG = Path("inbox_processed.log")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class InboxHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith('.md'):
            return
            
        logger.info(f"New file detected: {event.src_path}")
        # Give some time for file write to complete
        time.sleep(2)
        process_inbox_file(Path(event.src_path))

def process_inbox_file(file_path: Path):
    """Main processing logic for a single file."""
    try:
        logger.info(f"Processing {file_path.name}...")
        
        # 1. Read Content
        content = file_path.read_text(encoding='utf-8')
        if not content.strip():
            logger.warning("Empty file, skipping.")
            return

        # 2. AI Analysis (Mocked for now, replace with actual LLM call)
        # In production, this would call Claude/GPT to analyze the content
        analysis = analyze_content_with_llm(content)
        
        # 3. Format Content
        formatted_content = apply_template(content, analysis)
        
        # 4. Determine Destination
        target_folder = VAULT_PATH / analysis.get('folder', 'Inbox_Processed')
        target_folder.mkdir(parents=True, exist_ok=True)
        
        target_filename = analysis.get('filename', file_path.name)
        if not target_filename.endswith('.md'):
            target_filename += '.md'
            
        target_path = target_folder / target_filename
        
        # Handle duplicates
        if target_path.exists():
            timestamp = int(time.time())
            target_path = target_folder / f"{target_path.stem}_{timestamp}.md"
            
        # 5. Write and Move
        target_path.write_text(formatted_content, encoding='utf-8')
        logger.info(f"Saved formatted note to: {target_path}")
        
        # Remove original from Inbox
        os.remove(file_path)
        logger.info(f"Removed original file from Inbox.")
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")

def analyze_content_with_llm(content: str) -> Dict:
    """
    Analyze content using LLM to extract metadata and structure.
    Returns a dict with: main_idea, summary, tags, folder, filename
    """
    # TODO: Implement actual LLM call here.
    # For now, we use heuristic/dummy data to demonstrate the flow.
    
    lines = content.strip().split('\n')
    title = lines[0].replace('#', '').strip()
    
    return {
        'main_idea': f"Summary of {title}",
        'folder': 'Notes', # Default fallback
        'tags': ['auto-captured'],
        'filename': f"{title}.md"
    }

def apply_template(original_content: str, analysis: Dict) -> str:
    """Apply the New Note Template structure."""
    # This roughly mimics apply_new_note_template.py but uses LLM analysis
    
    frontmatter = {
        'created': time.strftime('%Y-%m-%d %H:%M'),
        'tags': analysis.get('tags', []),
        'ContentType': 'Note'
    }
    
    fm_yaml = yaml.dump(frontmatter, sort_keys=False)
    
    body = f"""---
{fm_yaml}---

### Main Idea
- {analysis.get('main_idea', 'No summary available.')}

### Notes
{original_content}

### References
-

### Related Notes
-

"""
    return body

def main():
    if not INBOX_PATH.exists():
        INBOX_PATH.mkdir(parents=True, exist_ok=True)
        logger.info(f"Created Inbox at {INBOX_PATH}")
    
    # Process existing files on startup
    logger.info("Checking for existing files in Inbox...")
    for existing_file in INBOX_PATH.glob('*.md'):
        process_inbox_file(existing_file)
        
    logger.info(f"Watching {INBOX_PATH} for new files...")
    
    observer = Observer()
    observer.schedule(InboxHandler(), str(INBOX_PATH), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()

if __name__ == "__main__":
    main()
