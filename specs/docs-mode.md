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

## Add Document Modal

```
┌────────────────────────────────────────────────────────────────┐
│ Add Document                                                   │
├────────────────────────────────────────────────────────────────┤
│ Location:  [docs/architecture/     ▼]                          │
│ Filename:  [new-document.md          ]                         │
│                                                                │
│            [Cancel]  [Create]                                  │
└────────────────────────────────────────────────────────────────┘
```

## Delete Confirmation

```
┌────────────────────────────────────────────────────────────────┐
│ Delete Document                                                │
├────────────────────────────────────────────────────────────────┤
│ Are you sure you want to delete:                               │
│   docs/architecture/overview.md                                │
│                                                                │
│ This action cannot be undone.                                  │
│                                                                │
│            [Cancel]  [Delete]                                  │
└────────────────────────────────────────────────────────────────┘
```

## Inline Preview

When pressing `p`, show markdown preview:

```
┌────────────────────────────────────────────────────────────────┐
│ docs/architecture/overview.md                       [e] Edit   │
├────────────────────────────────────────────────────────────────┤
│ # Architecture Overview                                        │
│                                                                │
│ This document describes the high-level architecture of the     │
│ application...                                                 │
│                                                                │
│ ## Components                                                  │
│                                                                │
│ The system consists of three main components:                  │
│ - TUI Layer                                                    │
│ - iTerm2 Integration                                           │
│ - State Management                                             │
│                                                                │
│ [Press Esc to close, e to edit in external editor]             │
└────────────────────────────────────────────────────────────────┘
```

## External References (Future)

Future enhancement: Track bookmarked URLs and external links:

```python
@dataclass
class DocReference:
    """External documentation reference."""
    id: str
    title: str
    url: str
    category: str = ""
    notes: str = ""
```

```
│ External References                                            │
│ ├─ Textual Docs     https://textual.textualize.io/             │
│ ├─ iTerm2 API       https://iterm2.com/python-api/             │
│ └─ Design Spec      https://figma.com/...                      │
```

## Widget Implementation

```python
class DocsModeScreen(ModeScreen):
    """Docs Mode - documentation tree browser."""

    BINDINGS = [
        *ModeScreen.BINDINGS,
        ("a", "add_document", "Add"),
        ("d", "delete_document", "Delete"),
        ("r", "rename_document", "Rename"),
        ("p", "preview_document", "Preview"),
        ("enter", "open_document", "Open"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(
            DocTreeWidget(id="doc-tree"),
            id="main"
        )
        yield Footer()

    async def on_mount(self):
        """Build documentation tree."""
        tree = self.query_one("#doc-tree", DocTreeWidget)
        await tree.build_tree(self.project.path)


class DocTreeWidget(Tree):
    """Tree widget for documentation files."""

    async def build_tree(self, project_path: str):
        """Build tree from project documentation."""
        path = Path(project_path)

        # Add doc directories
        for dir_name in DOC_DIRECTORIES:
            dir_path = path / dir_name
            if dir_path.exists():
                self._add_directory(self.root, dir_path)

        # Add root-level doc files
        for file_name in DOC_FILES:
            file_path = path / file_name
            if file_path.exists():
                self.root.add_leaf(file_name, data=file_path)

    def _add_directory(self, parent: TreeNode, dir_path: Path):
        """Recursively add directory to tree."""
        node = parent.add(dir_path.name, data=dir_path)

        for item in sorted(dir_path.iterdir()):
            if item.is_dir():
                self._add_directory(node, item)
            elif item.suffix in (".md", ".txt", ".rst"):
                node.add_leaf(item.name, data=item)
```

## Related Specs

- [workflow-modes.md](./workflow-modes.md) - Mode system overview
- [ui.md](./ui.md) - Screen hierarchy
