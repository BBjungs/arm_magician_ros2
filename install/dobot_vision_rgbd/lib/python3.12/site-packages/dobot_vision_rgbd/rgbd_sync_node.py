def stamp_ns(message):
    return message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec


def sync_delta_ms(*messages):
    stamps = [stamp_ns(message) for message in messages]
    return (max(stamps) - min(stamps)) / 1_000_000.0


def registered_geometry_ok(color_message, depth_message, camera_info):
    return (
        color_message.width == depth_message.width == camera_info.width
        and color_message.height == depth_message.height == camera_info.height
        and color_message.header.frame_id == depth_message.header.frame_id
    )
