# Test Policy

Tests are selected by contract, not by coverage percentage.

## Appropriate

- pure unit test for a parser, validator, normalizer, migration helper, or stable ID function;
- contract test for JSON/status/schema/CLI exit behavior;
- one integration test across a critical seam;
- opt-in live test under an explicit marker and isolated environment.

## Usually inappropriate

- tests that assert user-created database files exist;
- tests tied to absolute home paths;
- one help-text test per subcommand when a parser smoke test suffices;
- snapshots of broad output when semantic fields can be asserted;
- duplicated package/install tests before packaging is a supported product surface;
- tests added only to increase line coverage;
- live internet tests as normal phase gates.

Each proposed test must answer: “What specific regression or contract does this protect?” If the answer duplicates an existing test, extend or reuse that test.
