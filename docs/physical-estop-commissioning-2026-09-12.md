# Physical E-stop commissioning policy — 2026-09-12

The workcell has an external physical E-stop. The operator confirmed that it is installed, released before motion, reachable during operation and directly stops the Dobot. Its circuit was not modified, disabled or bridged.

The calibration service now reports:

- Physical E-stop: PRESENT
- Hardware safety: OPERATOR VERIFIED
- Software E-stop monitoring: NOT CONNECTED

No ROS 2 E-stop topic or synthetic GPIO publisher is used. The absent software feedback no longer blocks calibration motion under this operator-verification policy. If a real ROS safety topic is configured in the future, a false or stale software safety state still blocks motion.

Motion is still blocked for invalid or stale depth, missing TCP/joint/alarm telemetry, an active Dobot alarm, failed trajectory validation, workspace or table-clearance violations, invalid/stale camera-carrier TF, and any calibration or verification failure. Calibration motion uses velocity and acceleration ratios of 0.05. The operator must remain at the workcell and stop motion immediately if it is abnormal.

## Current geometry evidence

The live read-only audit found two disconnected TF trees:

- magician_base_link -> TCP
- camera_link -> camera_depth_frame -> camera_color_frame -> camera_color_optical_frame

At the audit pose, TCP was [150.080, 0, 100.086] mm in magician_base_link with effectively zero yaw. The internal Orbbec transform from depth to color was present, but there is still no base-to-bracket or bracket-to-camera transform.

The prior yaw probe showed that the camera is installed before the tool rotation axis and does not rigidly rotate with TCP joint 4. Therefore a constant TCP -> camera transform must not be marked verified. The current calibration status correctly blocks only on missing camera-mount geometry.

Before a low-speed calibration run, establish the actual kinematic carrier frame (expected candidate: magician_link_4), measure the carrier-to-selected optical origin and rotation, independently measure the unobservable axial component and uncertainty, establish the controller TCP-to-cup-mouth reference, and measure the full camera/bracket envelope. Configure a carrier mount only when those measurements are available. The solver will then require dynamic carrier TF at each image exposure and will reject a missing, stale or extrapolated transform.

Evidence: [read-only TF/TCP audit](evidence/camera-mount-readonly-audit-2026-09-12.json).
