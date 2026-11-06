# Auto Calibration diagnosis and software repair — 2026-11-05

The live process reported `SCENE_VERIFY_FAILED` with zero accepted poses and
no motion command. The camera and robot telemetry were ready. The persisted
optical scene signature came from an earlier calibration viewpoint; the
automatic backend treated it as if it belonged to the current TCP pose.

For a new fit, the backend now measures a reference at the current pose after
a fresh continuous ten-second admission window. A second capture must pass
the existing scene comparison before planning/authorization. Acquisition also
checks the measured exposure pose, cancellation and readiness. The previous
passive baseline remains unchanged. The new reference is stored with its
actual pose, run ID, workspace, camera and mount identity in the automatic
session. Saved-calibration verification and the verified commissioning
handoff retain their existing reference checks.

The backend now checks the starting envelope before scene comparison and
reports `START_POSE_OUTSIDE_WORKSPACE` with the current TCP and signed
clearance margins. The operator page explains that result in Thai using the
existing installation limits. Those ranges describe envelope containment,
not a validated target or recovery trajectory.

Existing installation data allows envelope centers approximately X170.25–204.25,
Y−25.50–25.50, Z124.50–150.00 mm. The live TCP observed before deployment was
approximately [57.742, 0, −15.356, 0] mm/degrees. Its starting envelope is
outside the recorded free volume. No validated path from this position exists
in the available data. Expanding the workspace or shrinking the measured
attachment envelope to permit it would assert new physical evidence.

This repair does not complete physical calibration. Full trajectory validation,
real commissioning, run authorization, independent calibration verification
and live acceptance still apply. No settings, physical measurements, operator
acknowledgements or calibration results were invented.

## Verification

Calibration and Web regression suite: 437 collected, 435 passed after fixing
one new test fixture that omitted the context normally initialized by camera
preparation; 2 Node.js tests skipped because Node.js is absent. The first full
run passed 434 tests; the one corrected fixture was rerun separately and
passed. Runtime code was unchanged between those two runs. Tests used ROS
domain 231 with localhost discovery and mocked robot transport.

Coverage added for fresh run references, preservation of existing evidence,
the ten-second gate, timeout, cancellation, lost readiness, moved exposure
poses, independent scene comparison, and rejection of the observed outside
starting pose before capture, PTP changes or motion. `git diff --check` passed.

JUnit results: `/tmp/autocal-fix-regression.xml` and
`/tmp/autocal-fix-recheck.xml`.

## Deployed result

Restarted `dobot-magician.service` after three fresh stationary, alarm-clear
samples with no robot or operator job active. `STARTUP_AUTO_MOTION=false`
remained configured. The running calibration source digest is
`31d83ca3bb410fd47bf69f3627a98f725dd92d839006722a99a4f30dd69ee03d`.

Live preparation now reports `START_POSE_OUTSIDE_WORKSPACE`, with containment
deficits of 112.508 mm at X-min, 139.856 mm at Z-min, and 135.956 mm against the
table-clearance policy. These are conservative model violations, not measured
physical contact. It accepted zero calibration poses and sent no calibration
motion command. The fresh-run reference path is regression-tested but cannot
be reached on this hardware until its starting pose passes the geometry gate.

[Before restart](evidence/auto-calibration-fix-2026-11-05/before.json) and
[live result](evidence/auto-calibration-fix-2026-11-05/after.json).

## Explicitly requested HOME and reference check

The operator next requested HOME and use of its measured position as the
reference. The existing `/dobot_homing_srv` target was read as
[150, 0, 100, 0] mm/degrees. One `/dobot_homing_service` request was sent
after idle-operation, fresh-feedback and clear-alarm checks. Its response
only acknowledged that homing started; completion was determined separately
from feedback reaching the configured target and remaining stationary for
three seconds. No alarms appeared in the observed homing samples.

Observed home TCP: [150, 0, 100, 0] mm/degrees; joints [0, 3.05, 13.7, 0]
degrees. This was recorded as a start-pose reference in `magician_base_link`,
not a new coordinate origin or new free-volume measurement.

The automatic commissioning preflight then used the live home position as
its anchor (approximately [150.026, 0, 99.961] mm at preparation).
Run `ca6e9b16250c47a2b07b6f975ef1bfaf` stopped at
`START_POSE_OUTSIDE_WORKSPACE`: X-min deficit 20.224 mm, Z-min deficit
24.539 mm, table policy deficit 20.639 mm. Zero calibration poses were
accepted, no calibration motion was sent, and PTP restoration was not
required. The HOME motion itself was executed as explicitly requested.

[Measured home reference](evidence/home-reference-20261105T060232Z/home-reference.json),
[homing feedback](evidence/home-reference-20261105T060232Z/home-feedback.json),
[calibration preflight from home](evidence/home-reference-20261105T060232Z/calibration-from-home.json).
