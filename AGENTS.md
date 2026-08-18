# Custom Agent Rules

## Prioritize Implementation Plan Over Test Criteria
- **Rule**: Always strictly prioritize the approved implementation plan over satisfying outdated, conflicting, or failing test assertions.
- **Action**: Never re-introduce dead code, anti-patterns, or deviations from the approved architecture simply to make legacy or incorrect tests pass. Instead, update and refactor the test assertions to properly validate the approved implementation plan.
