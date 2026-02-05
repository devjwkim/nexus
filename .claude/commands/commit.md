# commit command

Commits and pushes current changes.

## Execution Steps

1. **Check changes:**
   ```
   git status
   git diff --stat
   ```

3. **User confirmation:**
   - Show list of changes
   - Confirm commit

4. **Write commit message:**
   - Use conventional commit format (feat, fix, docs, chore, etc.)
   - Summarize changes concisely

5. **Commit and push (include all changes):**
   ```
   git add .
   git commit -m "<commit message>"
   git push
   ```
   **Important: Use `git add .` to include all changes including untracked files**

---

**Notes:**
- Verify sensitive files (.env, credentials, etc.) are in .gitignore
- Check files to be included with git status before commit
