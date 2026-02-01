# Configuration

## Overview

JSON-based configuration with global defaults and project-local overrides.

## File Locations

| File | Location | Purpose |
|------|----------|---------|
| Global config | `~/.config/iterm-controller/config.json` | App settings, project list, templates |
| Project config | `{project}/.iterm-controller.json` | Project-local overrides (optional) |
| Plan file | `{project}/PLAN.md` or configured path | Task tracking |

## Configuration Loading

```python
from pathlib import Path
import json
from dacite import from_dict, Config as DaciteConfig

CONFIG_DIR = Path.home() / ".config" / "iterm-controller"
GLOBAL_CONFIG_PATH = CONFIG_DIR / "config.json"

async def load_app_config() -> AppConfig:
    """Load global application configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    if GLOBAL_CONFIG_PATH.exists():
        with open(GLOBAL_CONFIG_PATH) as f:
            data = json.load(f)
        return from_dict(
            data_class=AppConfig,
            data=data,
            config=DaciteConfig(cast=[Enum])
        )

    # Return default config
    return AppConfig()

async def save_app_config(config: AppConfig):
    """Save global application configuration."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    with open(GLOBAL_CONFIG_PATH, "w") as f:
        json.dump(asdict(config), f, indent=2, default=str)

def load_project_config(project_path: str) -> dict:
    """Load project-local configuration overrides."""
    config_path = Path(project_path) / ".iterm-controller.json"

    if config_path.exists():
        with open(config_path) as f:
            return json.load(f)

    return {}
```

## Configuration Merging

Merge global config with project-local overrides.

**Merge Strategy: Deep Merge with Override**

```python
import copy

def merge_configs(global_config: dict, project_config: dict) -> dict:
    """
    Merge project config into global config.

    Rules:
    - Scalars: project overrides global
    - Lists: project replaces global (no merge)
    - Dicts: recursive merge
    - None in project: removes key from global
    """
    result = copy.deepcopy(global_config)

    for key, value in project_config.items():
        if value is None:
            # None removes key
            result.pop(key, None)
        elif isinstance(value, dict) and key in result and isinstance(result[key], dict):
            # Recursive merge for dicts
            result[key] = merge_configs(result[key], value)
        else:
            # Override for scalars and lists
            result[key] = value

    return result
```

**Example:**

```json
// Global: ~/.config/iterm-controller/config.json
{
  "settings": {
    "default_ide": "vscode",
    "polling_interval_ms": 500,
    "notification_enabled": true
  },
  "session_templates": [
    {"id": "shell", "name": "Shell", "command": ""}
  ]
}

// Project: ./my-project/.iterm-controller.json
{
  "settings": {
    "default_ide": "cursor"
    // polling_interval_ms inherits 500
    // notification_enabled inherits true
  },
  "scripts": {
    "start": {"command": "npm run dev"}
  }
}

// Result:
{
  "settings": {
    "default_ide": "cursor",
    "polling_interval_ms": 500,
    "notification_enabled": true
  },
  "session_templates": [
    {"id": "shell", "name": "Shell", "command": ""}
  ],
  "scripts": {
    "start": {"command": "npm run dev"}
  }
}
```

## Configuration Schema

```python
@dataclass
class AppSettings:
    """Global application settings."""
    default_ide: str = "vscode"
    default_shell: str = "zsh"
    polling_interval_ms: int = 500
    notification_enabled: bool = True
    github_refresh_seconds: int = 60
    health_check_interval_seconds: float = 10.0

@dataclass
class AppConfig:
    """Complete application configuration."""
    settings: AppSettings = field(default_factory=AppSettings)
    projects: list[Project] = field(default_factory=list)
    templates: list[ProjectTemplate] = field(default_factory=list)
    session_templates: list[SessionTemplate] = field(default_factory=list)
    window_layouts: list[WindowLayout] = field(default_factory=list)
```

## Project Templates

Templates for creating new projects.

```python
@dataclass
class ProjectTemplate:
    """Template for creating new projects."""
    id: str                              # Unique identifier
    name: str                            # Display name
    description: str = ""                # Template description
    setup_script: str | None = None      # Script to run after creation
    initial_sessions: list[str] = field(default_factory=list)  # SessionTemplate IDs
    default_plan: str | None = None      # Initial PLAN.md content
    files: dict[str, str] = field(default_factory=dict)  # Additional files to create
    required_fields: list[str] = field(default_factory=list)  # Form fields needed
```

### Template CRUD Operations

```python
class TemplateManager:
    """Manages project templates."""

    def __init__(self, config: AppConfig):
        self.config = config

    def list_templates(self) -> list[ProjectTemplate]:
        """List all available templates."""
        return self.config.templates.copy()

    def get_template(self, template_id: str) -> ProjectTemplate | None:
        """Get template by ID."""
        for template in self.config.templates:
            if template.id == template_id:
                return template
        return None

    def add_template(self, template: ProjectTemplate):
        """Add a new template."""
        if self.get_template(template.id):
            raise ValueError(f"Template {template.id} already exists")
        self.config.templates.append(template)

    def update_template(self, template: ProjectTemplate):
        """Update an existing template."""
        for i, t in enumerate(self.config.templates):
            if t.id == template.id:
                self.config.templates[i] = template
                return
        raise ValueError(f"Template {template.id} not found")

    def delete_template(self, template_id: str):
        """Delete a template."""
        self.config.templates = [
            t for t in self.config.templates if t.id != template_id
        ]

    def validate_template(self, template: ProjectTemplate) -> list[str]:
        """Validate template configuration. Returns list of errors."""
        errors = []

        if not template.id:
            errors.append("Template ID is required")
        if not template.name:
            errors.append("Template name is required")

        # Validate session template references
        session_ids = {s.id for s in self.config.session_templates}
        for session_id in template.initial_sessions:
            if session_id not in session_ids:
                errors.append(f"Unknown session template: {session_id}")

        return errors
```

### Running Setup Scripts

```python
class TemplateRunner:
    """Runs template setup scripts during project creation."""

    async def create_from_template(
        self,
        template: ProjectTemplate,
        project_path: str,
        form_values: dict[str, str]
    ) -> Project:
        """Create a new project from template."""
        path = Path(project_path)

        # Create project directory
        path.mkdir(parents=True, exist_ok=True)

        # Create additional files
        for filename, content in template.files.items():
            file_path = path / filename
            file_path.parent.mkdir(parents=True, exist_ok=True)

            # Substitute template variables
            content = self._substitute_vars(content, form_values)
            file_path.write_text(content)

        # Create default PLAN.md
        if template.default_plan:
            plan_content = self._substitute_vars(template.default_plan, form_values)
            (path / "PLAN.md").write_text(plan_content)

        # Run setup script
        if template.setup_script:
            await self._run_setup_script(template.setup_script, path, form_values)

        # Create project object
        project = Project(
            id=form_values.get("name", path.name),
            name=form_values.get("name", path.name),
            path=str(path),
            template_id=template.id
        )

        return project

    def _substitute_vars(self, content: str, values: dict[str, str]) -> str:
        """Substitute {{var}} placeholders in content."""
        for key, value in values.items():
            content = content.replace(f"{{{{{key}}}}}", value)
        return content

    async def _run_setup_script(
        self,
        script: str,
        path: Path,
        values: dict[str, str]
    ):
        """Run template setup script."""
        # Substitute variables in script
        script = self._substitute_vars(script, values)

        # Run script
        process = await asyncio.create_subprocess_shell(
            script,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise SetupScriptError(
                f"Setup script failed: {stderr.decode()}"
            )
```

## Session Template Configuration

```python
@dataclass
class SessionTemplate:
    """Template for spawning terminal sessions."""
    id: str                              # Unique identifier
    name: str                            # Display name
    command: str                         # Initial command to run
    working_dir: str | None = None       # Working directory (default: project root)
    env: dict[str, str] = field(default_factory=dict)  # Additional env vars
    health_check: str | None = None      # Associated health check ID
```

## Window Layout Configuration

```python
@dataclass
class WindowLayout:
    """Predefined window layout with tabs and sessions."""
    id: str                              # Layout identifier
    name: str                            # Display name
    tabs: list[TabLayout] = field(default_factory=list)

    def to_json(self) -> dict:
        """Serialize for storage."""
        return asdict(self)

    @classmethod
    def from_json(cls, data: dict) -> "WindowLayout":
        """Deserialize from storage."""
        return from_dict(data_class=cls, data=data)

class WindowLayoutManager:
    """Manages window layouts."""

    def __init__(self, config: AppConfig):
        self.config = config

    def save_layout(self, layout: WindowLayout):
        """Save or update a layout."""
        for i, existing in enumerate(self.config.window_layouts):
            if existing.id == layout.id:
                self.config.window_layouts[i] = layout
                return
        self.config.window_layouts.append(layout)

    def load_layout(self, layout_id: str) -> WindowLayout | None:
        """Load a layout by ID."""
        for layout in self.config.window_layouts:
            if layout.id == layout_id:
                return layout
        return None

    def delete_layout(self, layout_id: str):
        """Delete a layout."""
        self.config.window_layouts = [
            l for l in self.config.window_layouts if l.id != layout_id
        ]
```

## Environment File Parsing

```python
import re

class EnvParser:
    """Parses .env files for environment variables."""

    VAR_PATTERN = re.compile(r'\$\{(\w+)\}')

    def parse(self, content: str) -> dict[str, str]:
        """Parse .env file content."""
        env = {}

        for line in content.splitlines():
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Parse KEY=value
            if "=" in line:
                key, value = line.split("=", 1)
                key = key.strip()
                value = self._parse_value(value.strip())
                env[key] = value

        # Expand variable references
        return self._expand_vars(env)

    def _parse_value(self, value: str) -> str:
        """Parse value, handling quotes."""
        # Remove surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        return value

    def _expand_vars(self, env: dict[str, str]) -> dict[str, str]:
        """Expand ${VAR} references."""
        result = {}

        for key, value in env.items():
            # Expand ${VAR} references
            def replace(match):
                var_name = match.group(1)
                return env.get(var_name, os.environ.get(var_name, ""))

            result[key] = self.VAR_PATTERN.sub(replace, value)

        return result

    def load_file(self, path: Path) -> dict[str, str]:
        """Load environment from .env file."""
        if not path.exists():
            return {}
        return self.parse(path.read_text())
```
