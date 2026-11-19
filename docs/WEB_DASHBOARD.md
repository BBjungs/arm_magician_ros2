# Web Dashboard

The responsive dashboard uses HTML, CSS and JavaScript with a Python standard-library HTTP backend. It displays the RGB stream, registered depth status, bounding boxes, object and image centers, pixel errors, TCP, joints, alarms, run state and diagnostic text.

The server binds to `127.0.0.1`. From a desktop with SSH access, use `ssh -N -L 8080:127.0.0.1:8080 <operator>@<jetson>` and open the forwarded URL on that desktop. A mobile SSH client can forward the same loopback port for a browser on the phone. Keep the forwarding endpoint private. Use a separate ROS domain with local discovery for the simulator and keep the ROS domain trusted.

## Operator authorization

Set `DOBOT_OPERATOR_TOKEN` in the launch environment to enable operator access. The browser keeps the token in JavaScript memory. Only authenticated operators can claim an exclusive short lease. The browser renews the lease while active. Expiration stops the current owner’s run. STOP requires an authenticated operator and can interrupt another lease, including while a confirmation is displayed.

| HTTP route | Purpose |
| --- | --- |
| GET `/api/status` | Current dashboard state and detection metadata |
| GET `/api/frame/{frame_id}.jpg` | JPEG corresponding to a recent status sample |
| POST `/api/control`, `/api/heartbeat`, `/api/release` | Acquire, renew or release control |
| POST `/api/confirm` | Obtain a short-lived confirmation for HOME, observation or Auto Center |
| POST `/api/command` | Submit an exact operation with a unique `Idempotency-Key` |
| POST `/api/stop` | Cancel the workflow and initiate controller stop verification |

POST calls require a Bearer token. Lease-scoped calls include `X-Control-Lease`. Confirmations are single-use and bound to the operation and relevant workflow state, including target identity. Reusing an idempotency key with the same payload returns the recorded result within the lease. A conflicting payload is rejected. A disconnected browser loses authorization when its lease expires.

The physical emergency stop is independent of the dashboard. Software STOP reports the verified workflow outcome through the run state.

## Browser acceptance

Check the layout at 1280 px and at 360–430 px. In each layout run the complete workflow using a detectable synthetic target. Use the target list and a pointer ROI on desktop and a touch ROI on mobile. During a run, try STOP, close the controlling tab, and attempt a second control claim from a separate browser. Confirm that the terminal state and hold status match the outcome.
