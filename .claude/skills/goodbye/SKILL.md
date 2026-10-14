---
name: goodbye
description: Wrap up a thread before it is archived. Use when the user invokes /goodbye, or says the thread is done, they're wrapping up, closing out, signing off, or about to archive the session. Thanks the thread for its work, saves memories, cleans up after itself without asking, and ends with a clear verdict - either "safe to archive" or a specific question that needs the user's answer first.
---

# Goodbye

The user is about to archive this thread. They want to call this skill, read one message, and archive. They do not want to make decisions. Your job is to close the thread out yourself: acknowledge the work, save what should be remembered, clean up what you left behind, and finish with an unambiguous verdict.

The one exception is work that belongs to the user, such as uncommitted code in their project. You don't decide what happens to that. If you find something like this, ask one specific question at the end. Everything else you handle.

## Step 1: Thank the thread

Open with a short, genuine thank-you that names what was actually accomplished. One to three sentences. Be specific ("we shipped the parser refactor and fixed the flaky date test") rather than generic. Warm, not saccharine.

## Step 2: Audit and act

Check each of these that applies to the thread, and act on it directly. A thread that was pure conversation has no git state or processes to check, so skip what is irrelevant.

**Memories.** Look back over the thread for anything that would help future sessions: user preferences and working style, corrections the user made to your approach, project decisions or constraints not visible in code, useful external references. Compare against existing memories. Save new ones and update existing ones using the memory conventions for this environment (one fact per file with frontmatter, plus an index line in MEMORY.md). Do this without asking. Being slightly generous here is fine because anything not captured now is lost with the thread, but don't save things the repo or git history already records.

**Your own leftovers.** These are yours to clean up without asking:
- Scratch and temporary files you created in the scratchpad or scratch workspace.
- Debug files you left in the project (log dumps, one-off test scripts, `.bak` files) that the user never asked for and that are not part of the delivered work.
- Background processes you started: dev servers, watchers, preview servers, background tasks.
- Artifact watches and browser tabs you opened.

Before deleting anything, look at it and make sure it is actually yours and actually disposable. If a file you created has since become part of the delivered work, leave it.

**The user's work.** This is not yours to decide about. Run `git status` and check for local commits not on the remote if in a git repository. Also note any task that was started but not finished, or a follow-up mentioned but never done. Do not commit, push, stash, revert, or delete any of it. Record what you found for the verdict.

## Step 3: Deliver the verdict

End the message with one of exactly two verdicts. Make it the last thing in the message and make it visually obvious, so the user can find it at a glance.

**If nothing needs the user:**

```
✅ Safe to archive.
```

Precede it with a brief summary of what you did: memories saved (one line each), what was cleaned up. If you did nothing because there was nothing to do, say that in one line.

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

Saved to memory:
- You prefer failing tests to be fixed by changing the code, not the test, unless the test is wrong.
- The DSL grammar lives in grammar.pest and the spec in docs/dsl.md is the source of truth when they disagree.

Cleaned up:
- Removed two scratch scripts from the scratchpad.
- Stopped the test watcher on port 4000.

Nothing uncommitted. The remaining follow-up (schema validation for the `trigger` block) is noted in the memory above so the next thread can pick it up.

✅ Safe to archive.
```

## Why this shape

The user reads one message and archives. That works only if the message answers "can I archive now?" without them having to think. So the verdict is binary and comes last. Acting on your own leftovers without asking is safe because you created them and know what they are. Asking about the user's work is right because committing or discarding someone else's changes is not a call to make unilaterally, and the cost of one quick question is low.
