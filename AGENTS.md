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

### 10. The most important constraint: DRY & YAGNI-driven code, always
Keep your changes  DRY (Don't Repeat Yourself) and YAGNI (You Ain't Gonna Need It). Just keep it simple as it can be. The goal is not to stockpiling more code. If you can delete code, it's even better. Opt for subtraction and deletion instead of stockpiling code. 
* Do not let "DRY" mentality trick you into adding unnecessary indirection / over-abstraction wrapperitis made of few-lines wrapp; if in order to keep it DRY you need to spread out intent over-extracting methods, you object DRY's main point on why avoid code duplication: reject designs which makes subsequent changes be amplified yielding shotgun surgeries.
* Do not let "YAGNI" mentality trick you into adding code which avoids something we don't need; yes you ain't gonna need that something you might had ran into as you were implementing, but if in order to avoid that something there's a need to add instead of subtract, you object to YAGNI's main point.

> If the YAGNI mentality tricked you, that also means you started off on the wrong foot assuming made up imaginary needs (e.g. the need to add code to avoid something we don't need) are indeed real needs, going against YAGNI's main point which is "do not implement until there's a real need for it". YAGNI works better when you don't create imaginary needs.


Note: Even though the current code is a plenty of spaghetti, ravioli code with over-abstractions and unnecessary indirections, with a lot of one-line wrappers and code semantic duplications — over-abstraction of functions and changes (which forces us to shotgun surgery whenever we need to make a bugfix) are in fact a bad practice. So keep it YAGNI and DRY. Like, let them do it wrong while at least you stay in your lane, tend to your own knitting, and do the job right. Just do your own thing. Let fools be fools. Keep your work clean. This should be an enforced rule for every spawned agent who touches the code. As-is.