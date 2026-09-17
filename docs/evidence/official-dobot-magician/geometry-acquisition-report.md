# Eye-in-hand geometry acquisition: CAD/vendor-first audit

Audit date: 2026-09-14; vendor and as-built follow-up: 2026-09-15;
live Orbbec TF follow-up: 2026-09-16 (Asia/Bangkok)

Scope: establish `robot base -> tool/J4 -> suction_tcp -> camera_link` before
manual measurement or target calibration. No robot motion was commanded and
`geometry_verified` remains `false`.

## Sources checked

- DOBOT Download Center, Magician product id 316, CAD category id 17.
- DOBOT Magician User Guide V1.7.0 (2019-01-09).
- DOBOT Magician API Description V1.2.3 (2019-07-19).
- DobotStudio Windows V1.5.1 Magician, statically extracted.
- DobotStudio Windows V1.9.4 official installer, statically extracted without
  installation or execution.
- DobotStudio V1.5.1 bundled Panda3D visualization assets.
- Official DOBOT Demo V2.2 archive (payload labelled V2.1).
- Live official DobotLab 2.4.6 web/DobotBlock bundles from DOBOT CDN.
- Official Magician STEP and URDF shared by DOBOT staff (`Ryan_Yin`) on the
  DOBOT forum (archived topics 5010 and 4512).
- Forum tool-inclusive STEP/STL (`DOBOT_Magician-mit-TOOLS`) attributed to
  Variobotic/dobot.de; treated as third-party cross-check evidence only.
- Current repository URDF, startup code, meshes, mount config and TF notes.

The current official Magician CAD filter returns an unrelated script-example
record. An older official assembly STEP and URDF were recovered through links
posted by DOBOT staff on the archived vendor forum. The official STEP is a
dimensioned bare-robot assembly but does not contain the suction tool. A
tool-inclusive forum STEP was therefore inspected only as a non-authoritative
cross-check; it was not substituted for official evidence. DOBOT download-host
TLS certificates were expired on the audit date; affected downloads were
hashed locally.

## Findings

| Parameter | Candidate value | Frame meaning | Source | Confidence |
| --- | --- | --- | --- | --- |
| Controller Cartesian origin | Centre of rear-arm, forearm and base motors | Robot Cartesian base | User Guide 3.3.2 | official, verified |
| Controller/tool axes | `+X` away from base, `+Y` left, `+Z` up; `+R` CCW about vertical | Controller and ROS convention | User Guide; URDF J4 axis `0 0 1` | official + repository, verified |
| ROS `tool` origin | J4/tool-output yaw-axis centre | Current rotating tool frame | `magician.urdf.xacro`: J4 child/tool frame at `joint_origin_xyz="0.06 0 0"` | software verified; physical datum not labelled in official CAD |
| Standard suction preset | `xBias=59.7, yBias=0, zBias=0 mm` | Controller end-effector offset, not cup-tip-only offset | DobotStudio V1.5.1 and live DobotLab 2.4.6 | official vendor software, verified |
| Bare forearm/flange -> J4/tool-output axis | `+59.7 mm`; URDF uses rounded `+60 mm` | Horizontal controller X bias, not suction axial length | DobotStudio/DobotLab preset; current URDF yaw-joint origin | vendor preset verified; URDF differs by 0.3 mm |
| J4/tool origin -> suction physical tip | `z=-70.0 mm` | Vertical distance from J4 centre to cup-mouth centre plane; `below_tool_origin` maps to tool `-Z` | User-confirmed as-built manual measurement on installed hardware, 2026-09-15 | as-built measurement accepted; complete mount validation pending |
| Xacro `end_effector_length` | `60 mm` | Intended vertical tool length, currently unused in active branch | `magician.urdf.xacro` | repository hint only |
| Suction visual mesh bottom | `z=-57.291 mm`; top `z=-0.015 mm` | Extent relative to the mesh's intended J4-aligned origin, not a compliant contact-plane TCP | `suction_cup.dae` scene transform; reproducible audit script | repository cross-check only; not official provenance |
| `suction_tcp -> camera reference` | `[+50.0, 0.0, +35.0] mm` | From cup-mouth centre to measured camera centre in tool-frame axes | User-confirmed as-built manual measurements: 50.0 mm farther from base, 0.0 mm centred, 35.0 mm above suction TCP | as-built translation input; rotation and multi-pose validation pending |
| Installed Orbbec model family | original `Gemini` (`SV1301S_U3`, depth PID `0x0614`; RGB PID `0x0511`) | Physical camera whose centre is the measured mount endpoint | Official `orbbec/OrbbecSDK_v2` `DevicePids.hpp`; official legacy `orbbec/ros_astra_camera` labels the internal SDK name `Astra SV1301S_U3`; live serial `AY2A760003E` | vendor mapping verified; not Gemini 2 and not Astra 2 |
| Orbbec internal color TF | translation `[0.543805,-9.925951,0.090043] mm`; quaternion `[-0.500286649,0.497451541,-0.499821699,0.502427610]` xyzw | `camera_link -> camera_color_optical_frame` | Live Orbbec factory `/tf_static`, serial `AY2A760003E`, 2026-09-16 | factory, verified live; do not hand-measure |
| Orbbec internal depth TF | translation `[0,0,0] mm`; quaternion `[-0.5,0.5,-0.5,0.5]` xyzw | `camera_link -> camera_depth_optical_frame` | Live Orbbec factory `/tf_static`, serial `AY2A760003E`, 2026-09-16 | factory, verified live; do not hand-measure |
| Overall geometry | `geometry_verified: false` | Validation gate | `eye_in_hand_mount.yaml` | unverified |

## Official CAD and frame separation

The recovered official STEP (`0_DOBOT230_FOR_ASSEMBLY_ASM`, Creo Parametric,
2018-04-16) contains 248 solids but no suction-cup or gripper assembly. It can
support the bare-arm/J4 mechanical audit, but it cannot define the compliant
cup contact plane. The recovered official URDF likewise models the wrist links
and a final vertical yaw axis but supplies no suction TCP.

The tool-inclusive forum STEP explicitly contains `Saugnapf`, `BZ31017` and
`BZ31018`. It shows that the apparent physical motor shaft and the suction/tool
output spindle are horizontally offset, so they must not be conflated. Its
suction axis is approximately `(X,Y)=(-298.633,81.230) mm`; another repeated
distal cylindrical axis is around `(-269.934,81.230) mm`, a separation of about
`28.699 mm`. The suction assembly reaches a lowest geometric Z near
`66.684 mm`, but neither that face nor a J4/TCP datum is semantically labelled.
Consequently this CAD does not independently prove
`tool/J4 -> suction_tcp = (0,0,-70) mm`. That value is now sourced from the
as-built measurement recorded below; the external implementation is retained
only as corroborating evidence.

## Vendor preset interpretation

DobotStudio has two independent UI paths that label `59.7` as `SuctionCup`
and call `SetEndEffectorParams(59.7, 0, 0)`. Its same selector maps `70` to
`Laser`, so that number is not evidence for suction Z. Live DobotLab 2.4.6
repeats the Magician behaviour: selecting suction or gripper sends
`xOffset=59.7, yOffset=0, zOffset=0`; pen sends `61`. Thus vendor software
confirms the horizontal end-fixture bias but contains no physical cup-tip Z
preset.

The official Demo SDK defines `GetEndEffectorParams` and all three fields, but
contains no standard suction-tip geometry constant. During the initial audit it
could not be called safely because the active ROS stack held `/dev/ttyUSB0`.
When the port later became idle, the repository driver was found to have no GET
parser for protocol message ID 60; this caused a valid reply to appear as `[]`.
After adding the specified three-float parser, a read-only controller query
returned `(0.0, 0.0, 0.0)`, consistent with the repository startup configuration.

## Full DobotStudio payload and bundled-model audit

The complete extracted V1.5.1 payload confirms the preset mapping in two
independent shipped UI implementations: `SuctionCup=59.7`, `Gripper=59.701`
(normalized to `59.7`), `Laser=70`, and `Pen=61`; every generated call is
`SetEndEffectorParams(xBias, 0, 0)`. No shipped source/config assigns a nonzero
Z bias or a physical cup-tip offset to the SuctionCup preset.

The later official DobotStudio V1.9.4 payload repeats the same mapping in both
its Example UI and Blockly implementation: `SuctionCup=59.7`,
`Gripper=59.701` (normalized to `59.7`), `Laser=70`, and `Pen=61`, followed by
`SetEndEffectorParams(...,0,0)`. It contains no suction TCP or nonzero suction
Z constant. Its `Dobot_Magician_SuctionCup.bam` and `Dobot2-0.X` hashes are
byte-for-byte identical to the V1.5.1 payload, so the newer package supplies no
additional dimensional datum.

The current DOBOT download metadata endpoint was audited read-only for record
IDs 1 through 2000 (valid records extend to approximately 1083). No hidden or
delisted Magician suction CAD/dimension record was found; the current Magician
"3D Model / Dimension Drawing" entry ID 368 resolves to `script-example.zip`,
confirming that the visible category is misclassified rather than a suction
assembly CAD source.

`Dobot_Magician_SuctionCup.bam` is a skinned Panda3D visualization asset, not
dimensioned CAD. Its animation rig contains translations `0.65`, `0.75`, and
`0.806` in undocumented model units, while `End001` has scale `0.005`. Neither
this file nor `Dobot2-0.X` marks a `suction_tcp`, contact plane, physical units,
or an unambiguous J4-to-cup-mouth datum. It therefore cannot be the source of
the measured J4-to-cup-mouth transform.

The read-only `GetEndEffectorParams` result exposes the controller's current
`(xBias,yBias,zBias)`, not a separately stored physical cup-tip datum. With the
serial port idle, the SuctionCup preset was also verified without motion:
original `(0,0,0)`; set/read-back `(59.70000076,0,0)` (float32 representation);
restore/read-back `(0,0,0)`. No queued command or robot motion was issued.

## Repository CAD/mesh audit

No STEP/STP/IGES, FreeCAD, 3MF or mesh for the as-built Dobot-Orbbec bracket
exists in the repository. Orbbec body meshes cannot establish bracket pose.
The suction mesh was added by the upstream ROS project and has no official DOBOT
provenance; its extent is only a sanity hint, not a TCP definition.

Applying the DAE's own 4x4 scene matrix (including scale and translation) gives
`z_min=-57.291 mm` and `z_max=-0.015 mm`. The nearly zero upper bound shows that
the mesh was intentionally registered near the current J4/tool origin. This is
consistent with the unused `end_effector_length=60 mm` repository hint, but it
contradicts treating `-70 mm` as already established. The calculation is
reproducible with `scripts/audit_suction_mesh_geometry.py`; the script always
marks the result as unverified because a visual mesh extent is not a
vendor-labelled physical TCP datum.

### Additional public ROS model provenance check

The separately audited `ecuador-robotics/DOBOT_Magician_ROS` repository is a
third-party research/simulation project, not a DOBOT vendor package. Although
it includes several suction-related DAE files and a generated
`suction_cup.urdf`, it does not define a frame at the physical cup contact
plane. Its arm Xacro terminates the fixed end-effector frame at
`xyz="0.06 0 0"`, which is the same horizontal J4/tool-output offset already
present in this project and is not a vertical suction-tip offset.

Its `meshes/dae/suction_cup.dae` has SHA-256
`e3f29dd6af0c95fe930e412b94416a16d497425ed919bf791c6af10ad6a0070e`,
identical byte-for-byte to this repository's suction mesh. It is therefore not
independent evidence for the `-57.291 mm` mesh extent, and it supplies no
vendor-labelled evidence for `tool/J4 -> suction_tcp = (0,0,-70) mm`; it is
corroborating evidence only.

## Live Orbbec factory transform verification

After the depth interface was restored on USB 3.0, the running driver identified
the installed unit as SDK device `SV1301S_U3`, serial `AY2A760003E`, firmware
`RD3013`.  The driver published the complete static chain
`camera_link -> camera_depth_frame -> camera_color_frame -> optical frames`.
The composed transforms recorded in the findings table were read directly from
TF; they are not inferred from the installation photograph.  A live cloud probe
received 167,828 finite XYZ points in `camera_color_optical_frame`, confirming
that the registered point-cloud stream required by markerless calibration is
currently populated.

The current official Orbbec SDK source maps depth PID `0x0614` to the original
`Gemini` OpenNI family, and maps companion RGB PID `0x0511` to `gemini`.  The
legacy official ROS driver calls the same internal model `Astra SV1301S_U3`.
This establishes that the unit is not Gemini 2 or Astra 2, so meshes for those
newer products must not be used to invent a body envelope.  No authoritative
body CAD/dimension file for this original unit is present in either official
repository; the enclosing-radius safety input therefore remains unresolved.

## As-built suction TCP measurement

On 2026-09-15 the user confirmed a physical measurement on the installed
standard suction assembly: J4/tool rotation-axis centre to the centre of the
suction-cup mouth contact plane is `70.0 mm`, physically
`below_tool_origin`. Under the verified tool convention (`+Z` upward), the
converter maps this unsigned measurement to:

```text
tool -> suction_tcp = [0.0, 0.0, -70.0] mm
                    = [0.0, 0.0, -0.070] m
```

This as-built measurement is the primary provenance. The previously located
external `(0,0,-70) mm` implementation is retained only as corroborating
evidence and is not treated as the source. This resolves the suction TCP
translation input but does not verify the camera mount or the complete
eye-in-hand geometry; `geometry_verified` therefore remains `false`.

The same as-built measurement record defines the camera reference as the
physical centre of the camera and gives unsigned components from
`suction_tcp`: `50.0 mm` closer to the robot base, `0.0 mm` centred laterally,
and `35.0 mm` below. With tool `+X` away from base, `+Y` left and `+Z` upward,
the converter result is:

```text
suction_tcp -> camera reference = [+50.0, 0.0, +35.0] mm
tool        -> camera reference = [+50.0, 0.0, -35.0] mm
```

These values come only from the reported physical measurements; no
photo-derived dimension is used. Rotation must be recovered by the production
markerless RGB-D multi-pose workflow; fiducials and calibration boards are not
accepted. Until held-out validation passes, these values are not publishable
as verified runtime geometry.

## Evidence integrity

| File | SHA-256 |
| --- | --- |
| `Dobot-Magician-User-Guide-V1.7.0.pdf` | `02d6770aaa97dcd55dcd50d22308c9bf380be8b1ede405c80f15ee4a41a2bbdd` |
| `Dobot-Magician-API-Description-V1.2.3.pdf` | `06d51e3553893397caeaefce6a0f7cc167368d6629757dd1b5c85376e49f1da7` |
| `DobotStudio(Windows)V1.5.1-Magician.zip` | `ae596b56a0bc0bd2fe7b1156732abc2a70bf412cd27966d7fff1c85d3232f07e` |
| `DobotStudio(Windows)V1.9.4.zip` | `f7626ef489adace3459058ab087384c12e9c6209d36eb198323767b23e57bcf6` |
| V1.5.1/V1.9.4 `Dobot_Magician_SuctionCup.bam` | `3bf1d09fc0a775d5120bc23bafadf91272a0b8c2a192a5e727d3a8e061e28882` |
| V1.5.1/V1.9.4 `Dobot2-0.X` | `b22c2eed568be35821cebaf4c2d156abbebd1193c04e324427e91e009250ff1b` |
| Official `0_DOBOT230_FOR_ASSEMBLY_ASM` STEP | `105a9ecf62b408d68bf37298e6bdb744f8b628a10d3e393ea0c12f3455b1c171` |
| Official `magician-master` URDF ZIP | `d98e48bc3debf466e6357c2c07539f88cd98a84cd7cac4c57a525da4f0362339` |
| Forum tool-inclusive ZIP | `0cced4f8940afba1bd65b7481165e80215b1934a8c60dc77979bb706c17b4db5` |
| Forum tool-inclusive STEP | `d6e97694ba385260bfcef890a66f31dcc07abd7db7a638ac7c1ca4a05de4cc90` |
