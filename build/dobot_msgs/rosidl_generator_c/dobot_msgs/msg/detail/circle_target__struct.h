// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target.h"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__STRUCT_H_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Constants defined in the message

// Include directives for member types
// Member 'class_name'
// Member 'rejection_reason'
#include "rosidl_runtime_c/string.h"
// Member 'camera_xyz'
#include "geometry_msgs/msg/detail/point__struct.h"

/// Struct defined in msg/CircleTarget in the package dobot_msgs.
/**
  * ID is local to this exposure; identify a target by (array header stamp, id).
 */
typedef struct dobot_msgs__msg__CircleTarget
{
  uint32_t id;
  /// black, white or yellow
  rosidl_runtime_c__String class_name;
  double center_uv[2];
  /// Metres, in the array header's registered optical frame.
  geometry_msgs__msg__Point camera_xyz;
  /// Optical Z in metres (not Euclidean range).
  double depth;
  /// Diameter in metres, measured in the object top plane.
  double size;
  double confidence;
  /// Visual suction suitability only; robot calibration/readiness is a separate gate.
  bool pickable;
  double top_height;
  double depth_valid_ratio;
  double depth_mad;
  rosidl_runtime_c__String rejection_reason;
} dobot_msgs__msg__CircleTarget;

// Struct for a sequence of dobot_msgs__msg__CircleTarget.
typedef struct dobot_msgs__msg__CircleTarget__Sequence
{
  dobot_msgs__msg__CircleTarget * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__msg__CircleTarget__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__STRUCT_H_
