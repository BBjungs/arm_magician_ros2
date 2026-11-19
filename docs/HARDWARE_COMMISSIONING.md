# Hardware commissioning

The following work requires separate authorization from the equipment operator. The current runtime supports mock motion and passive ROS telemetry. A commissioning record should include the workcell, operator, installed Dobot model and firmware, camera model and serial, mount revision, date, measurements and results.

## Passive checks

1. Secure the camera, cables and suction cup assembly. Check fasteners, strain relief and clearance across the full envelope. Record payload and tool dimensions.
2. Confirm the Orbbec color and registered depth profiles at the intended resolution. At several known distances and image locations, compare RGB edges with depth edges and measured depth. Check intrinsics, timestamp skew, units and stale data behavior.
3. Use the separately authorized read-only Dobot driver to record model, firmware, serial readback, joints, TCP and alarms. Compare units, joint conventions and frames with known physical references.
4. Run `ros2 run dobot_auto_center auto_center_readiness --seconds 5` against the existing ROS graph. Record the topic provenance and match the reported firmware against the vendor protocol documentation. This tool subscribes only, opens no serial or camera device and creates no motion client.

## Controlled commissioning

1. Verify the independent physical emergency stop, equipment recovery behavior and accessible operator stop stations before powered-motion trials.
2. Survey the workcell. Model joint limits, the table, self-collision, cable sweep, camera and tool envelopes, fixtures and obstacles. Validate full swept paths with clearance for readback error, deflection and worst-case braking.
3. In a separately authorized vendor-controlled trial, measure HOME behavior and swept travel. Establish a distinct observation pose with a clear view and verified transition path. Confirm XY reachability at fixed Z/R on the installed arm.
4. For the exact firmware and command mode, verify acceptance/readback semantics, queue bounds, timeouts, cancellation and force-stop behavior. Measure cessation and stopping distance using independent observation and fresh TCP/joint readback. Check alarms, reconnect, motor power loss, stale messages, queue reset, late replies and controller restart without automatic movement.
5. After those checks, implement and review an exclusive serial transport and integrate verified concurrency, full-path validation, physical E-stop state and measured stop verification. Only then authorize an instrumented Jacobian identification trial with the fixed mount.

The readiness report covers only ROS samples received during its observation window. It cannot certify the physical workcell or enable real motion.
