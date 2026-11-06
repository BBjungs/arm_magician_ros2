# Proposed calibration start and tracking reserve — 2026-11-05

The operator requested increasing values and running the robot while present
at the machine. The prepared change raises the HOME endpoint from
[150, 0, 100, 0] to [187.25, 0, 137.25, 0] mm/degrees within the existing
workspace. No measured free-volume bounds, table datum, attachment envelope
or physical-clearance requirement has been enlarged or reduced.

The previous fitted plan touched several measured boundaries exactly. It
could be rejected on live feedback with a small tracking deviation despite
the existing 2 mm settling tolerance. Automatic planning now requires a
2 mm target reserve, tries additional rigidly scaled/translated candidates,
and checks training and held-out excitation and independence using the
unchanged solver thresholds before collision checking. Runtime validation
still checks the actual segment against the original workspace.

The offline plan from the proposed start passes all existing joint and
collision checks. Its target ranges are X173.25–201.25, Y−21–21,
Z126.75–147.75 mm, with at least 2.25 mm reserve beyond the unchanged
workspace clearance. This validates the calibration plan from the new
endpoint, not the firmware's HOME procedure path from the current pose.

[Offline plan evidence](evidence/auto-calibration-start-2026-11-05/offline-plan.json).

Targeted regression: 112 passed and one JavaScript test skipped because
Node.js is absent. The final offline plan was checked after the small-scale
candidate skip condition was corrected. `git diff --check` passed.

The existing hardware HOME target remains [150, 0, 100, 0]. No HOME or
calibration motion was issued in this turn. An on-site confirmation question
is pending: E-stop and STOP tested, swept area clear, and mount secure. These
facts cannot be inferred solely from the operator being at the machine.
The run authorization implementation requires explicit acknowledgements in
`motion_authorization.py`; no acknowledgement has been synthesized.

The updated planner was loaded by a guarded service restart with startup
motion disabled. Live source digest:
`cfe06e5cb409611408b07ca6173560e1166edb54cfac29df8b3742e480a2cfa4`.
The unchanged current HOME position still correctly fails starting-envelope
validation; calibration motion remains false and accepted poses remain zero.
[Deployment evidence](evidence/auto-calibration-start-2026-11-05/deployment/after.json).

## Subsequent confirmed execution

The user subsequently explicitly confirmed E-stop, STOP, a clear swept area
and a secure camera/bracket. The live HOME target was changed to
[187.25, 0, 137.25, 0] mm/degrees, read back from the homing parameter service,
and one HOME was executed. Feedback reached that target and remained
stationary for three seconds with clear alarms. The target was persisted in
`dobot_homing/config/homing_params.yaml`.

Commissioning run `255ef12295284ae6802fee691439d27f` passed the starting-pose
check but failed before plan authorization/motion with
`No sufficiently supported dominant plane`. No calibration poses were
accepted. The diagnostic captured three stationary depth frames: valid-depth
coverage was 48.5–49.0%, but the best plane support was 27.6–29.5%, below the
unchanged 30% requirement. Offline refinement also remained below 30%; no
quality thresholds were relaxed. The user then requested a design that uses
Depth and a persistent mount transform rather than repeated calibration.

[HOME evidence](evidence/authorized-calibration-20261105T142203Z/after-home.json),
[commissioning result](evidence/authorized-calibration-20261105T142242Z/latest.json),
[depth diagnostic](evidence/plane-diagnostic-20261105T142533Z/report.json),
[new design](depth-picking-persistent-mount-design.md).
