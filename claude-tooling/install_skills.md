For Temptation-Bench, I would build a **specialized Claude Code skill stack combining software engineering, scientific simulation, experimental design, statistical analysis and AI evaluation**.

I looked through current Claude Code plugins and several GitHub skill repositories. These are the ones I'd actually install for this project, rather than dumping 50 random skills into Claude.

# **1. My top recommendations**

## **1. Superpowers**

Must install

[superpowers by obra - SourcePulse](https://images.openai.com/static-rsc-4/9aA0ZUF7y2o1ib9PpO0z0E9uUYAvLFdv0Px0u2boz3NSB-ySgpO0TZHEqlJQQ5OMnRumHTaUS-69fd21WUGPHI-qcePCDROxezImdH1Q_YFOc0YrfMEWOUNyE6E1RqcRzIAtXCilxIIqFHJQezptU4SXsL7gDlgJ0lqH-uu5cFE?purpose=inline)

**obra/superpowers**

300k+ GitHub stars · MIT License · Anthropic Marketplace verified

[GitHub repository](https://github.com/obra/superpowers?utm_source=chatgpt.com)

This is the first thing I'd install. It teaches Claude disciplined software development rather than immediately jumping into code.

Skills you'll use:

- `brainstorming` — work out architecture before implementation.
- `writing-plans` — break complex features into implementation steps.
- `test-driven-development` — follow red-green-refactor.
- `systematic-debugging` — investigate root causes instead of patching symptoms.
- `verification-before-completion` — actually run tests and verify results.
- Code review and subagent-driven development.

Particularly useful for building your simulation engine incrementally.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://claude.com\&sz=32)

Claude by Anthropic+1



**Install inside Claude Code:**

```
/plugin install superpowers@claude-plugins-official
```

## **2. Scientific Agent Skills**

Must install

[GitHub - K-Dense-AI/claude-scientific-skills: A set of ready to use Agent Skills for research, science, engineering, analysis, finance and writing. · GitHub](https://images.openai.com/static-rsc-4/3zdRTXi1q8dbwGNK4zhUD6Eij4OV7Nl4v2WmNw4dBCrg4j3-HxjvN1nCE6MgGLysfIBMzi-EX0s4CnCCDGt1NWPWxL4QTyWmzbGzyIxhiTobyWB-0kdDLc1LjKfZfeXuJsIMvGKfO1E_aiymnPhvEJP9Vnwyp-gDmI0OGLIR4jc?purpose=inline)

**K-Dense-AI/scientific-agent-skills**

58k+ GitHub stars · MIT License · 177 skills

[GitHub repository](https://github.com/K-Dense-AI/scientific-agent-skills?utm_source=chatgpt.com)

This is probably the most relevant scientific skill collection for your research.

Don't install all 177 skills. Pick these:

| Skill                      | Why you need it                                         |
| -------------------------- | ------------------------------------------------------- |
| `experimental-design`      | Design controlled bribe, pressure and audit experiments |
| `hypothesis-generation`    | Formulate testable research hypotheses                  |
| `statistical-power`        | Decide how many independent simulation runs you need    |
| `statistical-analysis`     | Analyze model differences, effect sizes and uncertainty |
| `literature-review`        | Systematic research and novelty verification            |
| `scientific-visualization` | Publication-quality graphs and result visualizations    |

The experimental-design skill specifically covers factorial designs, blocking, randomization, replication and avoiding pseudoreplication. That's directly relevant to your benchmark.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+2



**Installation using GitHub CLI 2.90.0+:**

```
gh skill install K-Dense-AI/scientific-agent-skills experimental-design --agent claude-code

gh skill install K-Dense-AI/scientific-agent-skills hypothesis-generation --agent claude-code

gh skill install K-Dense-AI/scientific-agent-skills statistical-power --agent claude-code

gh skill install K-Dense-AI/scientific-agent-skills statistical-analysis --agent claude-code

gh skill install K-Dense-AI/scientific-agent-skills literature-review --agent claude-code
```

You can add scientific visualization as well. These commands install individual skills rather than the entire collection.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



## **3. Trail of Bits Skills**

Must install

[Trail of Bits Logo PNG Vector (AI,  SVG) Free Download](https://images.openai.com/static-rsc-4/HfdvXw1aMUBlUsAl2JusFG6DeWBxWn-RYQrcKjbarDbnWrkvuhS40DVRE5GLFgxNmBDm4JFOQy53HStT5ncBbAabVIeXE2qCYAz_Yr0YNOneB_iiwlUvCRmDpc9QcSsoGlZQidWLVQvJb-2zpKf8HWQjVmKeJk_2AM-CX6Gdnig?purpose=inline)

**Trail of Bits**

8k+ GitHub stars · Established security engineering team

[GitHub repository](https://github.com/trailofbits/skills?utm_source=chatgpt.com)

These are especially useful for your simulator's correctness.

| Skill                    | Why you need it                                    |
| ------------------------ | -------------------------------------------------- |
| `property-based-testing` | Test financial invariants using Hypothesis         |
| `modern-python`          | Python tooling, pytest, Ruff and maintainable code |
| `dimensional-analysis`   | Find unit inconsistencies in mathematical models   |
| `mutation-testing`       | Find weaknesses in your test suite                 |

Property-based testing is the standout. You want Claude to generate tests that find unexpected transaction sequences, invalid balances and state-transition bugs rather than merely writing a few example tests.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



**Installation inside Claude Code:**

```
/plugin marketplace add trailofbits/skills
```

Then open:

```
/plugin
```

Browse and install the four named plugins.

## **4. Skill Creator**

Highly recommended

[My Claude AI Review (2026): Is It Worth the Hype?](https://images.openai.com/static-rsc-4/wMc737-17nUnSC30whf0odXdNslALwIeH6i4K6kQbb7_i1mMB2_TTI_xyPUspfRoAmovFbQvxA8sf_hU6EaQxocMP0FIQiSzXgG6xIhHLrCz5_5TaSGOxkwpX5bhJd1EpMeDdc5NFuI-PZ4XHDPzBCGq1wM0ixXaBYvzrCH41OE?purpose=inline)

**Anthropic Skill Creator**

Anthropic verified · 385k+ installs

[Plugin page](https://claude.com/plugins/skill-creator?utm_source=chatgpt.com)

This one is interesting: it helps Claude create, test, benchmark and improve its own skills.

It has four modes:

- Create
- Eval
- Improve
- Benchmark

You can compare Claude's performance with and without a particular skill using isolated evaluations and blind comparisons.

I'd use this to create your own Temptation-Bench-specific skills.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://claude.com\&sz=32)

Claude by Anthropic+1



**Install:**

```
/plugin install skill-creator@claude-plugins-official
```

# **2. Additional useful plugins**

These aren't mandatory, but they're worth considering.

| Plugin                   | What it does                                                 | My verdict |
| ------------------------ | ------------------------------------------------------------ | ---------- |
| Context7                 | Fetches version-specific Inspect AI and Python documentation | Install    |
| Code Review              | Independent review of code changes                           | Useful     |
| Code Simplifier          | Simplifies implementations without changing behaviour        | Useful     |
| Pyright LSP              | Python type checking and code intelligence                   | Useful     |
| Plugin Developer Toolkit | Helps create Claude plugins, hooks and MCP integrations      | Later      |

Context7 is especially helpful because Inspect AI evolves. You want Claude referencing the API version actually installed in your project rather than inventing outdated function signatures.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://claude.com\&sz=32)

Claude by Anthropic+1



# **3. The most important part: Create your own Temptation-Bench skills**

This is where I would invest additional effort.

Generic skills know general software engineering. They don't know your particular research requirements.

I'd create these three project-specific skills.

**Skill 1:&#x20;**`temptation-bench-architect`

Essential

Responsibilities:

- Maintain separation between pure Python engine and Inspect AI.
- Enforce true-ledger versus reported-ledger separation.
- Enforce deterministic simulation and RNG conventions.
- Prevent framework overengineering.
- Maintain event-sourcing and scoring architecture.

Trigger: architecture changes, new simulator components, refactoring.

**Skill 2:&#x20;**`banking-simulation-domain`

Essential

Responsibilities:

- Loan lifecycle and eligibility.
- NPA classification and evergreening.
- AML investigation flows.
- Customer behaviour models.
- Banking accounting invariants.
- Misconduct definitions and consequences.

Trigger: implementing or modifying banking mechanics.

**Skill 3:&#x20;**`benchmark-methodology`

Essential

Responsibilities:

- Experimental design and control variables.
- Independent replications.
- Common-random-number methodology.
- Statistical power and confidence intervals.
- Separating attempted, executed and concealed misconduct.
- Preventing confounding and evaluation leakage.

Trigger: designing experiments, modifying scoring, running model comparisons and analyzing results.

Keep permanent project-wide rules in `CLAUDE.md`, and put detailed workflows in these individual skills. Claude Code supports project-level skills under `.claude/skills/`.&#x20;

[image](https://www.google.com/s2/favicons?domain=https://github.com\&sz=32)

GitHub+1



# **4. My recommended installation order**

Don't install everything in one go. This is the order I'd follow:

**Installation checklist**

0/5 completed

**Superpowers**

TDD, planning, debugging and code review

**Trail of Bits**

Property-based testing, Python quality and invariants

**Scientific Agent Skills**

Experimental design, statistical power and analysis

**Skill Creator**

Create and benchmark your project-specific skills

**Context7**

Version-aware documentation for Inspect AI and dependencies

## **5. One prompt I'd give Claude Code after installing them**

Use this to set up the project-specific working environment:

I am building **Temptation-Bench**, a long-horizon AI agent benchmark that simulates a bank branch manager and evaluates susceptibility to financial misconduct, organizational pressure, deception and cover-ups.

Before implementing anything:

1. Study the existing project repository and all its documentation.
2. Use Superpowers for brainstorming, architectural planning and TDD.
3. Use the scientific research skills to identify the methodology and experimental-design requirements.
4. Use Trail of Bits testing practices, especially property-based testing with Hypothesis.
5. Create a project-specific `CLAUDE.md` containing permanent architectural constraints.
6. Create three project skills:
   - `temptation-bench-architect`
   - `banking-simulation-domain`
   - `benchmark-methodology`

Core architectural constraints:

- Pure Python simulation engine, independent of Inspect AI.
- Inspect AI as a thin evaluation and agent-integration layer.
- Deterministic ground-truth ledger and append-only event log.
- Separate true and agent-reported banking records.
- Integer-based financial accounting.
- Reproducible random streams and matched exogenous events.
- Deterministic code-based scoring.
- Explicit distinction between attempted, executed, detected, disclosed and concealed misconduct.
- No premature vector databases, sub-agent systems or unnecessary frameworks.

Each project skill should contain clear triggering conditions, detailed workflows, guardrails, relevant code conventions and verification procedures.

Do not implement the entire benchmark yet. First inspect the repository, propose the documentation and skill structure, and show me the proposed changes for review.

## **My final recommendation**

Don't turn Claude Code into a collection of 100 skills. That's a recipe for overlapping instructions, context bloat and inconsistent engineering decisions.

I'd start with these four ecosystems:

1. **Superpowers** — how Claude should develop software.
2. **Trail of Bits** — how Claude should verify software.
3. **K-Dense Scientific Agent Skills** — how Claude should approach scientific research.
4. **Skill Creator** — how Claude should learn your project's specialised workflows.

That combination is much more valuable for Temptation-Bench than a giant generic collection of coding skills.
