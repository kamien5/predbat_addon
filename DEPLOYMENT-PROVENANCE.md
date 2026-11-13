# ⚠️ OBSOLETE — See DEPLOY-UPGRADE.md

This document has been superseded by **DEPLOY-UPGRADE.md** which consolidates all deployment procedures.

**Date obsoleted**: 2026-11-07  
**Reason**: Multiple contradictory deployment docs consolidated into single source of truth  
**Replacement**: [DEPLOY-UPGRADE.md](./DEPLOY-UPGRADE.md)

---

**Historical context** (preserved for reference only):

This document previously described Supervisor provenance tracking and merge/tag procedures.

**Critical issues** that led to replacement:
- Hardcoded tree hash `9319125d...` (from old commit, not dynamic check)
- "Deploy immediately from main" guidance (unsafe without source pin)
- T+5 deploy, T+10 backup order (backup must be FIRST)
- No clear blocker on unproven Supervisor source resolution

**DO NOT** follow procedures in this document. Use DEPLOY-UPGRADE.md instead.
