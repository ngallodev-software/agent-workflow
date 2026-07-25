# License Selection Decision Memo

**Project**: `agent-workflow`  
**Use case**: Terminal-first control plane for distributed agent execution and workflow orchestration  
**Distribution model**: PyPI package + source repository  
**Date**: 2026-07-25

---

## Project Requirements Analysis

### Use Case and Constraints

`agent-workflow` is a Python CLI and optional MCP server that:

- **Executes operator-delegated coding agents** (Codex, Claude, explicit commands) in isolated Git worktrees and tmux sessions
- **Preserves durable evidence**: prompts, argv, logs, patches, provider events, sealed receipts, completion handoffs
- **Manages workflow DAGs** with approval gates, result bindings, retries, and parallel execution
- **Validates prompt packs deterministically** with cross-phase dependencies
- **Supports agent lifecycle**: status, attach, tail, interrupt, terminate, restart, review, acceptance, rejection
- **Provides optional MCP adapter**: read-only, bounded to configured roots, no daemon or remote transport

### Key Licensing Concerns

1. **Commercial use compatibility**: Must allow commercial users to run agent workflows (end-user integration with Codex, Claude, and third-party agents)
2. **Derivative works and proprietary extensions**: Organizations should be able to:
   - Deploy as internal tools without publishing modifications
   - Build proprietary agents/executors on top of the control plane
   - Integrate into closed-source products
3. **Patent safety**: GPL v3 has explicit patent grants; ASF 2.0 and MIT do not. Patent risk is moderate since the project is primarily orchestration logic, not novel algorithmic claims.
4. **Upstream dependencies**: 
   - **Core**: `jsonschema>=4.18,<5` (Apache 2.0)
   - **Optional eval**: `inspect-ai` and `inspect-swe` (likely permissive; verify)
   - **Optional MCP**: `mcp==1.28.1` (need to confirm license)
   - **Optional telemetry**: OpenTelemetry (Apache 2.0)
5. **Downstream compatibility**: 
   - Users integrate with Claude API, OpenAI Codex, and proprietary agent frameworks
   - No requirement to open-source integrations
   - Community expects permissive licenses for development tools (precedent: Click, Typer, Pydantic)

### Community Expectations

- **Similar projects**: 
  - Task orchestration: Airflow (Apache 2.0), Prefect (Apache 2.0), Temporal (MIT/elastic)
  - Agentic systems: LangChain (MIT), AutoGen (Python Software Foundation), Crew AI (MIT)
  - Git/worktree tools: most are MIT or Apache 2.0
- **Development-tool precedent**: Python CLI frameworks favor permissive licenses (Typer, Click, Pydantic all MIT)

---

## License Candidates

### Apache License 2.0

**Pros:**
- Permissive for commercial use and proprietary extensions
- Explicit patent grant and termination clause protects licensees and licensor
- Compatible with downstream proprietary derivatives (no copyleft requirement)
- Industry standard for data infrastructure and orchestration tools (Airflow, Prefect, OpenTelemetry)
- Clear patent grants help commercial users evaluate risk
- Mature, well-tested license with extensive case law

**Cons:**
- Slightly longer and more complex than MIT
- Requires license and notice preservation in binary distributions
- Minimal administrative burden; well-understood by enterprises
- Not "maximally permissive" (one more requirement than MIT)

**Fit for this project:** ✅ **Strong fit**
- Enterprise/commercial users likely to deploy this in production need patent certainty
- Orchestration-first architecture is common in enterprise infrastructure
- Patent termination clause protects against frivolous litigation
- No barrier to proprietary extensions or internal-use variants

### MIT License

**Pros:**
- Maximally permissive; no conditions on use or modification
- Shortest, simplest license; minimal legal noise
- Common in Python ecosystem; familiar to contributors
- Works well for libraries and tools with many downstream users
- Zero friction for closed-source derivatives

**Cons:**
- No explicit patent grant (implicit, but less certain for risk-averse orgs)
- No patent termination clause; patent litigation risk remains
- Does not explicitly address trademark issues
- Rare for orchestration/infrastructure software (typically Apache 2.0 or GPL)

**Fit for this project:** ⚠️ **Acceptable, but suboptimal**
- MIT is simpler and has lower friction
- Patent risk is moderate (control-plane logic, not algorithmic innovation)
- Large enterprises may prefer Apache 2.0 for patent certainty
- If simplicity is priority and patent risk is accepted, MIT works

### GPL v3

**Pros:**
- Ensures all derivatives remain open-source (strong copyleft)
- Explicit patent grant and termination clause
- Protects against proprietary appropriation of community work
- Strong community alignment for ethical licensing

**Cons:**
- **Critical incompatibility**: GPL v3 requires derivative works to be open-source
  - Proprietary agents built on `agent-workflow` would need GPLv3 (not negotiable)
  - Companies building closed-source products cannot use this as a base
  - Users integrating with proprietary Codex/Claude executors may face legal ambiguity
- Complicates commercial adoption and enterprise integration
- Limits downstream ecosystem (fewer extensions, fewer collaborators)
- **Project vision conflict**: README and CONTRIBUTING.md describe current scope as terminal-first CLI; scope expansion and extensions are likely; GPL limits extension ecosystem

**Fit for this project:** ❌ **Poor fit**
- Project is a foundation for downstream agent work, not a complete product
- Proprietary extensions (custom executors, integrations) are use cases, not violations
- GPL forces a philosophical choice users likely do not want to make

### Other Candidates Considered

**AGPL v3**: 
- Triggers copyleft on network use; not applicable here (no network exposure)
- Even more restrictive than GPL v3 for this use case; rejected

**BSD (2-Clause or 3-Clause)**:
- Functionally equivalent to MIT (2-Clause) or MIT + trademark clause (3-Clause)
- Slightly more enterprise-friendly wording; no technical advantage
- Less common in Python; not chosen

**MPL 2.0 (Mozilla Public License)**:
- File-level copyleft; good middle ground between Apache and GPL
- Complexity not justified for a single-owner, focused project
- Less familiar to Python ecosystem

---

## Tradeoff Analysis

| Criterion | Apache 2.0 | MIT | GPL v3 |
|---|---|---|---|
| **Commercial use** | ✅ Full | ✅ Full | ❌ No (derivatives) |
| **Proprietary derivatives** | ✅ Yes | ✅ Yes | ❌ No |
| **Patent safety** | ✅ Explicit grant | ⚠️ Implicit | ✅ Explicit grant |
| **Simplicity** | ⚠️ 1 page | ✅ 12 lines | ⚠️ 3+ pages |
| **Python ecosystem precedent** | ✅ (infrastructure) | ✅ (libraries) | ⚠️ (rare) |
| **Enterprise adoption** | ✅ Standard | ✅ Acceptable | ❌ Rejected |
| **Downstream ecosystem** | ✅ Open | ✅ Open | ❌ Restricted |
| **Trademark/IP clarity** | ✅ Standard | ⚠️ Not addressed | ✅ Standard |

### Compatibility Analysis

**Apache 2.0 + Downstream Consumers:**
- Proprietary agent executors: ✅ Can be closed-source
- Claude API integrations: ✅ No license restrictions
- Codex integrations: ✅ No license restrictions
- Custom workflow DAGs: ✅ Can remain proprietary
- MCP adapters: ✅ Can be proprietary
- Test packs and evaluation code: ✅ Can be proprietary

**MIT + Downstream Consumers:**
- Same as Apache 2.0; no further restrictions

**GPL v3 + Downstream Consumers:**
- Proprietary agent executors: ❌ Must be GPL v3 (likely deal-breaker)
- Custom integrations: ❌ Must be GPL v3
- Forces philosophical choice on users (not ideal for infrastructure)

### Contribution Policy Alignment

Current CONTRIBUTING.md requires:
- Acceptance-first (issues/backlog before work)
- Single canonical execution path
- Security-sensitive analysis
- Release-gate compliance

These are **compatible with any permissive license**. GPL v3 would add burden by requiring derivative-work disclosures, but the project is not currently using GPL, so this is forward-looking rather than a constraint.

### Long-Term Maintenance Burden

**Apache 2.0:**
- Clear governance (patent indemnification, explicit grants)
- Legal clarity supports long-term stewardship
- Easier to attract enterprise contributors (familiar process)
- No additional enforcement burden

**MIT:**
- Minimal legal overhead
- No expectation management needed
- Simplest path, lowest maintenance

**GPL v3:**
- Requires vigilance on derivative-work disclosures
- Potential legal disputes with commercial users
- Higher enforcement burden if licensing violations occur
- Reduces contributor pool

---

## Recommendation

### **Recommended License: Apache License 2.0**

#### Reasoning

1. **Permissive scope**: Allows commercial use, proprietary derivatives, and closed-source integrations without restriction—aligned with project vision of being a foundation for downstream agent work.

2. **Patent certainty**: Explicit patent grant and termination clause provide legal clarity for enterprise users who may be risk-averse. Given that `agent-workflow` integrates with proprietary agent platforms (Codex, Claude), enterprise users will appreciate this clarity.

3. **Industry precedent**: Orchestration and infrastructure tools standardize on Apache 2.0 (Airflow, Prefect, OpenTelemetry, Kubernetes). This signals maturity and enterprise-ready governance.

4. **Downstream compatibility**: No conflict with downstream proprietary integrations, custom executors, or closed-source workflow DAGs. Users can build on top of `agent-workflow` without licensing friction.

5. **Contribution barriers**: Apache 2.0 is well-understood in Python and infrastructure communities. It does not discourage contributions from individuals or small teams.

6. **Upstream dependency compatibility**: 
   - `jsonschema` (Apache 2.0) ✅ Compatible
   - OpenTelemetry (Apache 2.0) ✅ Compatible
   - `mcp` (verify, likely permissive or Apache) ✅ Likely compatible
   - No GPL dependencies ✅ No copyleft conflict

#### Alternative (MIT)

**If simplicity is strongly prioritized**: MIT is also acceptable and removes the one-page-document barrier. However, the lack of explicit patent grant makes it slightly less attractive for enterprise deployment and orchestration software. The incremental complexity of Apache 2.0 is justified by the legal clarity it provides.

#### Not Recommended (GPL v3)

GPL v3 is fundamentally incompatible with the project's role as a foundation for proprietary agent work and integrations. It would force users to choose between open-sourcing their customizations or not using `agent-workflow` at all—an unnecessary constraint for infrastructure software.

---

## Implementation Notes

### Next Steps

1. **Dependency verification**: Confirm license of `mcp==1.28.1` and `inspect-ai`/`inspect-swe`. If any are GPL-licensed, revisit and document incompatibility or upgrade path.

2. **Add LICENSE file**: Place standard Apache 2.0 text at repository root (`LICENSE` file, no extension).

3. **Update pyproject.toml**: Add license classifier:
   ```toml
   [project]
   license = { text = "Apache-2.0" }
   classifiers = [
     # ... existing classifiers ...
     "License :: OSI Approved :: Apache Software License",
   ]
   ```

4. **Update package metadata**: Ensure `NOTICE` file exists if required (Apache 2.0 requires preserving license/notice in distributions; setuptools handles this automatically for wheel distributions).

5. **Document in README**: Add a line referencing the license:
   ```markdown
   ## License
   
   `agent-workflow` is licensed under the Apache License 2.0. The repository license file is still required before release.
   ```

6. **Legal review** (optional): If the organization has legal counsel, brief them on the choice and confirm it aligns with organizational practices.

### Open Questions for Maintainers

- Are there proprietary integrations or extensions planned that would benefit from explicit permission to remain closed-source? (Apache 2.0 is more defensive here.)
- Does the organization have existing open-source licensing standards (e.g., all projects must be Apache 2.0)?
- Is patent risk a realistic concern, given the domain and competitive landscape?

---

## Conclusion

**Apache License 2.0** balances permissiveness, legal clarity, and industry precedent. It removes licensing friction for commercial users and downstream derivatives while providing the explicit patent grants and governance structures expected in infrastructure software. This positions `agent-workflow` as a mature, enterprise-ready foundation for agent orchestration.
