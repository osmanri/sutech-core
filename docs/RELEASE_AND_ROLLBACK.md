# Su-Tech pilot release and rollback

This release pairs the `fao56.10` bot with the frontend pinned by the core
repository. `5eac4f3` is the previously verified core release. Record the next
merge SHA and both deployment runs before using it in a demonstration.

## Test gate

1. Check out the core commit and its recursive submodules. Run `npm ci` in
   `serverless`, followed by `npm test` and `npm run build`.
2. Run `frontend/test_*.cjs` and `frontend/test_*.js` with Node. The core tests
   compare the engine and generated catalog byte for byte and exercise Mini App
   transport, including cancellation and old links.
3. Run `node serverless/test/demo-browser.cjs` after the build with Playwright
   Chromium installed. CI checks a mobile viewport, three languages, language
   persistence, both soil greenhouse cases and the blocked substrate example.
4. Run the Python suite and compiled firmware host test. Check the matching
   GitHub Actions runs after merge. A green firmware host test covers simulated
   inputs and relay state. Bench measurements require a separate hardware check.

## Demonstration

Open `demo.html?example=greenhouse&lang=ru`. Show the tomato example in soil,
then select the heated example and explain what the measured ET₀ input means.
Select the substrate example to show where the method stops. For an internet
fallback, serve the built `serverless/dist` folder from localhost and open the
same page. Calculations use local JS and can run with all external requests
blocked. Device fonts are sufficient. The prepared pitch PDF is also offline.

## Recover a bad code release

Identify whether the bot modules, static Mini App, or both are affected. Check
the first failing step and the revision shown by `tgcloud status` before making
changes. GitHub Actions can deploy both parts from a reviewed revert to the
last verified pair of commits. Revert through a PR, run the same gates, and
confirm the deployed component and revision. Use `fetch` before the component
push and keep the revision check active. If the other component deployed first,
inspect the conflict before rerunning the failed job.

Task 4 introduces persistent application deletion markers. Reverting to code
from before Task 4 drops the protections while that code runs. Prefer a fix
forward when the defect touches deletion or user data. For data recovery use
the separate staging procedure in [DATA_RECOVERY.md](DATA_RECOVERY.md). A code
rollback cannot undo an executed deletion or any user activity.
