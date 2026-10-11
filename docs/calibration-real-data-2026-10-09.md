# Real-data calibration status (2026-10-09)

The camera and vision detector are online. Production motion remains disabled.
The active passive session contains **one real accepted pose**, not ten. The
supervised Auto sequence's `DRY_RUN_PASS` does not add observations or authorize
motion.

## Operator workflow

The operator page now exposes:

- **เก็บท่าจริง (ไม่สั่งขยับแขน)**: capture RGB-D and robot telemetry at the
  operator-positioned pose. No robot motion command is sent.
- **คำนวณคาลิเบรตจาก 10 ท่าจริง**: fit the first seven accepted observations,
  independently verify on the last three, save a session candidate, reload it,
  and repeat independent verification.
- **ทดสอบลำดับ AUTO (DRY-RUN)**: the existing non-moving plan simulation.

An on-site operator must assess the workspace and position the robot safely.
Displayed targets are guidance, not permission to bypass collision checks.
Do not move a powered robot by hand unless the hardware's supported procedure
permits it. Keep the physical emergency stop available.

HTTP services (POST):

- `/api/calibration/passive/capture`
- `/api/calibration/passive/solve`

Inspect `/api/vision/calibration` → `passive_solve` for completion, metrics,
held-out verification, reload verification, and candidate location. HTTP request
acceptance is not calibration success. `REAL_POSES_REQUIRED: 1/10` means nine
additional independent real poses are needed.

The solver initializes unknown mount rotation from measured AX=XB translation
evidence; a preverified rotation is **not** required for this passive solve.
The as-built translation constraint and camera identity remain mandatory.

## Remaining production admission

`CANDIDATE_VERIFIED` is deliberately separate from production `READY`. A
candidate is stored inside the passive session and does not replace
`~/.ros/dobot/markerless_calibration.npz` or enable a motion flag.
Live safety/table reference, repeatability, real-object validation, and motion
commissioning must still pass before production picking is authorized. The
numeric table datum in the robot base frame is not yet established; do not
assume controller Z=0 is the table surface.

Capture persistence now uses the exact RGB-D exposure timestamps, intrinsics,
and robot-history snapshot instead of newer live messages arriving during
registration. Existing observations are preserved unchanged for audit.

## Operator-authorized real smoke-test attempt

After the operator confirmed being present, the live scene baseline passed.
The actual `/calibration/auto/start_smoke_test` service was invoked with
`operator_confirmed: true`. It returned `FAIL: HARDWARE_NOT_READY` during
pre-dispatch checks, `MOTION_SENT: false`, `PTP_RESTORE: PASS`,
`PTP_PARAM_STATE_UNCERTAIN: false`, and `ARM_TOKEN_REVOKED: true`.
No pose was collected and the robot stayed at approximately
`[150.010, 0, 99.990] mm`, J4=0 degrees. Hardware readiness subsequently
returned to READY; the failed response did not record which individual
hardware condition was transiently missing, so its cause is not yet proven.

The baseline rejection response had an `accepted` keyword collision, now
fixed without changing its admission policy. Smoke-test responses now include
the pre-dispatch snapshot and readiness blockers for future diagnosis.
