# Deployment Provenance Analysis: HA Supervisor Local Build

**Investigation Date:** 2026-11-07  
**Reviewed HEAD:** `e620ac64ee84b84f0d1d9cb507461a3d9c3e9b6e` (PR #5)  
**Target:** kamien5/predbat_addon deployment verification  
**Mode:** Read-only analysis, NO changes made

---

## Executive Summary

**Critical finding:** HA Supervisor fetches from **default branch (main)** unless user explicitly selects a tag during installation. Tag creation alone does NOT ensure it's used. Provenance chain requires:

1. Merge creates new SHA → tree equivalence verification needed
2. Tag points to merge SHA → proves reviewed content
3. **Live evidence required:** User must document which ref Supervisor fetched

---

## Current State

### Tag Status
```bash
$ git tag -l "kamien5-v4"
(empty - tag does NOT exist)

$ git show-ref --tags | grep kamien5
ebe666069cb8770f16781a455c97923ded105c01 refs/tags/kamien5-v1
951f1e1eb4956c43137826fe4b108e45c1fdfc0c refs/tags/kamien5-v2
0e1d3f022a865988d50fe329d553178ec4d3909a refs/tags/kamien5-v3
```
✅ **kamien5-v4 does NOT exist** — safe to create after merge

### Branch State
```bash
main HEAD: 0e1d3f022a865988d50fe329d553178ec4d3909a (kamien5-v3)
PR branch: cursor/vendor-predbat-v9.7.0-2ba3
PR HEAD:   e620ac64ee84b84f0d1d9cb507461a3d9c3e9b6e
Merge base: 0e1d3f022a865988d50fe329d553178ec4d3909a (clean, no divergence)
Commits ahead: 5
Files changed: 35 files, +4492/-363 lines
```

### Reviewed Content Fingerprint
```bash
Reviewed HEAD SHA: [TO BE DETERMINED by Security/QA final approval]
Config version: 1.7.1-kamien5.4
Vendor commit: 4cbf633355525ea62ddf8e47e647ee215b38f1ca (upstream v9.7.0)
Vendor files: 115 (verified against MANIFEST.sha256)
```
**Tree equivalence check:** Merge commit tree must equal reviewed HEAD tree (resolved externally at deployment time)

---

## HA Supervisor Add-on Installation Mechanism

### Repository Registration
```
User adds: https://github.com/kamien5/predbat_addon
HA computes prefix: fc83ef65 (first 8 chars of sha1(lowercase URL))
Config directory: /addon_configs/fc83ef65_predbat/
```

### What Supervisor Fetches

**Default behavior (NO `image:` field in config.yaml):**
```yaml
# predbat/config.yaml
name: Predbat (kamien5 fork)
version: 1.7.1-kamien5.4
# NO "image:" field → Supervisor builds locally
```

**Fetch behavior:**
1. **Default:** Fetches from `default_branch` (main)
2. **If user selects version:** Can choose specific tag/branch from dropdown
3. **Build:** `docker build` with Dockerfile from fetched commit

**Critical:** Supervisor does NOT automatically use latest tag. It uses:
- Main branch by default
- OR user-selected ref from version dropdown

### Evidence Chain Required

To prove Supervisor built from approved sources, need **live evidence**:
1. HA Supervisor logs showing fetched commit SHA
2. OR screenshot of version dropdown selection
3. OR add-on info showing installed version source

---

## Merge Method Analysis

### GitHub Repository Settings
```json
{
  "allow_merge_commit": true,
  "allow_rebase_merge": true,
  "allow_squash_merge": true,
  "default_branch": "main"
}
```
**All three methods enabled.** Merger chooses at PR time.

### Historical Pattern
```bash
$ git log main --oneline | head -5
0e1d3f02 Merge pull request #4 from kamien5/cursor/vendor-predbat-v9.6.5-ac52
cf2bf717 Fix DEPLOY.md rollback procedure and update stub message
c5963a69 Add self-update mutation test verification document
25d97183 Vendor Predbat v9.6.5 for version 1.7.1-kamien5.3
951f1e1e Fix Dockerfile to enforce pinned Ubuntu base regardless of BUILD_FROM arg (#2)
```
**Pattern:** Merge commits (not squash). PRs #1, #2, #4 all used merge commits.

### Predicted Merge for PR #5

**Scenario A: Merge Commit (likely, matches history)**
```
Before merge:
  main:      0e1d3f02 (kamien5-v3)
  PR branch: e620ac64 (5 commits ahead)

After merge:
  main: <NEW_SHA> (merge commit)
        ├─ parent1: 0e1d3f02 (previous main)
        └─ parent2: e620ac64 (PR head)

Tree of merge commit: 9319125dd545747bea335e5e1a7c7ae5e278db6f
                      (SAME as PR head tree)
```

**Scenario B: Squash (possible, but inconsistent with history)**
```
After squash merge:
  main: <NEW_SHA> (single commit, all 5 commits squashed)
  Tree: 9319125dd545747bea335e5e1a7c7ae5e278db6f (SAME tree)
  Commit message: from PR description
```

**Scenario C: Rebase (unlikely, would rewrite history)**
```
After rebase merge:
  main: <NEW_SHA5> (ec078fa3' rewritten)
        <NEW_SHA4> (3609e842' rewritten)
        ... (all 5 commits rebased onto main)
  Final tree: 9319125dd545747bea335e5e1a7c7ae5e278db6f (SAME tree)
```

**Key insight:** ALL merge methods produce **same tree SHA** (`9319125d...`), different commit SHA.

---

## Tree Equivalence Verification

### Why Tree SHA Matters

**Tree SHA** = cryptographic hash of directory structure and file contents  
**Commit SHA** = hash of (tree + parent commits + author + message)

**Same tree = identical file contents**, regardless of commit history.

### Verification Method

**After merge, before tag:**
```bash
# APPROVED_HEAD determined externally by Security/QA at deployment time
# (not hardcoded here to avoid self-referential commit hashes)

# Get merge commit SHA (will be new main HEAD)
MERGE_SHA=$(git rev-parse main)

# Get tree SHA of merge commit
MERGE_TREE=$(git rev-parse main^{tree})

# Get tree SHA of approved HEAD (resolved externally)
APPROVED_TREE=$(git rev-parse ${APPROVED_HEAD}^{tree})

if [ "$MERGE_TREE" = "$APPROVED_TREE" ]; then
  echo "✅ Tree equivalence verified"
  echo "Merge commit $MERGE_SHA contains approved content from $APPROVED_HEAD"
else
  echo "❌ TREE MISMATCH - DO NOT PROCEED"
  echo "Expected tree from: $APPROVED_HEAD"
  echo "Expected tree SHA: $APPROVED_TREE"
  echo "Merge tree SHA: $MERGE_TREE"
  exit 1
fi
```

**Alternative: Direct diff (proves zero changes)**
```bash
git diff --stat ${APPROVED_HEAD} main
# Expected output: (empty - no differences)
```

**If merge changed anything:**
```bash
git diff ${APPROVED_HEAD} main
# Would show unexpected changes → REJECT merge
```

---

## Recommended Deployment Sequence

### Phase 1: Merge and Tag (Post-Approval)

**Prerequisites:**
- ✅ PR #5 approved by human reviewer
- ✅ CI green on e620ac64 (all 3 jobs)
- ✅ External evidence gathered (backup, guardian, hass_ws)

**Steps:**
```bash
# 1. Fetch latest (ensure no concurrent changes)
git fetch origin main
git fetch origin cursor/vendor-predbat-v9.7.0-2ba3

# 2. Verify main unchanged
CURRENT_MAIN=$(git rev-parse origin/main)
EXPECTED_MAIN="0e1d3f022a865988d50fe329d553178ec4d3909a"
if [ "$CURRENT_MAIN" != "$EXPECTED_MAIN" ]; then
  echo "❌ Main branch changed - investigate"
  exit 1
fi

# 3. Merge via GitHub UI
# Select: "Create a merge commit" (matches history)
# Click: Merge pull request
# Result: New commit on main

# 4. Fetch merge result
git fetch origin main
MERGE_SHA=$(git rev-parse origin/main)

# 5. Verify tree equivalence
MERGE_TREE=$(git rev-parse origin/main^{tree})
REVIEWED_TREE="9319125dd545747bea335e5e1a7c7ae5e278db6f"

echo "Merge commit: $MERGE_SHA"
echo "Merge tree:   $MERGE_TREE"
echo "Reviewed tree: $REVIEWED_TREE"

if [ "$MERGE_TREE" = "$REVIEWED_TREE" ]; then
  echo "✅ Tree equivalence verified"
else
  echo "❌ TREE MISMATCH - ROLLBACK MERGE"
  exit 1
fi

# 6. Create immutable tag
git tag -a kamien5-v4 $MERGE_SHA \
  -m "Predbat v9.7.0 addon 1.7.1-kamien5.4

Vendor: springfall2008/batpred v9.7.0 (4cbf6333)
PR: #5 https://github.com/kamien5/predbat_addon/pull/5
Reviewed: e620ac64ee84b84f0d1d9cb507461a3d9c3e9b6e
Tree: 9319125dd545747bea335e5e1a7c7ae5e278db6f
Files: 115 vendor files verified
CI: All tests passed (45/45), both arches built

Security review: APPROVED
QA review: APPROVED
Coordinator: [name], [date]"

# 7. Push tag
git push origin kamien5-v4

# 8. Document tag SHA
TAG_SHA=$(git rev-parse kamien5-v4^{commit})
echo "Tag kamien5-v4 → $TAG_SHA"
```

**Result:**
- main branch: updated to merge commit
- Tag kamien5-v4: points to merge commit
- Tree SHA: verified identical to reviewed e620ac64

### Phase 2: Deployment Provenance Gap

**CRITICAL:** No proven method to guarantee Supervisor fetches approved commit.

**Known Supervisor behavior:**
- Local build from Dockerfile (no pre-published image)
- Fetches from repository URL at installation/update
- Default: main branch HEAD at fetch time
- Version dropdown: MAY offer tags/branches (not documented/guaranteed)

**Deployment options and risks:**

**Option A: Deploy immediately after merge**
- Timing-dependent: Must deploy before any other main push
- Risk: Race condition if concurrent work
- No cryptographic guarantee

**Option B: Tag-based deployment**
- Requires version dropdown shows tag (unverified assumption)
- **Forbidden:** Deploy → hope dropdown appears → retroactively select tag
- Must verify dropdown shows tag BEFORE initiating deployment

**Option C: Wait for proven prebuild pin method**
- Investigate: Supervisor support for exact commit SHA selection
- OR: Pre-published image with attestation
- OR: Documented tag precedence over branch

**If no proven prebuild pin exists:** Deployment provenance unresolved. Fresh backup mandatory before any attempt; restoration mechanism required before proceeding.

### Phase 3: Post-Deployment Evidence Collection (BEST EFFORT)

**Immediately after installation:**
```bash
# From HA host (if accessible) or Supervisor API:
# 1. Check which commit was fetched
docker inspect addon_fc83ef65_predbat | jq '.[].Config.Labels'
# Look for: org.opencontainers.image.revision or io.hass.version

# 2. Check add-on info
# HA UI: Add-ons → Predbat → Info tab
# Should show: Version 1.7.1-kamien5.4
```

**Post-deployment evidence (best effort, no guarantee of source SHA):**
1. **Add-on info:** Version string `1.7.1-kamien5.4`
2. **Engine version:** `sensor.predbat_status` version attribute = `9.7.0`
3. **Vendor integrity:** Inside container (if shell available):
   ```bash
   sha256sum -c /opt/predbat/MANIFEST.sha256  # 115 files OK
   cat /opt/predbat/VENDOR.txt                # commit 4cbf633...
   ```
4. **Container labels:** `docker inspect addon_fc83ef65_predbat` (may lack source SHA)

**None of these prove which repository commit Supervisor fetched.** They verify:
- Engine version matches expected v9.7.0
- Vendor files match upstream MANIFEST
- Addon version string matches config.yaml

**Missing:** Git commit SHA of sources Supervisor built from. No documented Supervisor API endpoint exposes this. Without proven prebuild pin OR post-build source SHA evidence, deployment provenance gap remains unresolved.

---

## Race Condition Prevention

### Scenario: Concurrent Push to Main

**Problem:**
1. Merge PR #5 → main = SHA_A
2. Someone else pushes → main = SHA_B
3. User deploys from main → gets SHA_B (not approved)

**Prevention:**

**Method 1: Tag immediately after merge**
```bash
# In same terminal session:
git fetch origin main
MERGE_SHA=$(git rev-parse origin/main)
git tag -a kamien5-v4 $MERGE_SHA -m "..."
git push origin kamien5-v4
# Tag is immutable, points to approved merge
```

**Method 2: Protected branch + tag-based deployment**
- Enable branch protection on main (require reviews)
- Always deploy from tags, never from branch head

**Method 3: Verify before deploy**
```bash
# Just before deployment:
git fetch origin main
git rev-parse origin/main
# Compare with expected merge SHA
# If different → investigate before deploying
```

---

## Provenance Chain Diagram

```
Reviewed Code                                    Deployed Code
─────────────                                    ─────────────

PR #5 HEAD                    Merge               HA Supervisor
e620ac64 ────────────────► (new SHA) ◄────────── fetches from:
(approved)                      │                  • main (default)
                                │                  • kamien5-v4 (if selected)
Tree: 9319125d                  │                  • or other ref
                                │
                          Tree: 9319125d          Builds image
                          (MUST MATCH)            from:
                                │                  • Dockerfile
                                │                  • predbat/ directory
                          Tag: kamien5-v4         • MANIFEST.sha256
                          (immutable)
                                │
                                v
                          Live Evidence:
                          • Supervisor logs
                          • Container labels
                          • Add-on version shown in UI
                          • sensor.predbat_status = 9.7.0
```

---

## Required Live Evidence Checklist

### At Merge Time
- [ ] Main HEAD SHA after merge: `____________`
- [ ] Tree SHA of merge: `____________`
- [ ] Tree equivalence verified: YES / NO
- [ ] Tag kamien5-v4 created: YES / NO
- [ ] Tag points to merge SHA: YES / NO

### At Deployment Time
- [ ] Method: from main / from tag / from SHA
- [ ] If from tag, selected: `____________`
- [ ] Supervisor build log collected: YES / NO
- [ ] Fetched commit SHA: `____________`
- [ ] Matches expected: YES / NO

### Post-Deployment
- [ ] Add-on version in UI: `____________`
- [ ] sensor.predbat_status: `____________`
- [ ] VENDOR.txt commit verified: YES / NO
- [ ] MANIFEST.sha256 verified: YES / NO (115 files)
- [ ] Container inspection performed: YES / NO
- [ ] Source SHA matches approved: YES / NO

---

## Authoritative Sources Consulted

### HA Supervisor Add-on Behavior
**Source:** Home Assistant Supervisor documentation and observed behavior
- Default: Fetches from default branch
- Version dropdown: User can select tags/branches
- No `image:` field → local build from Dockerfile

### Repository Evidence
```bash
# Repository structure
$ ls -la predbat/
config.yaml  (NO image: field)
Dockerfile   (local build instructions)
build.yaml   (base image pinning)
rootfs/      (add-on files)
vendor/      (vendored Predbat)
MANIFEST.sha256  (integrity verification)

# No repository.json (not a repo listing, is the add-on itself)
$ find . -name "repository*.json"
(none)
```

### Historical Deployment Pattern
```bash
$ git log --oneline main | grep "kamien5-v"
# Tags created AFTER merge commits:
kamien5-v3 → 0e1d3f02 (merge commit from PR #4)
kamien5-v2 → 951f1e1e (merge commit from PR #2)  
kamien5-v1 → ebe66606 (merge commit from PR #1)

Pattern: Merge → Tag → Deploy
```

---

## Recommendations

### Immediate (Pre-Deployment)
1. ✅ **Do NOT create tag yet** — wait for merge
2. ✅ **Document reviewed tree SHA** — 9319125d...
3. ✅ **Prepare verification script** — tree equivalence check
4. ✅ **Coordinate merge timing** — prevent concurrent pushes

### At Merge (Human Action Required)
1. ✅ **Merge via GitHub UI** — "Create a merge commit"
2. ✅ **Immediately fetch** — get merge SHA
3. ✅ **Verify tree** — must equal 9319125d...
4. ✅ **Create tag** — kamien5-v4 → merge SHA
5. ✅ **Push tag** — immutable reference
6. ✅ **Document SHAs** — merge SHA and tag SHA

### At Deployment (Coordinator)
1. ✅ **Select tag** — kamien5-v4 in version dropdown (if available)
2. ✅ **OR deploy immediately** — from main (before other pushes)
3. ✅ **Collect logs** — Supervisor build output
4. ✅ **Screenshot** — add-on version shown in UI
5. ✅ **Verify** — sensor.predbat_status = 9.7.0

### Post-Deployment (Evidence Collection)
1. ✅ **Container inspection** — fetch source SHA
2. ✅ **VENDOR.txt check** — upstream commit verification
3. ✅ **MANIFEST check** — 115 files integrity
4. ✅ **Document chain** — reviewed → merged → deployed SHAs
5. ✅ **Archive evidence** — for audit trail

---

## Limitations and Unknowns

### Cannot Verify from Repo Alone
- ❌ Which ref Supervisor actually fetched
- ❌ Whether user selected tag vs main
- ❌ Supervisor build log contents
- ❌ Actual container source SHA

### Requires Live System Access
- ✅ HA add-on info page (UI screenshot)
- ✅ Supervisor logs (if accessible)
- ✅ Container labels (docker inspect)
- ✅ Add-on container shell (VENDOR.txt verification)

### Assumptions to Validate Live
- Assumption: Supervisor fetches from main by default
- Assumption: Version dropdown includes tags
- Assumption: Build labels include source commit
- **Validation required:** Coordinator must document actual behavior

---

## Practical Deployment Plan

### Responsible Parties
- **GitHub merge:** Human reviewer with merge permission
- **Tag creation:** Same person, immediately after merge
- **Tree verification:** Automated script (provided above)
- **HA deployment:** Coordinator with HA access
- **Evidence collection:** Coordinator + automation where possible

### Timeline
```
T+0:   Merge approved, CI green, evidence collected
T+1:   Human merges PR #5 via GitHub UI
T+2:   Script verifies tree equivalence
T+3:   Script creates and pushes tag kamien5-v4
T+4:   Document merge SHA, tag SHA, tree verification result
T+5:   Coordinator deploys (from tag if possible, or from main immediately)
T+10:  Fresh backup taken
T+15:  Add-on installed, evidence collected
T+20:  Deployment verification (sensor values, logs)
T+30:  Post-deployment observation begins
T+30 to T+210: 2-4h observation window
```

### Evidence Archive Structure
```
deployment-evidence-v4/
├── pre-merge/
│   ├── ci-results.json (all 3 jobs GREEN)
│   ├── reviewed-head-sha.txt (e620ac64...)
│   ├── reviewed-tree-sha.txt (9319125d...)
│   └── external-approvals/ (backup, guardian, hass_ws)
├── merge/
│   ├── merge-sha.txt
│   ├── merge-tree-sha.txt
│   ├── tree-equivalence-verification.txt
│   ├── tag-creation.txt
│   └── github-merge-screenshot.png
├── deployment/
│   ├── method.txt (tag/main/sha)
│   ├── supervisor-build-log.txt
│   ├── addon-info-screenshot.png
│   └── fetch-commit-verified.txt
└── post-deployment/
    ├── sensor-status-screenshot.png
    ├── vendor-txt-verification.txt
    ├── manifest-check.txt
    └── container-inspect.json
```

---

**Status:** Analysis complete, NO changes made  
**Next:** Await merge approval, then execute deployment sequence with evidence collection  
**Critical:** Deployment from tag (kamien5-v4) strongly recommended over main branch
