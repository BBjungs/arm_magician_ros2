# One-click object-based RGB-D calibration

Startup investigation update: the generated production `dobot_msgs` interface
was out of sync with the Python source. See
[startup repair, evidence and deployment runbook](startup-repair-deployment-2026-11-13.md).
The repaired 16-package isolated build and software regressions pass; production
deployment and hardware acceptance remain pending explicit operator authorization.

The operator dashboard now offers **select an object → start → inspect the
result**. When exactly one suitable object is present, no selection click is
needed. The existing Maintenance credentials and per-plan motion confirmations
still apply. Opening the page, selecting an object, loading a saved result and
Dry Run never authorize robot movement.

## Acquisition and mathematical model

The RGB-D shape detector publishes its observed silhouette and a JPEG tied to
the RGB/depth timestamps, frame names and image dimensions. Calibration uses
this independent observation even if table-relative `pick_eligible` is false.
Picking classification/height rules are unchanged. A detector without a
segmentation outline and exposure provenance is not accepted by this path.

Selection is bound to the displayed exposure. The acquisition loop waits for
the detector's result for that exposure, instead of consuming every frame
before detection can finish. Per-frame detection indices are not track IDs.
After selection, mutual RGB-D feature registration establishes identity; lost,
ambiguous, mismatched or stale observations stop acquisition.

Only silhouette-interior RGB/depth and 3D object points enter registration and
optimization. There are **no dominant-plane, table-normal, plane-angle or
scene-plane verification terms** in the object path. The shared
`scene_geometry()` helper only checks 3D extent, thickness and valid point count;
it does not fit a plane. The legacy scene-calibration path remains separate.

Every accepted pose uses at least three distinct stationary exposures, with
RGB-D motion checks, common valid pixels and median depth filtering. Stationary
object motion over 2 mm/0.5 degrees is rejected. Before each permitted movement,
a fresh exposure is compared with the last stationary object reference. Across
views, robot/camera motion invariants and anchor/adjacent registration reject
inconsistent object motion; the final hand-eye residuals and independent data
must also pass. There is no recovery motion to search for lost objects.

Flat/narrow/featureless geometry, insufficient points, invalid depth, weak
texture, known circular symmetry, similar principal axes and competing
half-turn alignments are rejected. These checks evaluate visible evidence;
they do not claim to identify hidden geometry or uniquely identify two
indistinguishable objects. Multiple plausible matches are rejected.

The installation file must explicitly verify the physical camera parent and
rotation with joint 4. This implementation supports the currently documented
**TCP-mounted** installation, using the existing measured camera-reference
translation and Orbbec reference-to-optical TF. A different bracket is rejected
until its kinematic model and safety envelope are commissioned; no TCP transform
is silently reused for it.

Dobot XYZ/yaw motion does not make an unconstrained six-parameter hand-eye
transform observable. The solver preserves the existing measured translation
constraint and estimates three rotation parameters, checks excitation and the
motion Jacobian rank/condition, and composes the optical transform through the
factory TF. This is object-based calibration with installation measurements,
not a hybrid plane/object estimator. It never guesses missing translation DOFs.

Seven views are used for fitting. Three different poses are reserved before
fitting for independent verification. Existing registration, residual and
observability limits remain in force; no threshold was reduced for this work.

## Safety and persistence

The object backend inherits the established authorization, expiring run/plan
token, MOVL validation, full-arm collision checks, surveyed workspace, PTP 5/5
readback, guarded dispatch, cancellation and restoration logic. The surveyed
table clearance in the **workspace collision model** remains a safety boundary;
it is not a camera-derived plane admission check.

Object acquisition occurs before planning/authorization. Real motion requires
the existing commissioning evidence and explicit confirmations for the displayed
plan. A changed plan clears the browser confirmations. Dry Run validates sensor
data and the plan without calling authorization, PTP setters or movement. It
does not produce a calibration PASS or overwrite the production calibration.

Object bundles carry `calibration_method: object_based`, masked RGB-D, full sensor
depth for revalidation, an empty plane array, camera/mount identity, training
poses, observability and independent verification evidence. Saves retain the
existing temporary-file/fsync/atomic-replace procedure. Reload checks method,
context, transform, mount agreement, metrics and recomputed object geometry.
Scene/object observations cannot be mixed silently.

At startup, an existing verified object bundle uses a **stationary** load/check
path. It reidentifies the saved reference and compares fresh RGB-D evidence
against the saved transform; it does not refit or request motion. The existing
startup/verify services also route object bundles through this path. Missing or
changed reference objects cause a clear failure, not an automatic new fit.
An explicitly requested recalibration has its own endpoint.

Old live readiness is not carried across a reboot. The final mathematical result
remains `AWAITING_LIVE_VALIDATION` until the original hardware, observability,
independent/reload verification, repeatability, real-object validation and
health checks pass. For an object report, `object_stability` replaces
`table_stability`; other live-acceptance requirements are unchanged. A numerical
PASS never opens picking, and this software work supplies no physical hardware
acceptance evidence.

## Interfaces

| Interface | Purpose |
|---|---|
| `/calibration/object/select` | `SelectCalibrationObject`: pixel, image dimensions and RGB stamp; empty JSON requests automatic selection |
| `/calibration/object/start` | Load/check a saved object bundle, or prepare new automatic acquisition |
| `/calibration/object/dry_run` | Sensor/plan audit without physical motion |
| `/calibration/object/recalibrate` | Explicitly request a new object-based fit |
| `/calibration/object/commission` | Existing two-pose commissioning protocol using object observations |
| `/calibration/autonomous/authorize` | Unchanged explicit safety acknowledgements bound to the validated plan |
| `/calibration/status` | Object candidates, exposure-bound preview, selection/tracking, workflow and admission status |
| `/api/calibration/object/{action}` | Authenticated web bridge to object services |

The default detector topic is `/dobot_vision/detections`; it can be configured
with `object_detections_topic`. Object selection does not alter picking targets.
Normal users see Thai explanations for insufficient texture/3D data, symmetry,
reference movement, stale frames, unknown mounting and incomplete live validation.

## Software verification and installation state

Final regression results: **422 calibration tests passed** (336.070 s),
**179 web/RGB-D tests passed** (7.485 s), **0 failures, 0 skips**.
The real Chromium workflow check passed with **0 page errors**. The final
reference-retention change is additionally checked by the targeted Dry Run test.
JUnit evidence is in `/tmp/object-calibration-tests.xml` and
`/tmp/object-web-rgbd-tests.xml`; the browser screenshot is
`/tmp/object-calibration-browser.png`.

Tests use a ray-cast asymmetric stepped object with known camera/robot transforms,
independent held-out poses and injected robot transport. Coverage includes real
RGB-D registration/optimization, symmetry, moving objects, sensor provenance,
median filtering, unobservable/mixed data, corrupt bundles, wrong camera parents,
collision rejection, explicit authorization, full ten-pose acquisition, PTP
restoration, saved-result reuse and picking remaining disabled.

The Chromium check loads the repository's real HTML/JS/CSS and intercepts every
request with a mock API. It checks click coordinates/timestamps, start/Dry Run,
manual authorization, confirmation reset on plan changes and Thai error text.
The existing web authentication, operator, visual-servo and RGB-D regressions are
also exercised; unrelated pre-existing workspace changes are preserved.

Builds were performed in `/tmp/object-calibration-build` and
`/tmp/object-calibration-install`, including generated `dobot_msgs` interfaces.
Production services were **not restarted**, and no real robot motion was sent.
The running Python services continue using their already imported code until a
controlled deployment/restart. Deploy the updated `dobot_msgs`,
`dobot_calibration`, `dobot_vision_rgbd` and `dobot_web_interface` together; older
detector processes do not supply the required silhouette/exposure preview.

Reproduce the software tests after sourcing ROS Jazzy, the existing workspace
dependencies, and the isolated overlay:

```bash
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ROS_DOMAIN_ID=187 \
  ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_LOG_DIR=/tmp/object-calibration-regression-logs \
  .venv/bin/python -m pytest src/magician_ros2/dobot_calibration/test \
  -q --tb=short --junitxml=/tmp/object-calibration-tests.xml

OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 ROS_DOMAIN_ID=190 \
  ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST ROS_LOG_DIR=/tmp/object-web-regression-logs \
  .venv/bin/python -m pytest src/magician_ros2/dobot_web_interface/test \
  src/magician_ros2/dobot_vision_rgbd/test -q --tb=short \
  --junitxml=/tmp/object-web-rgbd-tests.xml

PLAYWRIGHT_BROWSERS_PATH=/tmp/object-ui-browsers /tmp/object-ui-env/bin/python \
  src/magician_ros2/dobot_web_interface/test/object_calibration_browser_check.py
```

The JavaScript regression tests need Node on `PATH`; this run uses the Node binary
bundled with the isolated Playwright installation, without changing system Node.
