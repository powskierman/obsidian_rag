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
from queue import Queue
from threading import Thread

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

# Configuration
VAULT_PATH = Path(os.getenv('OBSIDIAN_VAULT_PATH', '/Users/michel/Library/Mobile Documents/iCloud~md~obsidian/Documents/Michel'))
INBOX_PATH = VAULT_PATH / "00_Inbox"
TEMPLATE_PATH = VAULT_PATH / "Templates/New Note Template.md"
PROCESSED_LOG = Path("inbox_processed.log")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Processing Queue
file_queue = Queue()

class InboxHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        if not event.src_path.endswith('.md'):
            return
            
        logger.info(f"New file detected: {event.src_path}")
        # Add to queue instead of processing directly
        file_queue.put(Path(event.src_path))

def worker():
    """Worker thread to process files from the queue."""
    while True:
        file_path = file_queue.get()
        if file_path is None:
            break
            
        # Wait a bit for file write to complete (debounce)
        time.sleep(2)
        
        try:
            if file_path.exists():
                process_inbox_file(file_path)
            else:
                logger.warning(f"File vanished before processing: {file_path}")
        except Exception as e:
            logger.error(f"Error in worker for {file_path}: {e}")
        finally:
            file_queue.task_done()

def process_inbox_file(file_path: Path):
    """Main processing logic for a single file."""
    try:
        logger.info(f"Processing {file_path.name}...")
        
        # 1. Read Content
        # Use a retry mechanism for reading in case of file locks
        content = ""
        retries = 3
        while retries > 0:
            try:
                content = file_path.read_text(encoding='utf-8')
                break
            except OSError:
                retries -= 1
                time.sleep(1)
        
        if not content and retries == 0:
            logger.error(f"Failed to read file: {file_path}")
            return

        if not content.strip():
            logger.warning("Empty file, skipping.")
            return

        # 2. AI Analysis (Mocked for now)
        analysis = analyze_content_with_llm(content)
        
        # 3. Format Content
        formatted_content = apply_template(content, analysis)
        
        # 4. Determine Destination
        target_folder = VAULT_PATH / analysis.get('folder', 'Notes') # Changed default to 'Notes'
        target_folder.mkdir(parents=True, exist_ok=True)
        
        target_filename = analysis.get('filename', file_path.name)
        # Sanitize filename
        target_filename = "".join([c for c in target_filename if c.isalpha() or c.isdigit() or c in (' ', '-', '_', '.')]).rstrip()
        if not target_filename.endswith('.md'):
            target_filename += '.md'
            
        target_path = target_folder / target_filename
        
        # Handle duplicates
        if target_path.exists():
            timestamp = int(time.time())
            target_path = target_folder / f"{target_path.stem}_{timestamp}.md"
            
        # 5. Write New File
        target_path.write_text(formatted_content, encoding='utf-8')
        logger.info(f"Saved formatted note to: {target_path}")
        
        # 6. Delete Original (Safe Remove)
        try:
            os.remove(file_path)
            logger.info(f"Removed original file from Inbox.")
        except OSError as e:
            logger.error(f"Error deleting original file: {e}")
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {e}")

def analyze_content_with_llm(content: str) -> Dict:
    """
    Analyze content using LLM to extract metadata and structure.
    Returns a dict with: main_idea, summary, tags, folder, filename
    """
    # Placeholder logic
    lines = content.strip().split('\n')
    # Use first non-empty line as title, truncate to 50 chars
    title = next((line for line in lines if line.strip()), "Untitled").replace('#', '').strip()[:50]
    
    return {
        'main_idea': f"Summary of {title}",
        'folder': 'Notes', 
        'tags': ['auto-captured'],
        'filename': f"{title}.md"
    }

def apply_template(original_content: str, analysis: Dict) -> str:
    """Apply the New Note Template structure."""
    
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
        file_queue.put(existing_file)
        
    logger.info(f"Watching {INBOX_PATH} for new files...")
    
    # Start worker thread
    t = Thread(target=worker)
    t.daemon = True
    t.start()
    
    observer = Observer()
    observer.schedule(InboxHandler(), str(INBOX_PATH), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        file_queue.put(None) # Signal worker to stop
    observer.join()

if __name__ == "__main__":
    main()