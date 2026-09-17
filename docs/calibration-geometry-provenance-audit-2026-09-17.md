# Geometry provenance and safety-reference audit — 2026-09-17

## Corrected as-built translation

The measurement converter implements the verified TCP convention correctly:
`+X` is farther from the robot base and `+Z` is upward.  The prior error was
in the filled measurement form, not in the converter: it recorded the two
physical direction words as `closer_to_robot_base` and `below`.

| Segment | Corrected as-built direction | TCP-frame translation |
| --- | --- | --- |
| tool/J4 origin → suction TCP | 70.0 mm below tool origin | `[0, 0, -70] mm` |
| suction TCP → camera reference | 50.0 mm farther from base, centred, 35.0 mm above suction TCP | `[+50, 0, +35] mm` |
| tool/J4 origin → camera reference | derived sum | `[+50, 0, -35] mm` |

The correction is in `config/eye-in-hand-mount-measurement-form.yaml`,
`config/camera-mount-measurements.yaml`, and the calibration mount model.
It does not provide, imply, or alter a tool-to-camera rotation.  Therefore
`geometry_verified` remains false.

The mount-model fingerprint changed from
`c23bc32825c1aca5e821f0c8e2bc6ae7d855b9bef140562032c326759664b245` to
`0d3c21088fa2bba7a89ecc8784f705c29a5be55ba9b20855395985e5169d434b`.
The existing session is deliberately incompatible.  Its manifest and
`pose_001.npz` have not been modified.  Migration is not safe because its
plane/camera observations were recorded under the old geometric constraint:
retain it as evidence, create a new session after table-reference approval,
and recapture Pose 1.  Do not copy or transform its accepted status.

## Table reference

The repository does **not** establish that controller Cartesian `Z=0` or
`magician_base_link` is the tabletop.  In the standalone URDF,
`magician_base_link` is 131.305 mm above the synthetic
`magician_root_link` (`magician_joint_base`), but neither that root nor the
controller Cartesian datum is tied to the installed table surface.  The
driver's Cartesian pose convention likewise contains no table-plane datum.

The only measurement needed is:

> Measure the signed vertical coordinate, in millimetres, from the origin of
> `magician_base_link` to the actual tabletop at the calibration area; report
> it as `table_surface_z_in_magician_base_link_mm` (positive in `+Z`).

The stored Pose 1 plane (depth about 204–230 mm and optical normal
`[-0.0079, -0.1382, -0.9904]`) is retained only as a plausibility observation.
Without verified tool→camera rotation it cannot determine the table height
and is not a motion-safety truth.  Automatic preflight now rejects an absent
finite table reference with `TABLE_REFERENCE_UNVERIFIED`; it no longer
defaults to 0 m.

## Trajectory-validator audit

The active validator is
`dobot_kinematics.trajectory_validator_server.PoseValidatorService`, using
`dobot_kinematics.dobot_inv_kin.calc_inv_kin`.  For Cartesian MOVL it samples
the straight Cartesian line at the configured 2 mm step and uses its single
analytic IK branch.  Runtime limits are axis 1 `(-120,120)`, axis 2
`(-5,90)`, axis 3 `(-15,90)`, and axis 4 `(-140,140)` degrees.  Axis 3's
effective lower bound is additionally raised by `max(0, axis2-40)`.

The URDF is not equivalent to those runtime controller-coordinate limits:
it declares different joint names/axes and, for example, axis-1 `[-125,125]`,
axis-2 `[-5,90]`, axis-3 `[-15,70]`, plus separate wrist/yaw joints.  No
limit has been expanded.  The validator now returns structured diagnostic
data on a Cartesian limit failure: failing joint/value/effective limits,
path sample and Cartesian point, analytic IK branch, and IK-estimated start
and target joint vectors.  Measured joint telemetry remains the authority
when it is available.
