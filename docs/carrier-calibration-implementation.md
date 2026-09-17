# Separate camera carrier and command TCP

The calibration code now supports a moving camera carrier distinct from the
reported TCP. It does not infer the carrier origin from the 50/0/35 mm mechanical
prior and does not substitute TCP when carrier TF is missing.

## Frame contract

- `tool_frame` remains the controller TCP. Captures retain `base_T_tool` for
  target agreement, motion commands and the centre of the swept safety envelope.
- Optional `carrier_frame` names the actual, independently verified camera
  bracket frame. It must differ from both base and TCP. A dynamic, validated
  robot-kinematic TF producer must supply its pose in the configured base frame.
  This solver still requires XYZ/yaw kinematics with carrier +Z aligned to base
  +Z; a tilted URDF frame needs a verified rigid axis-normalizing child frame.
- The adapter queries carrier TF at robot sample timestamps throughout the
  image's settling interval, with no latest-transform fallback. Missing,
  extrapolated, stale or moving carrier data prevents acceptance.
- Captures hold `base_T_carrier` separately. Registration prediction, excitation,
  optimization and held-out verification use `calibration_pose`, which selects
  the carrier in this mode. The scene/table transform also uses the carrier,
  while obstacle clearance is checked around the commanded TCP path.
- Carrier-mode plans vary TCP XY azimuth to excite the base joint while keeping
  commanded TCP orientation fixed. Existing local bounds and full trajectory
  validation remain in effect. Some starting poses cannot accommodate the plan;
  that is a rejection, not permission to enlarge the workspace.

## Mount and output contract

Use `carrier_mount.example.yaml` as an unverified template. A real mount file
must identify the same carrier frame and contain an independently verified
`carrier_T_camera_optical`, axial uncertainty and a TCP-centred enclosure bound
that covers every attached part throughout the planned configurations. The
axial translation is still unobservable under XYZ/yaw-only motion.

The public status reports the command frame, calibration parent and whether a
TCP-only consumer is supported. Published calibrated optical TF is parented to
carrier_frame. Internal Orbbec edges are untouched.

Carrier bundles use schema 2 and preserve both carrier training poses and
commanded TCP training poses, plus both anchor poses. The identity digest
includes carrier_frame. Schema 1 remains for the old TCP mode; existing saved
contexts may require recalibration because the adapter now includes that field.
The legacy matrix attribute/key `tool_T_camera` means parent-to-camera within
its schema/context, and must never be interpreted without them.

The current `VerifiedBundle` point consumer explicitly rejects schema 2 because
its API only receives a TCP pose. Automatic picking therefore remains blocked
until its callers supply synchronized carrier poses through an updated consumer.
A passed bracket calibration is not authorization to use the old point converter.

## Configuration and deployment status

The standalone calibration launch exposes `carrier_frame`. Its default is empty
for compatibility. No live launch configuration was changed, no stack restarted,
no measured mount marked verified, and no hardware motion was issued during this
software change. The existing physical attachment confirmation is retained.
Do not activate the example file merely to make the calibration start.

Before enabling a carrier run, establish the actual bracket's kinematic frame,
its measured optical extrinsic/axial prior and enclosure, and a real
hardware-backed safety input. The existing `safety_state_topic` requirement is
unchanged. User consent is not synthesized into a hardware safety message.

The new tests exercise carrier/TCP disagreement, tool-only false excitation,
base-azimuth planning, clearance frame separation, command pose checks,
mount identity, schema round-trip/consumer refusal, exact synthetic extrinsic
recovery, timestamped ROS TF lookup, unavailable TF and stale TF. Existing
registration, workflow, hardware and bundle tests are also run on a private
ROS domain, without access to the robot domain.
