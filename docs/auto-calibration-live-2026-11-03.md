# Auto Calibration deployment and live check — 2026-11-03

The operator explicitly authorized hardware testing, reported the expanded
installation inspected, and confirmed the exact proposed base-frame bounds:
X −8.35…382.85, Y −204.10…204.10, Z −54.10…328.60 mm. The configuration
records this as operator attestation, not an independent physical survey by
the assistant. Table Z −58 mm and the existing 25 mm clearance were retained.

Installed [configuration](../config/calibration-workspace-operator-confirmed.yaml)
at `/home/jetson/.ros/dobot/calibration_workspace.yaml`, bound to camera
AY2A760003E and the actual runtime mount fingerprint. Workspace digest:
`fcde7f4a974f4df8199a48ea889415bdff4d5209e879119454ee1bab43188ca4`.
The runtime now accepts this installation file; WORKSPACE_NOT_CONFIGURED is
resolved. No PTP parameter change or robot motion was issued during this work.

## Software fixes deployed

- Decimal serialization caused exact workspace boundaries to fail with a
  reported deficit of 0.000 mm. Added an arithmetic tolerance of 1e-12 m;
  the physical 25 mm clearance and mount uncertainty remain unchanged.
  Tests prove a 1e-9 m boundary violation is still rejected on all six box
  faces and at the table.
- Live preflight exposed `not enough values to unpack (expected 3, got 2)`.
  `_table_touchoff_stability()` returns `(stable, diagnostics)`. Fixed callers
  in automatic preparation and physical-stop confirmation before PTP restore.
  Regression tests use the actual stability function with robot history.
- When no plan anchored at the current pose fits, the planner can translate
  the complete existing plan within confirmed bounds. Translation preserves
  all relative displacements and rotations. It still validates current-pose
  entry, every subsequent segment, reach, soft joint limits and collisions
  before a per-run authorization can be issued. Plans too large for the volume
  and starting positions outside the volume remain rejected.
- The previously saved web fix that prevents showing robot READY with active
  or stale alarms was also loaded by the service restarts.

Targeted regression result: **104 passed, zero failures/errors/skips**.
[JUnit evidence](evidence/manual-workspace-20261102T162330Z/software-regression-104-tests.xml).
The fitted-plan regression includes the suction-cup collision model.
`git diff --check` passed for changed calibration source and tests.

The hardware service was restarted only after fresh, stationary, alarm-clear
feedback and idle-operation checks. `STARTUP_AUTO_MOTION=false` remained set;
no HOME or observation-pose motion was requested. The new software digest
reported by the live process is
`c35a73824fbf9564975a0cefa3ccb472d193fadde8807ef70618ff259b35098b`.

## Actual hardware result

The real RGB-D stream passed hardware readiness, acquired its initial scene
baseline with the continuous admission gate, and passed scene comparison.
Final depth-valid ratio was approximately 37.81%; the threshold is 35%.
No active alarms or motion goals were reported.

Run `a0fcc544b0d84f498b8cba8396ec73db` reached FAULT with
NO_FEASIBLE_AUTOMATIC_PLAN. The actual TCP was approximately
`[119.683, 145.491, 50.416, 50.559]` mm/degrees. Its attachment envelope lies
outside the confirmed box and fails the configured table-clearance bound.
The tool-center range allowed by the box and conservative envelope is
X170.25…204.25, Y−25.50…25.50, Z124.50…150.00 mm.

An interior starting pose `[187.25, 0, 137.25, 0]` mm/degrees passes the
offline fitted-plan test. This validates that endpoint and the subsequent
local-model plan, not a path from the current robot pose. Positioning into
the start region requires an on-site procedure with its actual route checked
by the operator. The assistant did not send a recovery move from the rejected
pose. After repositioning, fresh telemetry, scene rebaselining, hardware
readiness, full-plan validation, commissioning and per-run authorization
remain required.

Current result: zero accepted calibration poses, motion_command_sent=false,
PTP_RESTORE=NOT_REQUIRED, production_ready=false.
[Live evidence](evidence/manual-workspace-20261102T162330Z/installed-final-live.json).
