---
area: system
title: Knowledge Document Management Guide
keywords: [documentation, note, librarian, obsidian]
related_files:
  - .claude/agents/librarian.md
  - .nexus/note/index.md
updated: 2026-02-05
---

# Overview

`.nexus/note/` folder is the project knowledge document storage.
`@librarian` agent handles document creation, update, and archiving.

# Folder Structure

```
.nexus/note/
├── index.md              # Knowledge index (for navigation)
├── domain/               # Domain models, business logic
├── api/                  # API endpoints, interfaces
├── db/                   # Database schema, tables
└── system/               # System config, deployment, infra
```

# Document Writing Rules

## File Naming
```
projectname_{area}_subject.md
e.g., nexus_system_documentation.md
```

## YAML Header (Required)
```yaml
---
area: domain|api|db|system
title: Document Title
keywords: [keyword1, keyword2]
related_files:
  - path/to/file1
  - path/to/file2
updated: YYYY-MM-DD
---
```

## Obsidian Links
- Write without extension: `[[nexus_system_documentation]]`
- Forbidden: `[[nexus_system_documentation.md]]`

# Index Rules

`.nexus/note/index.md` is the only index.

- Write only document links and brief descriptions
- Detailed info is based on each document's YAML header

# Librarian Agent Usage

## How to Call
- `@librarian [task description]`
- Auto-called on `~@` completion

## Work Scope
- Create/update documents in `.nexus/note/**`
- Archive to `.nexus/note_archived/**`

## Restrictions
- No source code modification
- No git operations
- No document creation in other folders

# Archiving

For documents no longer needed:
1. Move to `.nexus/note_archived/`
2. Remove link from `index.md`
3. Delete the link line from other documents

# Related Documents

- [[example_system_sample]]
