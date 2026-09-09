// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from dobot_msgs:srv/ExecuteHomingProcedure.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/execute_homing_procedure.h"


#ifndef DOBOT_MSGS__SRV__DETAIL__EXECUTE_HOMING_PROCEDURE__STRUCT_H_
#define DOBOT_MSGS__SRV__DETAIL__EXECUTE_HOMING_PROCEDURE__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

/// Struct defined in srv/ExecuteHomingProcedure in the package dobot_msgs.
typedef struct dobot_msgs__srv__ExecuteHomingProcedure_Request
{
  uint8_t structure_needs_at_least_one_member;
} dobot_msgs__srv__ExecuteHomingProcedure_Request;

// Struct for a sequence of dobot_msgs__srv__ExecuteHomingProcedure_Request.
typedef struct dobot_msgs__srv__ExecuteHomingProcedure_Request__Sequence
{
  dobot_msgs__srv__ExecuteHomingProcedure_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__ExecuteHomingProcedure_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'instruction'
#include "rosidl_runtime_c/string.h"

/// Struct defined in srv/ExecuteHomingProcedure in the package dobot_msgs.
typedef struct dobot_msgs__srv__ExecuteHomingProcedure_Response
{
  bool success;
  /// description of homing procedure
  rosidl_runtime_c__String instruction;
} dobot_msgs__srv__ExecuteHomingProcedure_Response;

// Struct for a sequence of dobot_msgs__srv__ExecuteHomingProcedure_Response.
typedef struct dobot_msgs__srv__ExecuteHomingProcedure_Response__Sequence
{
  dobot_msgs__srv__ExecuteHomingProcedure_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__ExecuteHomingProcedure_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  dobot_msgs__srv__ExecuteHomingProcedure_Event__request__MAX_SIZE = 1
};
// response
enum
{
  dobot_msgs__srv__ExecuteHomingProcedure_Event__response__MAX_SIZE = 1
};

/// Struct defined in srv/ExecuteHomingProcedure in the package dobot_msgs.
typedef struct dobot_msgs__srv__ExecuteHomingProcedure_Event
{
  service_msgs__msg__ServiceEventInfo info;
  dobot_msgs__srv__ExecuteHomingProcedure_Request__Sequence request;
  dobot_msgs__srv__ExecuteHomingProcedure_Response__Sequence response;
} dobot_msgs__srv__ExecuteHomingProcedure_Event;

// Struct for a sequence of dobot_msgs__srv__ExecuteHomingProcedure_Event.
typedef struct dobot_msgs__srv__ExecuteHomingProcedure_Event__Sequence
{
  dobot_msgs__srv__ExecuteHomingProcedure_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__ExecuteHomingProcedure_Event__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // DOBOT_MSGS__SRV__DETAIL__EXECUTE_HOMING_PROCEDURE__STRUCT_H_
