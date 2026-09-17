// generated from rosidl_generator_c/resource/idl__struct.h.em
// with input from dobot_msgs:srv/GetPTPCommonParams.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/get_ptp_common_params.h"


#ifndef DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__STRUCT_H_
#define DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__STRUCT_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>


// Constants defined in the message

/// Struct defined in srv/GetPTPCommonParams in the package dobot_msgs.
typedef struct dobot_msgs__srv__GetPTPCommonParams_Request
{
  uint8_t structure_needs_at_least_one_member;
} dobot_msgs__srv__GetPTPCommonParams_Request;

// Struct for a sequence of dobot_msgs__srv__GetPTPCommonParams_Request.
typedef struct dobot_msgs__srv__GetPTPCommonParams_Request__Sequence
{
  dobot_msgs__srv__GetPTPCommonParams_Request * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__GetPTPCommonParams_Request__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'error'
#include "rosidl_runtime_c/string.h"

/// Struct defined in srv/GetPTPCommonParams in the package dobot_msgs.
typedef struct dobot_msgs__srv__GetPTPCommonParams_Response
{
  bool success;
  uint8_t velocity_percent;
  uint8_t acceleration_percent;
  uint8_t raw_velocity_percent;
  uint8_t raw_acceleration_percent;
  bool timed_out;
  rosidl_runtime_c__String error;
} dobot_msgs__srv__GetPTPCommonParams_Response;

// Struct for a sequence of dobot_msgs__srv__GetPTPCommonParams_Response.
typedef struct dobot_msgs__srv__GetPTPCommonParams_Response__Sequence
{
  dobot_msgs__srv__GetPTPCommonParams_Response * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__GetPTPCommonParams_Response__Sequence;

// Constants defined in the message

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.h"

// constants for array fields with an upper bound
// request
enum
{
  dobot_msgs__srv__GetPTPCommonParams_Event__request__MAX_SIZE = 1
};
// response
enum
{
  dobot_msgs__srv__GetPTPCommonParams_Event__response__MAX_SIZE = 1
};

/// Struct defined in srv/GetPTPCommonParams in the package dobot_msgs.
typedef struct dobot_msgs__srv__GetPTPCommonParams_Event
{
  service_msgs__msg__ServiceEventInfo info;
  dobot_msgs__srv__GetPTPCommonParams_Request__Sequence request;
  dobot_msgs__srv__GetPTPCommonParams_Response__Sequence response;
} dobot_msgs__srv__GetPTPCommonParams_Event;

// Struct for a sequence of dobot_msgs__srv__GetPTPCommonParams_Event.
typedef struct dobot_msgs__srv__GetPTPCommonParams_Event__Sequence
{
  dobot_msgs__srv__GetPTPCommonParams_Event * data;
  /// The number of valid items in data
  size_t size;
  /// The number of allocated items in data
  size_t capacity;
} dobot_msgs__srv__GetPTPCommonParams_Event__Sequence;

#ifdef __cplusplus
}
#endif

#endif  // DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__STRUCT_H_
