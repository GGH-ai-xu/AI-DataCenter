# Public Repo Push Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把仓库整理到适合对外共享和安全 push 的状态，不改动现有产品行为。

**Architecture:** 只修改仓库协作配置、公开说明和 CI 入口，不触碰业务逻辑。所有文档与校验命令必须与当前代码实现一致，并优先保护本地运行态与凭据文件不被入库。

**Tech Stack:** Git, Markdown, EditorConfig, Git attributes, GitHub Actions, FastAPI, Vue 3, Node test runner

---

### Task 1: Harden repository ignore and text normalization

**Files:**
- Modify: `.gitignore`
- Create: `.editorconfig`
- Create: `.gitattributes`

- [ ] Step 1: Add explicit ignore coverage for runtime state, caches, worktrees, and generated artifacts
- [ ] Step 2: Add a root `.editorconfig` aligned with current Python, frontend, Markdown, and PowerShell conventions
- [ ] Step 3: Add a root `.gitattributes` to stabilize LF/CRLF behavior across platforms

### Task 2: Rewrite public-facing setup and security docs

**Files:**
- Modify: `README.md`
- Modify: `backend/.env.example`

- [ ] Step 1: Replace outdated “首页接入中心” workflow with the current login/import/console flow
- [ ] Step 2: Document the default admin bootstrap, master key requirement, and SSH Linux import mode
- [ ] Step 3: Update the backend env example to only include public-safe sample keys and paths

### Task 3: Align CI with verified repository checks

**Files:**
- Modify: `.github/workflows/ci.yml`

- [ ] Step 1: Keep Python compile and root unittest checks
- [ ] Step 2: Add frontend test execution through the existing `npm test` script
- [ ] Step 3: Keep production build validation through `npm run build`

### Task 4: Verify the resulting repository state

**Files:**
- Verify only

- [ ] Step 1: Run root Python unittest selection that covers the new repo-hygiene-sensitive areas
- [ ] Step 2: Run frontend test suite through `npm test`
- [ ] Step 3: Run frontend production build
- [ ] Step 4: Inspect git diff and confirm no local runtime state is staged by the config changes
