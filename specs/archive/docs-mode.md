# DEPRECATED - Docs Mode Screen

> **DEPRECATION NOTICE**: This spec was deprecated on 2026-02-02.
>
> Docs Mode has been replaced by the "Docs Section" in the unified Project Screen.
> See [ui.md](../ui.md) for the new architecture.
>
> This file is kept for historical reference only.

---

# Docs Mode Screen

## Overview

Tree-based documentation browser for project files. Allows navigating, viewing, adding, editing, and organizing documentation.

## Tree Structure

Shows nested folder hierarchy of documentation files:

```
docs/
├── getting-started.md
├── architecture/
│   ├── overview.md
│   ├── data-flow.md
│   └── components.md
├── api/
│   └── endpoints.md
specs/
├── README.md
├── models.md
└── ui.md
README.md
CHANGELOG.md
```

## Layout

```
┌────────────────────────────────────────────────────────────────┐
│ my-project                           [Docs] 1 2 3 4   [?] Help │
├────────────────────────────────────────────────────────────────┤
│ Documentation                                                  │
│ ┌────────────────────────────────────────────────────────────┐ │
│ │ ▼ docs/                                                    │ │
│ │   ├─ getting-started.md                                    │ │
│ │   ▼ architecture/                                          │ │
│ │     ├─ overview.md                                         │ │
│ │     ├─ data-flow.md                                        │ │
│ │     └─ components.md                                       │ │
│ │   ▶ api/                                                   │ │
│ │ ▼ specs/                                                   │ │
│ │   ├─ README.md                                             │ │
│ │   ├─ models.md                                             │ │
│ │   └─ ui.md                                                 │ │
│ │ README.md                                                  │ │
│ │ CHANGELOG.md                                               │ │
│ └────────────────────────────────────────────────────────────┘ │
├────────────────────────────────────────────────────────────────┤
│ ↑↓ Navigate  Enter Open  a Add  d Delete  r Rename  p Preview │
└────────────────────────────────────────────────────────────────┘
```

## Tracked Directories

Default directories scanned for documentation:

```python
DOC_DIRECTORIES = [
    "docs/",
    "specs/",
    "documentation/",
]

DOC_FILES = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "LICENSE",
]
```

## Actions

| Key | Action | Description |
|-----|--------|-------------|
| `↑/↓` | Navigate | Move selection in tree |
| `←/→` | Collapse/Expand | Collapse or expand folder |
| `Enter` | Open | Open file in editor / expand folder |
| `a` | Add | Add new document (prompts for name/location) |
| `d` | Delete | Delete document (with confirmation) |
| `r` | Rename | Rename document |
| `p` | Preview | Preview markdown inline |
| `Esc` | Back | Return to project dashboard |
