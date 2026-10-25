---
name: goodbye
description: Wrap up a thread before it is archived. Use when the user invokes /goodbye, or says the thread is done, they're wrapping up, closing out, signing off, or about to archive the session. Thanks the thread for its work, records its state on GitHub, saves lessons to memory and retires its own STATE memories, cleans up after itself without asking, and ends with a clear verdict - either "safe to archive" or a specific question that needs the user's answer first.
---

# Goodbye

The user is about to archive this thread. They want to call this skill, read one message, and archive. They do not want to make decisions. Your job is to close the thread out yourself: acknowledge the work, put its state where the next thread will find it, save what should be remembered, clean up what you left behind, and finish with an unambiguous verdict.

The one exception is work that belongs to the user, such as uncommitted code in their project. You don't decide what happens to that. If you find something like this, ask one specific question at the end. Everything else you handle.

## Step 1: Thank the thread

Open with a short, genuine thank-you that names what was actually accomplished. One to three sentences. Be specific ("we shipped the parser refactor and fixed the flaky date test") rather than generic. Warm, not saccharine.

## Step 2: Audit and act

Check each of these that applies to the thread, and act on it directly. A thread that was pure conversation has no git state or processes to check, so skip what is irrelevant.

**State goes to GitHub.** The thread's project state is what is in flight, what was ruled, what was left over, and what a follow-up needs. It goes on the issue or PR it belongs to, as a comment, or on a new issue when nothing holds it. A new issue follows the repo's filing rules: search first, then a kind and a reachability label. A tracker record reaches every machine, every cloud session and the next thread. A memory reaches only this machine, and it decays into a false present-tense claim once its thread is gone. Do this without asking, and the summary names each comment and issue. The repo is public, so one kind of state stays out of the tracker: private notes such as spend, a plan to contact someone, or anything about the user's own machine. Those stay in memory, slimmed to that private remainder.

**Memories.** Save what no GitHub record can hold: lessons that are timeless and scoped to their class, user preferences and working style, corrections the user made to your approach, useful external references. Compare against existing memories and update one rather than duplicate it. Use the memory conventions for this environment: one fact per file with frontmatter, plus an index line in MEMORY.md. Do this without asking. Be slightly generous with lessons, because one not captured now is lost with the thread. Don't save what the repo or git history already records.

**Retire your own STATE memories.** A STATE memory this thread wrote or owns is retired once its state is on GitHub or finished: delete the file and its index line, and rewrite every memory that links to it. A STATE memory still needed is refreshed instead, with today's date and the query that re-derives it. Leave other threads' STATE memories to the threads that own them.

**Keep the memory index inside its limits.** When `MEMORY.md` nears the loader's limits (`wc -c MEMORY.md`, `wc -l MEMORY.md`), retire closed STATE and fold same-class lessons into one file, rewriting every memory that links to a folded name. Never shorten index lines to fit: an index line exists to carry its memory's conclusion, and a trimmed one stops firing.

Auto memory is machine-local: the memory directory under `~/.claude/projects/` is not shared across machines or with cloud sessions, so a memory written from a cloud session, or from a machine the user does not work on, does not reach the next thread. In that case do not report a memory as saved. Anything that fits only a personal memory, such as a working-style preference, goes under "Needs your input" so the user can carry it, instead of being declared saved and lost.

**Your own leftovers.** These are yours to clean up without asking:
- Scratch and temporary files you created in the scratchpad or scratch workspace.
- Debug files you left in the project (log dumps, one-off test scripts, `.bak` files) that the user never asked for and that are not part of the delivered work.
- Background processes you started: dev servers, watchers, preview servers, background tasks.
- Artifact watches and browser tabs you opened.

Before deleting anything, look at it and make sure it is actually yours and actually disposable. If a file you created has since become part of the delivered work, leave it.

**The user's work.** This is not yours to decide about. Run `git status` and check for local commits not on the remote if in a git repository. Also note any task that was started but not finished, or a follow-up mentioned but never done; each is state, so it goes on its issue or PR as above. Do not commit, push, stash, revert, or delete any of the user's work. Record what you found for the verdict.

## Step 3: Deliver the verdict

End the message with one of exactly two verdicts. Make it the last thing in the message and make it visually obvious, so the user can find it at a glance.

**If nothing needs the user:**

```
✅ Safe to archive.
```

Precede it with a brief summary of what you did: state recorded on GitHub (each comment or issue, one line each), memories saved, STATE memories retired, what was cleaned up. If you did nothing because there was nothing to do, say that in one line.

**If something needs the user:**

```
⚠️ Needs your input before archiving:
1. [Specific question with the options spelled out, e.g. "3 uncommitted files in src/parser/ - commit them, or leave them for the next thread?"]
2. [...]
```

Keep the list short and each question answerable in a few words. Only put things here that you genuinely cannot decide yourself. Uncommitted or unpushed project work is the main case. Unfinished tasks are usually just informational and belong in the summary, not here, unless leaving them half-done would break something.

Once the user answers, act on their answers, confirm in one line, and close with:

```
✅ Safe to archive.
```

## Example of a clean close

```
Thanks for this one. We got the card DSL parser handling nested effects and the three failing round-trip tests are green.

Recorded on GitHub:
- The remaining follow-up (schema validation for the `trigger` block), as a comment on its issue, so the next thread can pick it up.

Saved to memory:
- You prefer failing tests to be fixed by changing the code, not the test, unless the test is wrong.

Retired:
- The STATE memory tracking this parser work, now that its PR is merged.

Cleaned up:
- Removed two scratch scripts from the scratchpad.
- Stopped the test watcher on port 4000.

Nothing uncommitted.

✅ Safe to archive.
```

## Why this shape

The user reads one message and archives. That works only if the message answers "can I archive now?" without them having to think. So the verdict is binary and comes last. Acting on your own leftovers without asking is safe because you created them and know what they are; a STATE memory is one of those leftovers, and a thread that archives without retiring it leaves the next thread a claim nobody is keeping true. Asking about the user's work is right because committing or discarding someone else's changes is not a call to make unilaterally, and the cost of one quick question is low.
