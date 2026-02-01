# Problem Statement: iTerm2 Project Orchestrator

## Problem

Developers working on multiple projects simultaneously face constant context-switching friction. Each project requires:
- Multiple terminal tabs/panes (dev servers, test watchers, Claude sessions, linters)
- Remembering which commands to run and in what order
- Manually monitoring session output for prompts requiring attention (Claude questions, test confirmations, build failures)
- Switching between projects means tearing down and rebuilding terminal layouts

This is especially painful when running multiple Claude Code sessions across projects—missing a clarifying question means wasted time and lost momentum.

## Context

The current workflow for a developer with 2-3 active projects:
1. Open iTerm2 manually
2. Create tabs for each service (dev server, tests, Claude)
3. Navigate to correct directory in each tab
4. Run startup commands in specific order
5. Constantly scan all tabs for output requiring attention
6. When switching projects, either leave stale tabs or close and rebuild

A POC exists demonstrating iTerm2's Python API capabilities:
- Can spawn tabs/panes programmatically
- Can monitor session output via polling
- Can detect session termination
- Uses Textual for TUI rendering

The iTerm2 Python API provides the building blocks (see `docs/API_REFERENCE.md`), and detailed specifications exist for the full application (see `docs/APP_SPEC.md`, `docs/DATA_MODEL.md`).

## Desired Outcome

A terminal-based TUI application that serves as a "control room" for development projects:

**One command to open a project and have all dev environment tabs spawn, configured, and monitored.**

Key capabilities:
- **Control Room view** showing all active sessions across all projects, sorted by attention-needed status
- **Session attention detection** with system notifications when Claude asks a question or a prompt needs input
- **Project templates** for one-click setup of new worktrees/branches with predefined tab layouts
- **Task tracking** integrated with PLAN.md files showing implementation progress
- **Health checks** to verify services are running
- **GitHub integration** showing PR status, sync state, and unresolved comments
- **Auto mode** for hands-off project lifecycle progression—configure commands for each workflow stage (e.g., `claude /prd`, `claude /specs`, `claude /plan`) and the system automatically advances through Planning → Execute → Review → PR when each phase completes

## Success Criteria

- [ ] Can create a new project from a template (runs setup script, creates branch, spawns configured sessions)
- [ ] Control Room displays all sessions across projects with accurate status (Working/Waiting/Idle)
- [ ] System notification fires within 5 seconds when any session enters Waiting state
- [ ] Can spawn/kill individual sessions from the dashboard
- [ ] Project dashboard shows task progress parsed from PLAN.md
- [ ] Health checks poll configured endpoints and display status
- [ ] GitHub panel shows branch sync status and PR info (using `gh` CLI)
- [ ] Quit confirmation offers options: close all, close managed only, leave running
- [ ] Settings screen allows configuring defaults (IDE, shell, notification preferences)
- [ ] Auto mode can be configured with stage-specific commands that run when a phase completes
- [ ] Can launch a new window with a predefined set of tabs/sessions

## Out of Scope

- **Remote/SSH projects** - Strictly local development
- **Session replay/history** - No persistent output storage beyond scrollback
- **Cross-machine sync** - No cloud sync of project configs
- **Plugin system** - No extensibility API in V1
- **Inter-session communication** - Sessions are independent
