# Auto Calibration and operator interface update

The operator page now contains the camera, system/calibration status, job and
placement selection, START and an always-accessible STOP. It sends no startup,
commissioning, capture, calibration or authorization requests on load, polling,
selection changes or reload. START still repeats the server readiness checks.

## Changed files

- `dobot_web_interface/static/operator.html`, `operator.js`, `operator.css`:
  read-only calibration status, pose/percentage, accepted RGB-D count, results,
  last verified-save time and errors; STOP remains above the expanded camera.
- `dobot_web_interface/static/maintenance.html`, `maintenance.js`: existing
  commissioning, seven explicit confirmations, pause/resume/abort, manual
  capture/solve, dry-run, startup recovery and HOME controls moved here.
- `dobot_web_interface/web_interface.py`: authenticated Maintenance page/assets
  and command APIs, normalized-path access checks, internal executor credential
  compatibility, calibration status projection, startup STOP latch, and exclusion
  of manual movement/HOME while calibration is active. No API was removed.
- `dobot_web_interface/setup.py`: package the new Maintenance assets.
- `dobot_calibration/autonomous.py`, `autonomous_backend.py`, `geometry.py`,
  `node.py`, `passive_solver.py`: existing automatic worker used for startup,
  bounded image retries, reuse of saved geometry, explicit verify/save stages,
  atomic geometry persistence/reload and retained live-acceptance gating.
- `dobot_auto.launch.py`, `scripts/start_dobot_autostart.sh`: default to automatic
  startup inspection; automatic HOME/observation motion remains opt-in.
- Tests in both packages and their READMEs were updated.

Package roots are `src/magician_ros2/dobot_web_interface/` and
`src/magician_ros2/dobot_calibration/`. Python modules and static assets are in
the nested same-name Python module directory; `setup.py`, `launch/`, `test/`
and README files are directly under each package root.

Updated tests: calibration `test_automatic_calibration.py`,
`test_passive_solver.py`, `test_ros_adapter.py`; web `test_auth.py`,
`test_autonomous_api.py`, `test_autonomous_ui.py`, `test_operator_ui.py` and the
new `test_operator_calibration_ui.py`.

## Behavior and authorization

For new geometry: preflight and full plan validation → explicit scoped
authorization in Maintenance → ten move/settle/capture/validate steps → fit seven
poses → verify three held-out poses → atomic save and reload → restore PTP
parameters → evaluate production readiness. No per-pose button is required.

Image-quality failures retry up to three total captures at the same pose.
Rejected images never increment the accepted count. STOP, unsafe/stale sensors,
expired authorization, pose mismatch and storage failures do not retry motion.

A matching saved bundle uses its three independent verification poses with fresh
images and the same motion safeguards, without another ten-pose collection or
refitting. It does not assume that a saved file alone authorizes picking.

After two-pose commissioning the server prepares the next plan once; it never
copies commissioning authorization to that plan. Reloading a browser cannot
start another worker or generate a new motion permit.

Maintenance needs `DOBOT_MAINTENANCE_TOKEN` (or existing `DOBOT_WEB_API_TOKEN` /
`api_token`). Basic username is `maintenance`; API clients may use a Bearer token.
No configured credential means Maintenance is unavailable. Network credentials
are distinct from physical motion authorization. STOP/abort remain accessible.

## Hardware and remaining production integration

This update does **not** claim that the installation is production READY.
`live_acceptance_error` is retained. The current repository has no producer for
the complete live acceptance record: hardware, table stability, observability,
independent verification, repeatability, reload verification, real-object
validation and a READY geometry health check. That hardware-backed integration
must be completed before a verified geometry result can admit picking. The
automatic worker reports `AWAITING_LIVE_VALIDATION` instead of fabricating PASS.

The installation also needs measured workspace/mount geometry, an authoritative
scene baseline, fresh synchronized RGB-D and robot feedback, working safety
inputs/E-stop, two-pose commissioning and explicit authorization for each new
plan. HOME and observation-pose readiness must pass the existing startup gates.
The physical Emergency Stop remains independent of the software STOP.

No controller service was restarted and no real motion command was sent during
this implementation. Build/install and restart with the workcell safely stopped
before using the new backend and Maintenance routes; editing source does not
upgrade an already-running Python process.

## Automated verification

The complete tests in `dobot_calibration/test` and `dobot_web_interface/test`
exercise the state machine, solver/verification, authorization, retry exhaustion,
sensor loss, STOP, saved-bundle reuse, PTP restoration, persistence failures,
Maintenance access, DOM references, read-only polling and START admission.

Final result: **368 tests passed**, no failures. Chromium passed all three
viewports with no JavaScript errors. `git diff --check` passed.

Tests run with `ROS_DOMAIN_ID=231`, `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`,
mocked hardware and temporary ROS logs. Chromium checks use intercepted HTTP
responses only: 1440×1000, 390×844 and 768×1024, including expanded camera STOP,
no JavaScript errors, and no extra POST on page reload.
