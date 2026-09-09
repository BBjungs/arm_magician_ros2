// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from dobot_msgs:srv/GripperControl.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/gripper_control.h"


#ifndef DOBOT_MSGS__SRV__DETAIL__GRIPPER_CONTROL__STRUCT_H_
#define DOBOT_MSGS__SRV__DETAIL__GRIPPER_CONTROL__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

// Include directives for member types
// Member 'gripper_state'
#include "rosidl_runtime_c/string.h"

/// Struct defined in srv/GripperControl in the package dobot_msgs.
typedef struct dobot_msgs__srv__GripperControl_Request
{
  rosidl_runtime_c__String gripper_state;
  bool keep_compressor_running;
} dobot_msgs__srv__GripperControl_Request;

// Struct for a sequence of dobot_msgs__srv__GripperControl_Request.
typedef struct dobot_msgs__srv__GripperControl_Request__Sequence
{
  dobot_msgs__srv__GripperControl_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__GripperControl_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'message'
// already included above
// #include "rosidl_runtime_c/string.h"

/// Struct defined in srv/GripperControl in the package dobot_msgs.
typedef struct dobot_msgs__srv__GripperControl_Response
{
  bool success;
  rosidl_runtime_c__String message;
} dobot_msgs__srv__GripperControl_Response;

// Struct for a sequence of dobot_msgs__srv__GripperControl_Response.
typedef struct dobot_msgs__srv__GripperControl_Response__Sequence
{
  dobot_msgs__srv__GripperControl_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__GripperControl_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  dobot_msgs__srv__GripperControl_Event__request__MAX_SIZE = 1
};
// response
enum
{
  dobot_msgs__srv__GripperControl_Event__response__MAX_SIZE = 1
};

/// Struct defined in srv/GripperControl in the package dobot_msgs.
typedef struct dobot_msgs__srv__GripperControl_Event
{
  service_msgs__msg__ServiceEventInfo info;
  dobot_msgs__srv__GripperControl_Request__Sequence request;
  dobot_msgs__srv__GripperControl_Response__Sequence response;
} dobot_msgs__srv__GripperControl_Event;

// Struct for a sequence of dobot_msgs__srv__GripperControl_Event.
typedef struct dobot_msgs__srv__GripperControl_Event__Sequence
{
  dobot_msgs__srv__GripperControl_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__GripperControl_Event__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // DOBOT_MSGS__SRV__DETAIL__GRIPPER_CONTROL__STRUCT_H_
