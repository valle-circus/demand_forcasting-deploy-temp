# CLAUDE.md

Claude Code must read and follow the repository-wide instructions in
`AGENTS.md` before changing this project. `AGENTS.md` is authoritative if these
files ever differ.

## Git actions require explicit user authorization

- Do not stage, commit, push, pull, merge, rebase, cherry-pick, tag, create or
  change branches/worktrees, or open/merge/close a pull request unless the user
  explicitly requests that specific action.
- Editing files or completing a task never implies permission to commit or
  push. Leave changes uncommitted and report them unless the user explicitly
  asks otherwise.
- Permission for one Git action does not authorize later Git actions. Read-only
  inspection such as `git status`, `git diff`, and `git log` remains allowed.

## Temporary GitHub deployment mirror

- Work on the currently checked-out branch. Do not create, switch, rename, or
  delete branches, and do not create a worktree, unless the user explicitly
  requests it. The user decides whether a branch or pull request is needed.
- `circus-kitchens/demand_forcasting` is authoritative. Do not independently
  create a pull request; if the user requests one, this is the only repository
  where it may be opened and merged.
- `valle-circus/demand_forcasting-deploy-temp` is temporarily used only by
  Vercel and Render. Do not open or merge pull requests there.
- This checkout normally fetches from the organization repository and pushes to
  both repositories through two `origin` push URLs. Verify the local setup with
  `git remote -v` and `git config --get-all remote.origin.pushurl` because a new
  clone does not inherit it.
- After a GitHub-side merge in the organization, synchronize the deployment
  mirror only when the user explicitly requests it, using the specific commands
  they authorize. The usual sequence is:

  ```powershell
  git switch main
  git pull --ff-only origin main
  git push origin main
  ```

- Check the full output because a multi-destination push is not atomic. Follow
  the complete workflow and cleanup rules in `AGENTS.md`.
