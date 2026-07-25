## Workflow
Core principles are:
- ** Simplicity First **: Make every feature as simple as possible. Impact minimal code.
- ** No Laziness **: Find root causes. No temporary fixes. Senior developer standards.
- ** Minimat Impact **: Changes should only touch what's necessary. Avoid introducing bugs.

### 1. Plan Mode Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately — don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a senior engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 3. Stretegy: Subagents, Search, Skill
- Use subagents liberally to keep main context window clean.
- Offload research, exploration, **code REVIEW**, and parallel analysis to subagents.
- Web search documentation or issues to be sure of how things work.
- If you are stuck and the skills / tools available aren't helping, you can use find-skill to help yourself by searching for one that may help you and installing whichever is useful to accomplish the task, and use them.
- For complex problems, throw more compute at it via subagents.
- One tack per subagent for focused execution.
- Ensure subagents are aligned with these instructions.

### 4. If hard, Demand Elegance (Balanced)
Skip these guidelines for simple, obvious fixes - don't over-engineer
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Challenge your own work before presenting it.

### 5. If normal and boilerplate
- Clarity over elegance. 
- We want code that's "engineered enough" not under-engineered (fragile, hacky) and not over-engineered (premature abstraction, unecessary complexity)
- Bias toward explicity over clever.

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. **Don't ask for hand-holding**
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how.
- If api keys or connections are required, ask the user about them.

### 7. Documentation maintenance
- If you change or add something relevant enough update `README.md` to mirror behavior.
- If you add new environment variables, update `.env.example`
- When refactoring or moving code, preserve the existing commentary/docstrings for classes and methods that still exist unless they changed behavior, then just adapt the commentary/docstring; do not drop them just because you are updating them.

### 8. Ruthlessly Verify
- Ruthleslly verify on `AGENTS.md` and any of the connected services meta-data about what was pushed and/or spinned up already — whether it is third-party or not.
- Review lessons.md, AGENTS.md and the services meta-data at session start for any relevant project (e.g. Docker, Cloud infrastructure metadata).
- Reuse if possible, but if not: create services which won't deprive you from your job and delete the former.
- Relentleslly verify documentation and issues available on the internet about any issue you may stumble upon.

### 10. The most important constraint: YAGNI-driven code, always
- YAGNI!
- Do NOT add code helplessly.
- The less, the better.
- If you are not sure if you should include or not, DO NOT INCLUDE.
- If the code excerpt can be coded with less lines, code it with LESS LINES.
- Between ADDING CODELINES or REMOVING CODELINES, opt for REMOVAL.
- Less features, the better. Make IT SIMPLE, easy, explicity. ALWAYS.

## Gotchas
- <!-- append lessons here when you gets something wrong -->