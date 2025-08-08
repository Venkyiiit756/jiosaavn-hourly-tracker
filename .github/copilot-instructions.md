<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

Current purpose:
A minimal, headless Python script (run via GitHub Actions hourly) that fetches JioSaavn play counts and stores per‑song history as JSON plus a summary file.

Guidelines for suggested changes:
1. Preserve strict hourly granularity (no intra-hour writes unless design explicitly changes).
2. Keep storage simple: append JSON entries (timestamp, play_count). Avoid reintroducing CSV or a database.
3. Favor minimal dependencies (requests, BeautifulSoup, pytz only unless strongly justified).
4. Ensure network fetch robustness (timeout, limited retries, graceful failure without crashing workflow).
5. Never allow decreasing play counts to overwrite higher stored values.
6. Writes must be atomic (temp file + replace) for JSON artifacts.
7. Keep summary lightweight (current, hour delta, 24h delta). Avoid heavy analytics unless requested.
8. Avoid adding Flask / web UI unless explicitly asked (legacy UI deprioritized).
9. Keep code readable: small functions, no premature abstraction.
10. Keep GitHub Actions workflow fast (< ~10s typical). No long loops or large data processing.
11. If adding features (retention, anomaly detection, config), make them opt-in and default to current minimal behavior.
12. Log succinctly: only note fetch failures, skipped (same hour), appended entries.
13. Timezone: continue using Asia/Kolkata and store timestamps as 'YYYY-MM-DD HH:MM:SS IST'.
14. Do not introduce minute-level scheduling logic.
15. Avoid storing redundant derived metrics inside history entries (summary file handles that).

When uncertain, choose the minimal path and ask for clarification.
