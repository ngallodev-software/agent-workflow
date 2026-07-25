# Future acceptance specifications

These are black-box journeys for backlog behavior that is intentionally not implemented yet.
They run against the installed wheel and are marked `xfail(strict=True)`: the expected failure
keeps the specification visible, while an unexpected pass fails the suite until the scenario is
reviewed and promoted into `tests/acceptance/`.

Do not add parser, dictionary-shape, or mocked-helper expectations here. A future test must name
an approved backlog item and exercise a complete operator-visible outcome.
