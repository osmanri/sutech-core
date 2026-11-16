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

## Honesty rules

- Do not invent statistics, quotes or results; unknown values stay `[in brackets]` until the owner supplies them.
- The experiment result and field data do not exist yet; the study in `research/` is model against model.
- The code was written with an AI assistant; say so honestly wherever authorship is described.
