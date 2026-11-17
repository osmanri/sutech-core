# Rules for Claude working in this repository

## Commit and push after every change (owner's standing instruction)

After **each** completed change (code, docs, presentation sources, data), without being asked again:

1. `git add` only the files that belong to the change (never secrets, never large temporary files);
2. commit with a message that says *what* and *why*;
3. push to the working branch `claude/project-competition-review-f8o9yv` (`git push -u origin <branch>`);
4. tell the owner in the reply that it is pushed and give the commit hash.

Run the tests for what you touched before committing. Do not push to any other branch and do not open a pull
request unless asked. The sibling repository `sutech-frontend` (the website) follows the same rule.

At the start of a session check `git status` and `git log origin/<branch>..HEAD` so nothing is left unpushed.

## Authorship of commits (owner's instruction, 17 November 2026)

- Every commit is authored and committed as `Osman <osmanchelovek@gmail.com>` (set `git config user.name` / `user.email` in each clone).
- Never add `Co-Authored-By: Claude`, `Claude-Session` or "Generated with Claude Code" lines to commit messages or pull request descriptions.
- On 17 November 2026 the history of this repository and of `sutech-frontend` was rewritten so that older commits carry the same author. The state before the rewrite is kept in the branches `backup/before-author-rewrite-20261117-main` and `-branch` (delete them when no longer needed).
- This is about commit metadata only. The honesty rule below still applies: the paper and the website say that the code was written with an AI assistant.

## Honesty rules

- Do not invent statistics, quotes or results; unknown values stay `[in brackets]` until the owner supplies them.
- The experiment result and field data do not exist yet; the study in `research/` is model against model.
- The code was written with an AI assistant; say so honestly wherever authorship is described.

## Merging and deploying (owner's standing instruction)

The owner only sends requests in chat. After a change is committed and pushed:

1. open a pull request from the working branch into `main` and merge it yourself (the owner authorised this);
2. a merge that touches `serverless/**` or `bot/**` triggers `.github/workflows/deploy-bot.yml`, which runs the bot tests
   and publishes the bot (modules only, never `--force`, never the Mini App). Check the run is green and report it;
3. if the run is red, read the job log, fix, and repeat; never leave `main` red;
4. the bot's live code is backed up daily by `backup-live-bot.yml` to the branch `live-bot-backup`: if that branch exists,
   the live bot differs from `main`. Merge it into `main` (ignoring CR/LF differences) before deploying anything.

Full plain-language guide for the owner: `docs/HOWTO.md`. Secret `BOT_ENV` (text of `bot/.env`) is already set in GitHub.

## Repository layout (after the tidy-up of 17 November 2026)

- Python tests live in `tests/` (run `python3 run_tests.py`); bot tests in `serverless/test/`; website tests in the `frontend` repository.
- Documents are in `docs/` (old audits in `docs/audits/`, archive in `docs/archive/`); only README, REPRODUCE, CHANGELOG, CITATION and LICENSE stay in the root.
- Crops are edited ONLY in `crops/catalog.json`, then `python3 crops/build.py`; the engine copy in `frontend/js/sutech-engine.js` and the generated crop files must be copied to the frontend repository byte for byte (a test enforces it).
- Add every user-visible change to `CHANGELOG.md`.
