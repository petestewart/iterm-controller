# Spec Planner - Implementation Prompt

Study @specs/README.md and PLAN.md

Work on the first unchecked task (`- [ ]`) in PLAN.md. Tasks are organized by phase - complete them in order unless dependencies require otherwise.

1. Find the first unchecked task (`- [ ]`) in the current phase
2. Read any referenced specs (listed after "Spec:") before implementing
3. Implement the task following the acceptance criteria
4. Write tests to verify it works
5. Mark the task complete by changing `- [ ]` to `- [x]` in PLAN.md

When a task is complete:
1. Change `- [ ]` to `- [x]` for the completed task
2. Change `[pending]` to `[complete]` in the task's status tag
3. IMPORTANT: Commit changes with a message describing what was completed, then push your commit

## Rules

- **All acceptance criteria must pass** before marking a task complete
- **If new work is discovered**, add it to the appropriate phase in PLAN.md
- **Read the relevant spec** before implementing any task
- **Write tests** for new functionality
- **Commit frequently** after completing tasks
