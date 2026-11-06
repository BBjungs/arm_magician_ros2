# Auto Calibration hardware check — 2026-11-02

Physical robot and camera AY2A760003E were connected. Live TCP, joints and
alarm feedback were fresh, and depth was valid. The robot reported alarms
45 and 48 (the driver's decimal-looking hexadecimal labels): joint 3 negative
limit and parallelogram positive limit. Live joint feedback was approximately
[0, 5.39, -84.58, 0] degrees; TCP was [26.565, 0, 280.746, 0] mm/degrees.
No recovery motion or HOME was commanded, and alarms were not cleared.

The HTTP commissioning request returned 503, `Maintenance access is not
configured`. The local ROS `/calibration/autonomous/commission` preparation
service was exercised without issuing any plan authorization. Run
`79db95aa80ca482dafcd9d65741e465c` reached FAULT with
`WORKSPACE_NOT_CONFIGURED: /home/jetson/.ros/dobot/calibration_workspace.yaml`.
Its diagnostics also recorded the active alarms and missing scene baseline.
Accepted poses: 0; motion command sent: false; PTP restore: NOT_REQUIRED.
This is a real preflight check, not a completed physical calibration.

The operator API incorrectly displayed the robot as ready whenever the action
server was available and idle, even with active alarms. It now requires fresh
alarm feedback, an explicit clear state and an empty alarm-code list. The
robot check and top-level fault message display the alarm reason. Regression
coverage includes active, stale, missing and contradictory alarm reports.

Validation: 41 tests passed across test_operator_ui.py, test_auth.py and
test_autonomous_api.py in isolated ROS domain 231. The modified files passed
git diff --check. These tests use mocked robot transport. The running web
process has not been restarted, so the UI fix is saved in source but is not
yet loaded by the live service. Restarting the complete hardware service
also clears alarms during bringup; this was not used as alarm recovery.

Remaining physical prerequisites: resolve the actual joint/link limit state
at the workcell and supply surveyed free-volume limits. The existing
commissioning measurement form explicitly identifies its former TCP values
as simulation inputs, not measured free space. No verified workspace values,
operator acknowledgements, commissioning results or calibration results were
invented. Maintenance credentials also remain unconfigured for HTTP control.

Live evidence: [before](evidence/auto-calibration-hardware-2026-11-02/before.json)
and [after commissioning preflight](evidence/auto-calibration-hardware-2026-11-02/after-commission-preflight.json).

## Retry after the operator requested another attempt

Live alarms were now empty and hardware readiness was READY. Current TCP was
approximately [208.159, 29.527, 75.893, 8.074] mm/degrees. Commissioning run
`d7100c0b149f44f1a06f89d3cc1626cb` again stopped at WORKSPACE_NOT_CONFIGURED;
its other blocker was SCENE_BASELINE_MISSING. No motion was sent, no poses
were accepted and PTP restoration was not required.

A stationary workspace observation successfully acquired three real depth
frames. Its result was INSUFFICIENT_OBSERVATION: stable valid pixels were
42.30%, the observed region was too small for the clearance policy, and the
camera-to-base transform and whole-robot environment remained unverified.
The measured surface patch was approximately 128.6 x 28.9 mm at a camera
depth of 179–185 mm. This patch is not a measured free volume or a verified
table datum. No workspace configuration was generated from it.

Retry evidence: [preflight](evidence/auto-calibration-hardware-2026-11-02/retry-commission-preflight.json)
and [stationary observation](evidence/auto-calibration-hardware-2026-11-02/retry-workspace-observation.json).

## User-supplied XYZ bounds

The user supplied X170–230, Y−70–70, Z50–120 after being asked for free-volume
bounds in millimetres in the robot base frame. These were recorded separately
in `commissioning-workspace-input-2026-11-02.yaml`; the earlier measurement
history was preserved. The user subsequently explicitly confirmed these are
the entire free-volume bounds including the camera and suction tool, not a
TCP target region. This resolves the scope question; the geometry rejection
below remains unchanged. The audit file records the input fingerprint before
this scope-only clarification was added to the input record.

The existing read-only audit evaluated the supplied box against fresh robot
feedback and all eight planner variants. Result: zero feasible geometry
variants, exit code 1 (expected geometry rejection), no motion command.
The box dimensions are 60 x 140 x 70 mm. The configured conservative sphere
requires 2 x (152.6 mm radius + 1 mm uncertainty + 25 mm clearance) = 357.2 mm
in each dimension even at a stationary pose. Thus no center position can fit
the configured sphere inside the supplied box. The current anchor also fails
the sphere/table clearance check by approximately 44.7 mm. These are bounds
from the configured model, not evidence of an observed physical collision.
No runtime workspace or verified flags were written.

Evidence: [supplied bounds audit](evidence/auto-calibration-hardware-2026-11-02/user-bounds-audit.json).
