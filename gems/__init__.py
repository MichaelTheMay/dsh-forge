"""The hidden-gem system.

Separate from the app on purpose. It reads the published discovery queue (a JSON
file), looks inside the most promising repositories, and writes ``gem-picks.json``.
The app only ever reads that picks file, so this package can change, be evaluated
and be moved to its own repository without touching app code.

Nothing here imports from ``dsh_forge``.
"""

PICKS_SCHEMA = "dsh-forge.gem-picks/v1"
REVIEW_SCHEMA = "dsh-forge.gem-review/v1"
INSPECTION_SCHEMA = "dsh-forge.gem-inspection/v1"
POLICY = "dsh-forge.gems/two-stage-v1"
