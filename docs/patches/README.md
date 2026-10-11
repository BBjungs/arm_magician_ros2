# Orbbec camera launch patch

`orbbec-raw-image-transport.patch` preserves the local camera driver change
from `src/OrbbecSDK_ROS2` (base commit
`0ea4ab68f5b8ddf22998b7c45d251dc58ea2779e`). The driver is a separate Git
repository, so its uncommitted file changes are not included in a parent
repository commit.

The patch limits RGB, depth, and IR publishing to raw image transport to
avoid encoding unused compressed streams.

From the workspace root, apply it to a clean driver checkout with:

```bash
git -C src/OrbbecSDK_ROS2 apply --check ../../docs/patches/orbbec-raw-image-transport.patch
git -C src/OrbbecSDK_ROS2 apply ../../docs/patches/orbbec-raw-image-transport.patch
```

The patch is already applied in the current workspace.
