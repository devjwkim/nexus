# fetch command

Fetches latest source from remote repository.

## Execution Steps

1. **Check current status:**
   ```
   git status
   git branch -vv
   ```

2. **Fetch remote changes:**
   ```
   git fetch origin
   git log HEAD..origin/main --oneline
   ```

3. **User confirmation:**
   - Show list of commits to fetch
   - Confirm pull

4. **Merge source:**
   ```
   git pull origin main
   ```

5. **Check changes:**
   ```
   git diff HEAD@{1} HEAD --stat
   ```

6. **@librarian call:**
   - Update `.nexus/note/` documents based on changes
   - Reflect other users' modifications to local docs
   - Skip if no documentation needed

7. **Verify result:**
   ```
   git log --oneline -5
   ```

---

**Notes:**
- Commit or stash local changes first
- Notify user if conflicts occur
