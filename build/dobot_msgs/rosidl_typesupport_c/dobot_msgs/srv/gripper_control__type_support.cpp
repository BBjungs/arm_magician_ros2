// generated from rosidl_typesupport_c/resource/idl__type_support.cpp.em
// with input from dobot_msgs:srv/GripperControl.idl
// generated code does not contain a copyright notice

#include "cstddef"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "dobot_msgs/srv/detail/gripper_control__struct.h"
#include "dobot_msgs/srv/detail/gripper_control__type_support.h"
#include "dobot_msgs/srv/detail/gripper_control__functions.h"
#include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/message_type_support_dispatch.h"
#include "rosidl_typesupport_c/type_support_map.h"
#include "rosidl_typesupport_c/visibility_control.h"
#include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_c
{

typedef struct _GripperControl_Request_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _GripperControl_Request_type_support_ids_t;

static const _GripperControl_Request_type_support_ids_t _GripperControl_Request_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _GripperControl_Request_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _GripperControl_Request_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _GripperControl_Request_type_support_symbol_names_t _GripperControl_Request_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, dobot_msgs, srv, GripperControl_Request)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, srv, GripperControl_Request)),
  }
};

typedef struct _GripperControl_Request_type_support_data_t
{
  void * data[2];
} _GripperControl_Request_type_support_data_t;

static _GripperControl_Request_type_support_data_t _GripperControl_Request_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _GripperControl_Request_message_typesupport_map = {
  2,
  "dobot_msgs",
  &_GripperControl_Request_message_typesupport_ids.typesupport_identifier[0],
  &_GripperControl_Request_message_typesupport_symbol_names.symbol_name[0],
  &_GripperControl_Request_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t GripperControl_Request_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_GripperControl_Request_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &dobot_msgs__srv__GripperControl_Request__get_type_hash,
  &dobot_msgs__srv__GripperControl_Request__get_type_description,
  &dobot_msgs__srv__GripperControl_Request__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace dobot_msgs

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, dobot_msgs, srv, GripperControl_Request)() {
  return &::dobot_msgs::srv::rosidl_typesupport_c::GripperControl_Request_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__struct.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__type_support.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_c
{

typedef struct _GripperControl_Response_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _GripperControl_Response_type_support_ids_t;

static const _GripperControl_Response_type_support_ids_t _GripperControl_Response_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _GripperControl_Response_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _GripperControl_Response_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _GripperControl_Response_type_support_symbol_names_t _GripperControl_Response_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, dobot_msgs, srv, GripperControl_Response)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, srv, GripperControl_Response)),
  }
};

typedef struct _GripperControl_Response_type_support_data_t
{
  void * data[2];
} _GripperControl_Response_type_support_data_t;

static _GripperControl_Response_type_support_data_t _GripperControl_Response_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _GripperControl_Response_message_typesupport_map = {
  2,
  "dobot_msgs",
  &_GripperControl_Response_message_typesupport_ids.typesupport_identifier[0],
  &_GripperControl_Response_message_typesupport_symbol_names.symbol_name[0],
  &_GripperControl_Response_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t GripperControl_Response_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_GripperControl_Response_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &dobot_msgs__srv__GripperControl_Response__get_type_hash,
  &dobot_msgs__srv__GripperControl_Response__get_type_description,
  &dobot_msgs__srv__GripperControl_Response__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace dobot_msgs

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, dobot_msgs, srv, GripperControl_Response)() {
  return &::dobot_msgs::srv::rosidl_typesupport_c::GripperControl_Response_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__struct.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__type_support.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__functions.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
// already included above
// #include "rosidl_typesupport_c/message_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_c/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_c
{

typedef struct _GripperControl_Event_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _GripperControl_Event_type_support_ids_t;

static const _GripperControl_Event_type_support_ids_t _GripperControl_Event_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _GripperControl_Event_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _GripperControl_Event_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _GripperControl_Event_type_support_symbol_names_t _GripperControl_Event_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, dobot_msgs, srv, GripperControl_Event)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, srv, GripperControl_Event)),
  }
};

typedef struct _GripperControl_Event_type_support_data_t
{
  void * data[2];
} _GripperControl_Event_type_support_data_t;

static _GripperControl_Event_type_support_data_t _GripperControl_Event_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _GripperControl_Event_message_typesupport_map = {
  2,
  "dobot_msgs",
  &_GripperControl_Event_message_typesupport_ids.typesupport_identifier[0],
  &_GripperControl_Event_message_typesupport_symbol_names.symbol_name[0],
  &_GripperControl_Event_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t GripperControl_Event_message_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_GripperControl_Event_message_typesupport_map),
  rosidl_typesupport_c__get_message_typesupport_handle_function,
  &dobot_msgs__srv__GripperControl_Event__get_type_hash,
  &dobot_msgs__srv__GripperControl_Event__get_type_description,
  &dobot_msgs__srv__GripperControl_Event__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace dobot_msgs

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_c, dobot_msgs, srv, GripperControl_Event)() {
  return &::dobot_msgs::srv::rosidl_typesupport_c::GripperControl_Event_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif

// already included above
// #include "cstddef"
#include "rosidl_runtime_c/service_type_support_struct.h"
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__type_support.h"
// already included above
// #include "rosidl_typesupport_c/identifier.h"
#include "rosidl_typesupport_c/service_type_support_dispatch.h"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"
#include "service_msgs/msg/service_event_info.h"
#include "builtin_interfaces/msg/time.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_c
{
typedef struct _GripperControl_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _GripperControl_type_support_ids_t;

static const _GripperControl_type_support_ids_t _GripperControl_service_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_c",  // ::rosidl_typesupport_fastrtps_c::typesupport_identifier,
    "rosidl_typesupport_introspection_c",  // ::rosidl_typesupport_introspection_c::typesupport_identifier,
  }
};

typedef struct _GripperControl_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _GripperControl_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _GripperControl_type_support_symbol_names_t _GripperControl_service_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, dobot_msgs, srv, GripperControl)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, srv, GripperControl)),
  }
};

typedef struct _GripperControl_type_support_data_t
{
  void * data[2];
} _GripperControl_type_support_data_t;

static _GripperControl_type_support_data_t _GripperControl_service_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _GripperControl_service_typesupport_map = {
  2,
  "dobot_msgs",
  &_GripperControl_service_typesupport_ids.typesupport_identifier[0],
  &_GripperControl_service_typesupport_symbol_names.symbol_name[0],
  &_GripperControl_service_typesupport_data.data[0],
};

static const rosidl_service_type_support_t GripperControl_service_type_support_handle = {
  rosidl_typesupport_c__typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_GripperControl_service_typesupport_map),
  rosidl_typesupport_c__get_service_typesupport_handle_function,
  &GripperControl_Request_message_type_support_handle,
  &GripperControl_Response_message_type_support_handle,
  &GripperControl_Event_message_type_support_handle,
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_CREATE_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    dobot_msgs,
    srv,
    GripperControl
  ),
  ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_DESTROY_EVENT_MESSAGE_SYMBOL_NAME(
    rosidl_typesupport_c,
    dobot_msgs,
    srv,
    GripperControl
  ),
  &dobot_msgs__srv__GripperControl__get_type_hash,
  &dobot_msgs__srv__GripperControl__get_type_description,
  &dobot_msgs__srv__GripperControl__get_type_description_sources,
};

}  // namespace rosidl_typesupport_c

}  // namespace srv

}  // namespace dobot_msgs

#ifdef __cplusplus
extern "C"
{
#endif

const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_c, dobot_msgs, srv, GripperControl)() {
  return &::dobot_msgs::srv::rosidl_typesupport_c::GripperControl_service_type_support_handle;
}

#ifdef __cplusplus
}
#endif
