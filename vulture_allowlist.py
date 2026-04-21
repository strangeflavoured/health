# vulture_allowlist.py
#
# Purpose: suppress Vulture false positives for code that IS used, but not
# in a way Vulture can trace statically (dynamic dispatch, DI frameworks,
# Docker entrypoints, Redis-OM field descriptors, etc.).
#
# How to use:
#   - Run `vulture src/ --make-whitelist` to generate an initial list.
#   - Move only INTENTIONAL suppressions here; fix genuine dead code.
#   - Keep entries grouped by reason so reviewers understand each decision.
#
# Vulture reads this file as valid Python, so syntax must be correct.
# Each entry is a reference that makes Vulture believe the symbol is used.
