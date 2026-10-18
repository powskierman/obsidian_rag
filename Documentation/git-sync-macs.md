# Git-based sync between Macs (no iCloud)

Working from different Macs on a project stored directly in iCloud is unsafe. This document defines a Git-based sync method between Canmore and the MacBook.

## Current local project folder

Use `/Users/michel/dev/obsidian_rag` for the current local working copy. The equivalent home-relative path is `~/dev/obsidian_rag`.

Keep source-code synchronization separate from vault synchronization and database snapshot transfer. A command under a named machine heading applies on that machine. Confirm its checkout path before use. See the [documentation index](README.md#project-folder).

## Setup: Canmore bare repo

### On Canmore, confirm existing working copy:

cd /Users/michel/dev/obsidian_rag

### Initialize repo if needed:

git init

### Create directory for bare repos:

mkdir -p ~/git

### Create bare central repo:

git init --bare ~/git/obsidian_rag.git

### Add bare repo as origin (if not already set):

git remote add origin ~/git/obsidian_rag.git

### If origin exists, adjust instead:

git remote set-url origin ~/git/obsidian_rag.git

### First commit and push from Canmore (one time):

git add .

git commit -m "Initial import from Canmore working copy"

git branch -M main

git push -u origin main



## Wiring the MacBook repo to Canmore

### On MacBook, go to existing project dir:

cd /Users/michel/dev/obsidian_rag

### Point remote origin to Canmore:

git remote set-url origin canmores-mac-mini:~/git/obsidian_rag.git

### Fetch from Canmore:

git fetch origin

### Ensure local branch is main and matches remote:

git branch -M main

git reset --hard origin/main

## Clean up tool-specific files

### Ignore Claude worktrees directory:

echo ".claude/" >> .gitignore

git add .gitignore

git commit -m "Ignore Claude worktrees directory"

git push

## Daily workflow (both machines)

### Before starting work:

git pull

### After making changes:

git status

git add <files>  # or: git add .

git commit -m "<message>"

git push