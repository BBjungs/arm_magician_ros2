# Mount motion probe — 2026-09-11

User authorized physical robot motion. Five sequential manual Cartesian linear
moves used velocity/acceleration ratios 0.05. Fresh TCP, homing, alarm and camera
checks ran before and during each move; the existing PTP server validated each
trajectory. All actions returned SUCCEEDED (4), with no reported alarms.
No homing, suction actuation, automatic picking or calibration was invoked.

| Move | Image rotation | Evidence |
|---|---:|---|
| Z +5 mm | -0.017 degrees | image scale 0.9773; 20 inliers |
| X +5 mm | +0.048 degrees | image shifted roughly down 11.7 px; 17 inliers |
| Y +5 mm | +1.748 degrees | base joint +1.85 degrees; 11 inliers |
| Tool yaw +3 degrees | +0.0095 degrees | joint 4 +3 degrees; 28 inliers |
| Tool yaw -3 degrees | +0.00063 degrees | joint 4 returned; see analysis JSON |

SIFT correspondences and RANSAC partial-affine fits compared before/after RGB
snapshots. These are image-space motion observations, not calibrated 3-D
extrinsics. The scene was assumed static; the small pose range does not establish
all possible bracket flex or link dependencies.

The forward/reverse yaw tests strongly contradict a camera rigidly attached to
the rotating TCP frame. Y translation changed base yaw by 1.85 degrees while
controller TCP yaw stayed zero; camera image rotation tracked that base yaw.
Thus the current constant reported-TCP-to-camera calibration model is unsuitable
for this mounting arrangement. Do not enable it by marking geometry verified.

The description model puts magician_joint_4 between magician_link_4 and
magician_link_suction_cup. magician_link_4 is a candidate camera parent, requiring
physical bracket confirmation and validation of its kinematics and measured
extrinsic. The camera and suction frame should branch from their actual rigid
parents. A suction_tcp-to-camera_link lookup remains possible through TF, but
would depend on joint state rather than be a constant static transform.

Next: establish the actual bracket parent and its kinematics, determine the
reported-TCP-to-cup-mouth correction, identify the measured optical endpoint,
and calibrate against the correct camera-parent motion. Internal Orbbec TF stays
unchanged. Mechanical prior remains 50/0/35 mm, with unresolved uncertainty.

Final reported pose: approximately [155.040, 5.000, 104.981] mm, yaw 0 degrees.
The arm remains 5 mm higher and +5 mm in X/Y relative to its start, rather than
making an extra descent. It is stationary; no action remains active in the last
successful result. Telemetry precision is not independently measured accuracy.

Raw before/after images, status, analysis and the probe script are preserved in
[evidence/mount-probe-2026-09-11](evidence/mount-probe-2026-09-11/).
