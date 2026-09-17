# Depth health commissioning — 2026-09-12

The deployed depth-health path passed a 30-second observation after the service
restart. All 60 sampled calibration status messages reported depth_fresh=true
and depth_stable=true. Observed depth reception ranged from 22.72 to 25.53 Hz:
above the existing >20 Hz acceptance gate, below the requested 30 Hz. This is
bounded runtime evidence, not long-term reliability or calibration acceptance.

## Changes

- The camera health monitor now subscribes directly to RGB and depth with
  keep-last-one best-effort QoS. Detector progress no longer controls camera
  liveness evidence.
- Camera health publishes at 10 Hz, within the existing calibration depth TTL
  of 0.5 seconds. Direct metrics include the maximum sensor timestamp gap.
- A single-thread executor replaces the monitor's four-thread executor.
  Live trials with four threads received depth too slowly; the final
  single-thread trial passed the unchanged rate and gap gates.
- Forwarded image age includes time spent waiting at the health relay.
  Calibration retains that image age instead of refreshing it to heartbeat
  arrival time. Invalid/missing ages fail closed.
- The RGB-D detector publishes health independently of completed detections,
  without reissuing cached detections. Live depth validity updates even when
  synchronized detection does not complete.
- Existing adapter test doubles were completed with current bundle fields.

LDP was already OFF in the camera startup log. No LDP or calibration geometry
value was changed. The service was restarted to load the source changes.
STARTUP_AUTO_MOTION remains false; no calibration motion, HOME, suction command
or picking command was issued.

## Validation

72 targeted tests passed on private ROS domain 173 with localhost discovery:
camera health, detector health, object fusion, calibration ROS adapter and
hardware readiness. Tests cover missing/stale/invalid image age, invalid depth,
a stopped direct stream despite a healthy detector report, and health publishing
without republishing targets. git diff --check passed for the touched packages.

Runtime evidence:
- [Final summary](evidence/depth-health-2026-09-12/summary.json)
- [60 final status samples](evidence/depth-health-2026-09-12/calibration-status-after.json)
- [TF and publisher inspection](evidence/depth-health-2026-09-12/ros-graph-after.json)

Intermediate observations are retained in the same evidence directory.
Timer changes alone did not resolve the issue; only the final deployed
configuration is represented by the final summary. The graph inspection was
taken before the last monitor changes and is topology evidence only.

## Remaining commissioning dependencies

The final 60 samples all reported SAFETY_UNVERIFIED: the driver supplies no
hardware E-stop/safety-state input. The equipment and connection must be
identified before configuring safety_state_topic; no synthetic permission
signal was published.

Calibration itself still reports an unverified mount, no bundle and zero
samples. Live TF inspection found only base-to-TCP and the camera's internal
tree, with no verified camera-carrier connection. Establish the bracket's
actual kinematic parent, optical extrinsic/axial prior, suction reference and
enclosure from physical evidence before activating carrier calibration.
The camera is mounted before tool yaw; a constant rotating-TCP camera mount
remains unsuitable.

Carrier-aware picking consumption and independent physical validation remain
required after a verified carrier calibration. This change does not authorize
picking or establish geometric accuracy.
