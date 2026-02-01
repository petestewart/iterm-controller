#!/bin/bash
#
# iTerm2 Controller Installation Script
#
# This script installs the iTerm2 Controller and configures the necessary
# dependencies for a new user to get running with a single command.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/petestewart/iterm-controller/main/install.sh | bash
#   # OR
#   ./install.sh
#
# Options:
#   --skip-optional    Skip optional dependencies (gh, terminal-notifier)
#   --no-venv          Install globally instead of in a virtual environment
#   --help             Show this help message
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MIN_PYTHON_VERSION="3.11"
MIN_ITERM_VERSION="3.5"
INSTALL_DIR="${INSTALL_DIR:-$HOME/.local/share/iterm-controller}"
CONFIG_DIR="$HOME/.config/iterm-controller"
VENV_DIR="$INSTALL_DIR/venv"

# Parse arguments
SKIP_OPTIONAL=false
USE_VENV=true

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-optional)
            SKIP_OPTIONAL=true
            shift
            ;;
        --no-venv)
            USE_VENV=false
            shift
            ;;
        --help)
            head -25 "$0" | tail -20
            exit 0
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            exit 1
            ;;
    esac
done

# Utility functions
print_step() {
    echo -e "\n${BLUE}==>${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_command() {
    command -v "$1" &> /dev/null
}

version_gte() {
    # Compare versions: returns 0 if $1 >= $2
    printf '%s\n%s' "$2" "$1" | sort -V -C
}

# Check macOS
check_macos() {
    print_step "Checking operating system..."

    if [[ "$(uname)" != "Darwin" ]]; then
        print_error "iTerm2 Controller requires macOS. Detected: $(uname)"
        exit 1
    fi

    local macos_version
    macos_version=$(sw_vers -productVersion)
    print_success "macOS $macos_version detected"
}

# Check/install Homebrew
check_homebrew() {
    print_step "Checking for Homebrew..."

    if ! check_command brew; then
        print_warning "Homebrew not found. Installing..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

        # Add Homebrew to PATH for Apple Silicon
        if [[ -f /opt/homebrew/bin/brew ]]; then
            eval "$(/opt/homebrew/bin/brew shellenv)"
        fi
    fi

    print_success "Homebrew is installed"
}

# Check/install Python
check_python() {
    print_step "Checking Python version..."

    local python_cmd=""
    local python_version=""

    # Try python3.11, python3.12, python3.13, then python3
    for cmd in python3.11 python3.12 python3.13 python3; do
        if check_command "$cmd"; then
            python_version=$("$cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
            if version_gte "$python_version" "$MIN_PYTHON_VERSION"; then
                python_cmd="$cmd"
                break
            fi
        fi
    done

    if [[ -z "$python_cmd" ]]; then
        print_warning "Python $MIN_PYTHON_VERSION+ not found. Installing via Homebrew..."
        brew install python@3.11
        python_cmd="python3.11"
        python_version="3.11"
    fi

    print_success "Python $python_version found ($python_cmd)"
    PYTHON_CMD="$python_cmd"
}

# Check/install iTerm2
check_iterm() {
    print_step "Checking for iTerm2..."

    if [[ -d "/Applications/iTerm.app" ]]; then
        # Get iTerm2 version
        local iterm_version
        iterm_version=$(defaults read /Applications/iTerm.app/Contents/Info CFBundleShortVersionString 2>/dev/null || echo "unknown")

        if version_gte "$iterm_version" "$MIN_ITERM_VERSION"; then
            print_success "iTerm2 $iterm_version found"
        else
            print_warning "iTerm2 $iterm_version found, but $MIN_ITERM_VERSION+ is recommended"
        fi
    else
        print_warning "iTerm2 not found. Installing via Homebrew..."
        brew install --cask iterm2
        print_success "iTerm2 installed"
    fi
}

# Enable iTerm2 Python API
configure_iterm() {
    print_step "Configuring iTerm2 Python API..."

    # iTerm2 stores preferences in com.googlecode.iterm2.plist
    local plist="$HOME/Library/Preferences/com.googlecode.iterm2.plist"

    if [[ -f "$plist" ]]; then
        # Check if API is already enabled
        local api_enabled
        api_enabled=$(defaults read com.googlecode.iterm2 EnableAPIServer 2>/dev/null || echo "0")

        if [[ "$api_enabled" == "1" ]]; then
            print_success "iTerm2 Python API already enabled"
        else
            print_warning "Enabling iTerm2 Python API..."
            defaults write com.googlecode.iterm2 EnableAPIServer -bool true
            print_success "iTerm2 Python API enabled"
            print_warning "Please restart iTerm2 for changes to take effect"
        fi
    else
        # iTerm2 hasn't been run yet, create the preference
        print_warning "iTerm2 preferences not found. Creating configuration..."
        defaults write com.googlecode.iterm2 EnableAPIServer -bool true
        print_success "iTerm2 Python API enabled"
        print_warning "Please launch iTerm2 at least once before using iterm-controller"
    fi
}

# Install optional dependencies
install_optional() {
    if [[ "$SKIP_OPTIONAL" == "true" ]]; then
        print_step "Skipping optional dependencies (--skip-optional)"
        return
    fi

    print_step "Installing optional dependencies..."

    # GitHub CLI
    if check_command gh; then
        print_success "GitHub CLI (gh) already installed"
    else
        print_warning "Installing GitHub CLI..."
        brew install gh
        print_success "GitHub CLI installed"
        print_warning "Run 'gh auth login' to authenticate"
    fi

    # terminal-notifier
    if check_command terminal-notifier; then
        print_success "terminal-notifier already installed"
    else
        print_warning "Installing terminal-notifier..."
        brew install terminal-notifier
        print_success "terminal-notifier installed"
    fi
}

# Install iterm-controller package
install_package() {
    print_step "Installing iterm-controller..."

    # Create install directory
    mkdir -p "$INSTALL_DIR"

    if [[ "$USE_VENV" == "true" ]]; then
        # Create virtual environment
        if [[ ! -d "$VENV_DIR" ]]; then
            print_warning "Creating virtual environment..."
            "$PYTHON_CMD" -m venv "$VENV_DIR"
        fi

        # Activate venv and install
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip

        # Check if we're in the source directory
        if [[ -f "pyproject.toml" ]] && grep -q "iterm-controller" pyproject.toml 2>/dev/null; then
            print_warning "Installing from local source..."
            pip install -e ".[dev]"
        else
            print_warning "Installing from PyPI..."
            pip install iterm-controller
        fi

        deactivate

        # Create wrapper script
        print_warning "Creating command wrapper..."
        mkdir -p "$HOME/.local/bin"
        cat > "$HOME/.local/bin/iterm-controller" << EOF
#!/bin/bash
source "$VENV_DIR/bin/activate"
exec python -m iterm_controller "\$@"
EOF
        chmod +x "$HOME/.local/bin/iterm-controller"

        print_success "iterm-controller installed to $VENV_DIR"
    else
        # Install globally
        if [[ -f "pyproject.toml" ]] && grep -q "iterm-controller" pyproject.toml 2>/dev/null; then
            pip install -e ".[dev]"
        else
            pip install iterm-controller
        fi
        print_success "iterm-controller installed globally"
    fi
}

# Create config directory and default config
create_config() {
    print_step "Setting up configuration..."

    mkdir -p "$CONFIG_DIR"

    if [[ ! -f "$CONFIG_DIR/config.json" ]]; then
        cat > "$CONFIG_DIR/config.json" << 'EOF'
{
  "settings": {
    "default_ide": "vscode",
    "default_shell": "zsh",
    "polling_interval_ms": 500,
    "notification_enabled": true,
    "github_refresh_seconds": 60,
    "health_check_interval_seconds": 10.0
  },
  "projects": [],
  "templates": [
    {
      "id": "default",
      "name": "Default Project",
      "description": "Basic project with shell and editor sessions",
      "initial_sessions": ["shell", "editor"],
      "setup_script": null
    }
  ],
  "session_templates": [
    {
      "id": "shell",
      "name": "Shell",
      "command": ""
    },
    {
      "id": "editor",
      "name": "Editor",
      "command": "${IDE:-code} ."
    },
    {
      "id": "dev-server",
      "name": "Dev Server",
      "command": "npm run dev"
    },
    {
      "id": "claude",
      "name": "Claude",
      "command": "claude"
    }
  ],
  "window_layouts": []
}
EOF
        print_success "Created default configuration at $CONFIG_DIR/config.json"
    else
        print_success "Configuration already exists at $CONFIG_DIR/config.json"
    fi
}

# Add to PATH if needed
configure_path() {
    if [[ "$USE_VENV" == "true" ]]; then
        print_step "Checking PATH configuration..."

        local local_bin="$HOME/.local/bin"

        if [[ ":$PATH:" != *":$local_bin:"* ]]; then
            print_warning "Adding $local_bin to PATH..."

            # Detect shell and update config
            local shell_config=""
            case "$SHELL" in
                */zsh)
                    shell_config="$HOME/.zshrc"
                    ;;
                */bash)
                    shell_config="$HOME/.bashrc"
                    ;;
            esac

            if [[ -n "$shell_config" ]]; then
                echo "" >> "$shell_config"
                echo "# Added by iterm-controller installer" >> "$shell_config"
                echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$shell_config"
                print_success "Added to $shell_config"
                print_warning "Run 'source $shell_config' or restart your shell"
            else
                print_warning "Add $local_bin to your PATH manually"
            fi
        else
            print_success "PATH already configured"
        fi
    fi
}

# Verify installation
verify_installation() {
    print_step "Verifying installation..."

    local iterm_controller_cmd=""

    if [[ "$USE_VENV" == "true" ]]; then
        iterm_controller_cmd="$HOME/.local/bin/iterm-controller"
    else
        iterm_controller_cmd="iterm-controller"
    fi

    if [[ -x "$iterm_controller_cmd" ]] || check_command iterm-controller; then
        print_success "iterm-controller command available"
    else
        print_warning "iterm-controller command not in PATH yet"
        print_warning "Run: export PATH=\"\$HOME/.local/bin:\$PATH\""
    fi

    # Test Python import
    if [[ "$USE_VENV" == "true" ]]; then
        source "$VENV_DIR/bin/activate"
    fi

    if "$PYTHON_CMD" -c "import iterm_controller" 2>/dev/null; then
        print_success "iterm_controller module importable"
    else
        print_warning "Module import test failed (may need PATH update)"
    fi

    if [[ "$USE_VENV" == "true" ]]; then
        deactivate 2>/dev/null || true
    fi
}

# Print final instructions
print_instructions() {
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║             iTerm2 Controller Installation Complete!           ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo -e "${BLUE}Quick Start:${NC}"
    echo "  1. Restart iTerm2 to enable the Python API"
    echo "  2. Run: iterm-controller"
    echo ""
    echo -e "${BLUE}Configuration:${NC}"
    echo "  Config file: $CONFIG_DIR/config.json"
    echo "  Edit to add projects, templates, and customize settings"
    echo ""
    echo -e "${BLUE}Optional Setup:${NC}"
    if ! check_command gh || ! (gh auth status &>/dev/null); then
        echo "  - GitHub CLI: Run 'gh auth login' for GitHub integration"
    fi
    echo "  - Create a project: Add to config.json or use the TUI"
    echo ""
    echo -e "${BLUE}Documentation:${NC}"
    echo "  https://github.com/petestewart/iterm-controller"
    echo ""
}

# Main installation flow
main() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║              iTerm2 Controller Installer                       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    check_macos
    check_homebrew
    check_python
    check_iterm
    configure_iterm
    install_optional
    install_package
    create_config
    configure_path
    verify_installation
    print_instructions
}

# Only run main when executed directly, not when sourced
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
