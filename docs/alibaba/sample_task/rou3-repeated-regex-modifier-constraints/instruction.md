Repeated route parameters with inline regular expression constraints should keep those constraints after modifier expansion.

When a parameter with a regex constraint uses a one-or-more or zero-or-more modifier, every matched segment in the repeated value must satisfy the inline regex. Interpreted lookup, match-all lookup, and compiled lookup should agree on both accepted and rejected paths, and the collected parameter value should remain the joined repeated path segments.

Unconstrained repeated parameters, optional single-segment parameters, catch-all wildcards, static routes, method matching, and existing compiled-router ordering should continue to behave as before.

Use the packaged repository to make the code change, add or update tests as needed, and leave the project in a working state. Preserve existing public behavior outside the requested change.
