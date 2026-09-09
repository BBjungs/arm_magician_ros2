// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target_array.h"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__STRUCT_H_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

// Constants defined in the message

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.h"
// Member 'reason'
#include "rosidl_runtime_c/string.h"
// Member 'detections'
#include "dobot_msgs/msg/detail/circle_target__struct.h"

/// Struct defined in msg/CircleTargetArray in the package dobot_msgs.
/**
  * RGB exposure stamp and registered optical frame; never the processing time.
 */
typedef struct dobot_msgs__msg__CircleTargetArray
{
  std_msgs__msg__Header header;
  bool valid;
  rosidl_runtime_c__String reason;
  /// Unit normal faces the camera; n dot camera_xyz + d = 0, metres.
  double table_plane[4];
  double table_inlier_ratio;
  double table_rmse;
  dobot_msgs__msg__CircleTarget__Sequence detections;
} dobot_msgs__msg__CircleTargetArray;

// Struct for a sequence of dobot_msgs__msg__CircleTargetArray.
typedef struct dobot_msgs__msg__CircleTargetArray__Sequence
{
  dobot_msgs__msg__CircleTargetArray * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__msg__CircleTargetArray__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__STRUCT_H_
