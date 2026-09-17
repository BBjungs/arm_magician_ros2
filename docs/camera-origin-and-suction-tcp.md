# Camera origins and suction TCP — 2026-09-11

User confirmed: the 50/0/35 mm outward/lateral/upward measurement starts at the
suction cup mouth center used for picking and ends at the approximate camera
lens assembly optical center. This is a mechanical prior, not final ROS XYZ.
The endpoint is not yet identified as the depth or color optical center.

## Orbbec driver evidence

Source: src/OrbbecSDK_ROS2/orbbec_camera/src/ob_camera_node.cpp.
Lines 773–781 select depth as base stream when available. publishStaticTF
(line 2981) maps SDK translation in mm to ROS metres as [z, -x, -y]/1000.
calcAndPublishStaticTransform uses SDK getExtrinsicTo(base_stream_profile)
for the other sensor origins and rotations. Each stream-to-optical edge has
zero translation and quaternion XYZW [-0.5, 0.5, -0.5, 0.5]. Link-to-base-stream
has zero translation; special Femto models can alter its rotation.

The live capture in tcp-camera-tf-audit-2026-09-11.json shows:

| Parent | Child | Translation in parent axes (mm) |
|---|---|---|
| camera_link | camera_depth_frame | 0, 0, 0 |
| camera_depth_frame | camera_depth_optical_frame | 0, 0, 0 |
| camera_depth_frame | camera_color_frame | 0.543805, -9.925951, 0.090043 |
| camera_color_frame | camera_color_optical_frame | 0, 0, 0 |

The link-to-depth edge is identity in this capture. Link and depth optical
therefore share an origin but not axes. Color optical origin is about 9.94 mm
away and its relative sensor rotation is nonzero (see raw quaternion evidence).
These are calibrated sensor-coordinate origins, not a housing midpoint.
Internal TF cannot locate an approximate hand-measured lens point or a housing
mark; that requires model-specific mechanical data or additional measurement.
Do not repeat the SDK axis/unit conversion on an already published ROS TF.

## Dobot evidence and desired chain

The state publisher uses controller get_pose() directly with XYZ converted to
metres and R as yaw; it adds no suction-mouth correction. Bringup includes
set_tool_null for suction_cup, whose source sets end-effector bias to (0,0,0).
This is source evidence, not current controller readback or physical verification.
Do not assume that the reported TCP is either a flange origin or the cup mouth.

```text
magician_base_link -> TCP/tool (J4 rotation-axis centre)
                       -> suction_tcp (cup mouth; 70.0 mm below tool)
                            -> camera_link (mount unresolved)
                                 -> camera_depth_frame
                                      -> camera_depth_optical_frame
                                      -> camera_color_frame
                                           -> camera_color_optical_frame
```

No identity correction is justified yet. Keep Orbbec as the sole publisher of
its internal edges; do not create competing optical-frame parents.

## Composition

Column-vector notation T_A_B maps coordinates in B into A. D = reported TCP,
S = suction_tcp, L = camera_link, O = selected optical frame:

```text
T_S_L = T_S_O * inverse(T_L_O)
T_D_O = T_D_S * T_S_L * T_L_O
T_base_O = T_base_D * T_D_O
```

Use actual internal TF including rotation. In particular,
t_S_L = t_S_O - R_S_L * t_L_O: a camera-axis offset cannot be subtracted
directly from a physical outward/upward measurement. If measured endpoint P is
only an approximate lens point, establish its correction to O first; internal
TF does not supply that missing correspondence.

The calibration consumer currently expects reported-tool-to-optical geometry,
so its eventual matrix must include T_D_S via T_D_O above, unless its tool frame
is deliberately migrated throughout. No runtime matrix has been filled.

## Still required

- Identification and uncertainty of the approximate optical endpoint.
- Camera rotation relative to suction_tcp and rigidity with tool yaw.
- Mount envelope and table clearance before calibration motion.

Only measurement metadata and documentation were updated. No transform was
published, no runtime parameters changed, and no robot motion was requested.


## Superseding Eye-in-Hand confirmation — 2026-09-14

Physical installation inspection supersedes the earlier image-based bracket
interpretation. The Orbbec is rigid on the rotating end-effector and follows
J4. The constant chain is:

```text
magician_base_link -> TCP/tool -> camera_link -> Orbbec optical frames
                              -> suction_tcp
```

The reported `TCP`/tool origin is the joint-4 rotation-axis centre. The user
confirmed the as-built distance to the centre of the suction-cup mouth plane
as `70.0 mm` in the physical `below_tool_origin` direction on 2026-09-15.
Because tool `+Z` is upward, this gives
`tool -> suction_tcp = [0, 0, -0.070] m`. The matching external `-70 mm` hint
is corroborating evidence only, not the primary source.
The camera's factory internal transforms remain owned by the Orbbec driver.

The remaining tool-to-camera translation is entered as unsigned physical
measurements in `config/eye-in-hand-mount-measurement-form.yaml` and converted
using the verified TCP frame convention. Tool-to-camera rotation is not taken
from a photograph or an assumed cardinal angle. The production markerless
RGB-D workflow estimates it using natural-feature registration, 3D RANSAC,
ICP and table-plane constraints while keeping measured translation fixed.

At least six training and two held-out poses must vary XYZ and J4 yaw. The
solver checks robot-axis rank, constrained Jacobian rank/condition, RGB-D
registration/ICP quality and held-out scene consistency in the robot base.
Until those checks pass, `geometry_verified` remains false and no mount TF is
published. The capture workflow never commands robot motion.
