# Auto Calibration bootstrap — 2026-10-31

Live `GET /api/operator/status` and `GET /api/vision/calibration` reported
`FAULT`, zero accepted poses and `motion_command_sent: false`. The recorded
startup blockers were `DEPTH_UNSTABLE`, `WORKSPACE_NOT_CONFIGURED` and
`SCENE_BASELINE_MISSING`. A subsequent live sample had hardware READY but
RGB-D ingestion still IDLE, no synchronized payload, and no passive session.

`AutomaticBackend.prepare()` previously required the scene baseline and
stable depth before activating the lazy capture subscriptions. That prevented
a first run from preparing its own observations and treated camera warm-up
as a terminal calibration failure.

The revised sequence validates the measured workspace, camera identity and
controller parameter state, then enables stationary capture inputs. It waits
within the existing capture timeout for healthy RGB-D/robot feedback. If no
baseline exists, it creates an empty session and requires the existing ten-second
continuous baseline admission window before capturing and persisting the scene.
Capture still validates the real exposure, point cloud and dominant plane;
readiness is rechecked after capture. Baseline creation does not count as a
calibration pose. Existing baselines, including rejected/incompatible files,
are preserved for their normal validation path. STOP interrupts warm-up and
prevents baseline persistence after cancellation.

The rest of the sequence retains full trajectory checks, two-pose commissioning,
per-run authorization, independent verification and live acceptance. The web UI
now identifies camera warm-up and initial baseline capture explicitly.

## Installation still required

`/home/jetson/.ros/dobot/calibration_workspace.yaml` is missing. The existing
`docs/commissioning-workspace-measurement-form.yaml` explicitly marks its
free-volume limits as unmeasured and its previous TCP ranges as simulation
inputs. Those values cannot certify the real workcell. The workspace gate
therefore remains closed until measured installation data is supplied.

This change is not evidence of a completed physical calibration or production
readiness. No calibration pose or workspace measurement is fabricated.

## Verification

The complete Calibration and Web test directories finished with exit code 0:
378 passed and two JavaScript integration tests skipped because Node.js is not
installed. Tests ran using the project virtual environment, ROS domain 231,
localhost discovery and temporary ROS logs; robot transport was mocked.
Both changed JavaScript files also passed syntax compilation, and
`git diff --check` passed.

Added regressions cover first-session warm-up and the ten-second admission
window, preservation of existing baselines, timeout, cancellation during
warm-up/capture, readiness loss, persistence failure, incompatible sessions,
activation before baseline admission, and cancelled sensor initialization.

After the tests, the user service was restarted with no active operator job or
motion command and with startup HOME/observation motion disabled. The live API
then reported robot, camera and depth ready. The new automatic run
`88834e6431d84e22af2e6757c9e14c3d` stopped at the measured-workspace gate:
`WORKSPACE_NOT_CONFIGURED: /home/jetson/.ros/dobot/calibration_workspace.yaml`.
It accepted zero poses, sent no motion command and did not report production
readiness. Initial baseline acquisition remains downstream of this missing
installation requirement and has only been exercised with test doubles here.
