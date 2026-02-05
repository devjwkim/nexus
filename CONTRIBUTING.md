# Contributing Guide

Thank you for your interest in contributing to Nexus!

This system is designed as an AI operational environment integrating Claude Code,
persistent memory, document management, and agent workflow orchestration.
To keep the architecture consistent and maintainable, please follow the guidelines below.

---

## 1. Contribution Types

You can contribute in several ways:

- Improving agent prompts and workflows (`.claude/agents/`)
- Enhancing memory/document integration (`.nexus/note/`)
- Adding new automation hooks or commands (`.claude/hooks/`, `.claude/commands/`)
- Fixing bugs and improving system stability
- Improving documentation

---

## 2. Code Style

- Keep modules independent and clearly scoped
- Avoid hardcoding local paths or credentials
- Write clear commit messages describing the purpose of changes
- Follow the existing folder structure:
  - `.claude/` - Claude Code configuration (agents, commands, hooks)
  - `.nexus/` - Project data (settings, history, notes, system scripts)

---

## 3. Security Rules

Do **NOT** include:

- API keys
- Telegram bot tokens
- Local system paths (e.g., `/Users/yourname/...`)
- Private documents or logs

Sensitive values must be placed in configuration templates with placeholder values only.

Example:
```properties
# Good
project.bot.token=YOUR_BOT_TOKEN

# Bad
project.bot.token=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

---

## 4. Pull Request Process

1. Fork the repository
2. Create a feature branch (`feature/your-feature-name`)
3. Commit changes with clear descriptions
4. Submit a Pull Request with an explanation of:
   - What was changed
   - Why the change is needed
   - How to test the changes

---

## 5. Agent and Memory Design Principles

When modifying agent prompts or memory handling:

- Maintain compatibility with the persistent memory architecture
- Ensure changes do not break document integration with Obsidian
- Keep agent roles clear and purpose-driven
- Test with `/boot` command after changes

### Agent Roles

| Agent | Responsibility |
|-------|----------------|
| @analyst | Requirements analysis only |
| @coder | Code implementation only |
| @tester | Test execution only |
| @reviewer | Code review only |
| @deployer | Git operations only |
| @librarian | Document management only |

---

## 6. Hook Development

When adding or modifying hooks:

- Ensure bash scripts are POSIX-compatible where possible
- Handle errors gracefully (don't break Claude Code flow)
- Test with both `~!`, `~@`, and `~#` workflows

---

We appreciate contributions that help improve long-term AI workflow persistence
and structured agent-based operations.

Thank you! 🎉
