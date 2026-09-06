# Browser and Tool Usage Rules

## Interface preference
1. Reliable structured MCP/API/tool when available.
2. Playwright/browser-control MCP for dynamic/interactive websites.
3. Manual browser interaction only when necessary.

## Filter-first search rule (mandatory)
Every search site (LinkedIn Jobs/People/Posts, Indeed, career pages, job boards)
exposes its own filter UI: date posted, experience level, remote/on-site,
company, location, connection degree, content type, salary, and similar facets.

- **Never reduce a search to a bare keyword query.** Keyword-only searches are
  incomplete runs, not comprehensive ones.
- **Use the site's native filters for every search**, applying at minimum:
  recency/date-posted, geography, and the facet that matters most for that
  source (experience level for Jobs; connection degree + current company for
  People; date posted + content type for Posts).
- **Navigate the UI like an agent**: open the page, read its state (filter
  panel, result count, active chips, sort order), apply/adjust filters based
  on what the UI actually shows, verify the applied filters are reflected in
  results, then paginate/sort as needed. Do not fire blind pre-built URLs and
  assume the filter state.
- URL parameters (e.g. `f_TPR`, `f_E`, `geoId`, `network`, `currentCompany`)
  are acceptable shortcuts ONLY when they mirror what the UI filter would set;
  after navigating, confirm from the page that the filters registered (active
  filter chips / result count). If a param is ignored, fall back to clicking
  the filter controls in the UI.
- Record which filters were applied per search in the run log
  (`tracking/search_runs/search_runs.csv` notes) so coverage is auditable.

## Mandatory browser tests for Playwright-connected agents
Any agent or worker that operates a browser through the Playwright MCP tools
(`mcp__playwright__browser_*`) MUST be exercised through a real browser test
before its workflow is considered working:

1. **Unit-level contract first** — pure logic behind the browser flow (URL
   builders, parsers, merge logic) is covered by pytest and must pass before
   any live run.
2. **Live smoke test per workflow change** — after creating or modifying an
   agent's browsing behavior, run at least one live navigation of its target
   site (navigate → apply filters → verify page state → extract) and record
   the outcome (page reachable, filters registered, rows extracted).
3. **Evidence, not claims** — report real extracted row counts / screenshots /
   page state; never mark a browser workflow verified without an actual run.
4. **Discipline during tests** — reuse tabs, close them afterwards, respect
   rate limits, and log coverage to `tracking/search_runs/search_runs.csv`
   when the test touches discovery sources.

## Browser-control rule
When real browser interaction is required, prefer Hermes' Playwright/browser-control MCP. Do not solve research by continuously spawning Chrome tabs.

## Tab discipline
- reuse tabs;
- keep a small working set;
- avoid one permanent tab per job/person;
- reuse LinkedIn/company search tabs;
- close temporary tabs when done;
- avoid duplicates;
- clean browser state after completing a task.

Typical working set: one LinkedIn search tab, one company-careers tab, one job/application detail tab, temporary tabs only when necessary.

## Task-oriented browsing
Every browser session needs a defined objective: e.g. find NVIDIA roles, inspect 15 referral candidates, search recent hiring posts, verify 10 jobs, or fill one application. Complete the goal, persist results, then clean up.

## Authentication
If login is required, ask the user to authenticate directly in the browser and reuse authenticated sessions/autofill/extensions. Never ask to store passwords, OTPs, recovery codes, or secrets in project files/chat.

## Failure handling
If a site blocks automation or requires login, record the failure, request authentication when needed, continue with other useful sources, and never mark the source as successfully searched when it was not.
