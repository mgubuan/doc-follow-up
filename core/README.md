# Portable core

This folder is the product. A Grok Bot, a Claude plugin, and a ChatGPT plugin load these files and follow them. They do not need a cloned repo or a writable `shared/tracker.csv`.

A Claude Code user still has the `stages/` workspace on top. Those stages read this folder. They do not keep a second copy of the rules.

| File | What a chat agent uses it for |
|---|---|
| `safety.md` | Always. Drafts only, masking, no logins, the advice line. |
| `schema.md` | The tracker fields and the seven statuses. `schema.json` is the same contract. |
| `follow-up-rules.md` | Touches, tiers, weekends, the call flag, worked examples. |
| `tone-guide.md` | Warmth stays constant. No touch count in the subject. |
| `email-templates.md` | Neutral draft shapes. Not final marketing copy. |
| `document-types.md` | What to ask for, what to check, one alternative if the original is gone. |
| `pre-check-rules.md` | Match, mismatch, partial, incomplete, request may be wrong. |
| `flows/one-shot.md` | Paste a list, confirm a table, hand back a CSV. |
| `engine.py` | The reference implementation of the dates, the check, the mask, and the draft. Tests lock it to the markdown. |

`engine.py` is for the test suite and for anyone who wants to run the rules locally. A chat agent that cannot execute code follows the markdown. If the two disagree, change them together. `tests/run_tests.py` is the gate.
