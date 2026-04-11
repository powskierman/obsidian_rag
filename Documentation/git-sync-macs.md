# Git-based sync between Macs (no iCloud)

Working from different Macs on a project stored directly in iCloud is unsafe. This document defines a Git-based sync method between Canmore and the MacBook.

## Setup: Canmore bare repo

### On Canmore, confirm existing working copy:

cd ~/dev/obsidian_rag

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

cd ~/obsidian_rag  # or actual path

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