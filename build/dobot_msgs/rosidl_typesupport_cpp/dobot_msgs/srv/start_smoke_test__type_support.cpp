// generated from rosidl_typesupport_cpp/resource/idl__type_support.cpp.em
// with input from dobot_msgs:srv/StartSmokeTest.idl
// generated code does not contain a copyright notice

#include "cstddef"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "dobot_msgs/srv/detail/start_smoke_test__functions.h"
#include "dobot_msgs/srv/detail/start_smoke_test__struct.hpp"
#include "rosidl_typesupport_cpp/identifier.hpp"
#include "rosidl_typesupport_cpp/message_type_support.hpp"
#include "rosidl_typesupport_c/type_support_map.h"
#include "rosidl_typesupport_cpp/message_type_support_dispatch.hpp"
#include "rosidl_typesupport_cpp/visibility_control.h"
#include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_cpp
{

typedef struct _StartSmokeTest_Request_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartSmokeTest_Request_type_support_ids_t;

static const _StartSmokeTest_Request_type_support_ids_t _StartSmokeTest_Request_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_cpp",  // ::rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
    "rosidl_typesupport_introspection_cpp",  // ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  }
};

typedef struct _StartSmokeTest_Request_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartSmokeTest_Request_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartSmokeTest_Request_type_support_symbol_names_t _StartSmokeTest_Request_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_cpp, dobot_msgs, srv, StartSmokeTest_Request)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, dobot_msgs, srv, StartSmokeTest_Request)),
  }
};

typedef struct _StartSmokeTest_Request_type_support_data_t
{
  void * data[2];
} _StartSmokeTest_Request_type_support_data_t;

static _StartSmokeTest_Request_type_support_data_t _StartSmokeTest_Request_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartSmokeTest_Request_message_typesupport_map = {
  2,
  "dobot_msgs",
  &_StartSmokeTest_Request_message_typesupport_ids.typesupport_identifier[0],
  &_StartSmokeTest_Request_message_typesupport_symbol_names.symbol_name[0],
  &_StartSmokeTest_Request_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t StartSmokeTest_Request_message_type_support_handle = {
  ::rosidl_typesupport_cpp::typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartSmokeTest_Request_message_typesupport_map),
  ::rosidl_typesupport_cpp::get_message_typesupport_handle_function,
  &dobot_msgs__srv__StartSmokeTest_Request__get_type_hash,
  &dobot_msgs__srv__StartSmokeTest_Request__get_type_description,
  &dobot_msgs__srv__StartSmokeTest_Request__get_type_description_sources,
};

}  // namespace rosidl_typesupport_cpp

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_typesupport_cpp
{

template<>
ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Request>()
{
  return &::dobot_msgs::srv::rosidl_typesupport_cpp::StartSmokeTest_Request_message_type_support_handle;
}

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_cpp, dobot_msgs, srv, StartSmokeTest_Request)() {
  return get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Request>();
}

#ifdef __cplusplus
}
#endif
}  // namespace rosidl_typesupport_cpp

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "dobot_msgs/srv/detail/start_smoke_test__functions.h"
// already included above
// #include "dobot_msgs/srv/detail/start_smoke_test__struct.hpp"
// already included above
// #include "rosidl_typesupport_cpp/identifier.hpp"
// already included above
// #include "rosidl_typesupport_cpp/message_type_support.hpp"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_cpp/message_type_support_dispatch.hpp"
// already included above
// #include "rosidl_typesupport_cpp/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_cpp
{

typedef struct _StartSmokeTest_Response_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartSmokeTest_Response_type_support_ids_t;

static const _StartSmokeTest_Response_type_support_ids_t _StartSmokeTest_Response_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_cpp",  // ::rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
    "rosidl_typesupport_introspection_cpp",  // ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  }
};

typedef struct _StartSmokeTest_Response_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartSmokeTest_Response_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartSmokeTest_Response_type_support_symbol_names_t _StartSmokeTest_Response_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_cpp, dobot_msgs, srv, StartSmokeTest_Response)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, dobot_msgs, srv, StartSmokeTest_Response)),
  }
};

typedef struct _StartSmokeTest_Response_type_support_data_t
{
  void * data[2];
} _StartSmokeTest_Response_type_support_data_t;

static _StartSmokeTest_Response_type_support_data_t _StartSmokeTest_Response_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartSmokeTest_Response_message_typesupport_map = {
  2,
  "dobot_msgs",
  &_StartSmokeTest_Response_message_typesupport_ids.typesupport_identifier[0],
  &_StartSmokeTest_Response_message_typesupport_symbol_names.symbol_name[0],
  &_StartSmokeTest_Response_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t StartSmokeTest_Response_message_type_support_handle = {
  ::rosidl_typesupport_cpp::typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartSmokeTest_Response_message_typesupport_map),
  ::rosidl_typesupport_cpp::get_message_typesupport_handle_function,
  &dobot_msgs__srv__StartSmokeTest_Response__get_type_hash,
  &dobot_msgs__srv__StartSmokeTest_Response__get_type_description,
  &dobot_msgs__srv__StartSmokeTest_Response__get_type_description_sources,
};

}  // namespace rosidl_typesupport_cpp

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_typesupport_cpp
{

template<>
ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Response>()
{
  return &::dobot_msgs::srv::rosidl_typesupport_cpp::StartSmokeTest_Response_message_type_support_handle;
}

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_cpp, dobot_msgs, srv, StartSmokeTest_Response)() {
  return get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Response>();
}

#ifdef __cplusplus
}
#endif
}  // namespace rosidl_typesupport_cpp

// already included above
// #include "cstddef"
// already included above
// #include "rosidl_runtime_c/message_type_support_struct.h"
// already included above
// #include "dobot_msgs/srv/detail/start_smoke_test__functions.h"
// already included above
// #include "dobot_msgs/srv/detail/start_smoke_test__struct.hpp"
// already included above
// #include "rosidl_typesupport_cpp/identifier.hpp"
// already included above
// #include "rosidl_typesupport_cpp/message_type_support.hpp"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
// already included above
// #include "rosidl_typesupport_cpp/message_type_support_dispatch.hpp"
// already included above
// #include "rosidl_typesupport_cpp/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_cpp
{

typedef struct _StartSmokeTest_Event_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartSmokeTest_Event_type_support_ids_t;

static const _StartSmokeTest_Event_type_support_ids_t _StartSmokeTest_Event_message_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_cpp",  // ::rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
    "rosidl_typesupport_introspection_cpp",  // ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  }
};

typedef struct _StartSmokeTest_Event_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartSmokeTest_Event_type_support_symbol_names_t;

#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartSmokeTest_Event_type_support_symbol_names_t _StartSmokeTest_Event_message_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_cpp, dobot_msgs, srv, StartSmokeTest_Event)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, dobot_msgs, srv, StartSmokeTest_Event)),
  }
};

typedef struct _StartSmokeTest_Event_type_support_data_t
{
  void * data[2];
} _StartSmokeTest_Event_type_support_data_t;

static _StartSmokeTest_Event_type_support_data_t _StartSmokeTest_Event_message_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartSmokeTest_Event_message_typesupport_map = {
  2,
  "dobot_msgs",
  &_StartSmokeTest_Event_message_typesupport_ids.typesupport_identifier[0],
  &_StartSmokeTest_Event_message_typesupport_symbol_names.symbol_name[0],
  &_StartSmokeTest_Event_message_typesupport_data.data[0],
};

static const rosidl_message_type_support_t StartSmokeTest_Event_message_type_support_handle = {
  ::rosidl_typesupport_cpp::typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartSmokeTest_Event_message_typesupport_map),
  ::rosidl_typesupport_cpp::get_message_typesupport_handle_function,
  &dobot_msgs__srv__StartSmokeTest_Event__get_type_hash,
  &dobot_msgs__srv__StartSmokeTest_Event__get_type_description,
  &dobot_msgs__srv__StartSmokeTest_Event__get_type_description_sources,
};

}  // namespace rosidl_typesupport_cpp

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_typesupport_cpp
{

template<>
ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Event>()
{
  return &::dobot_msgs::srv::rosidl_typesupport_cpp::StartSmokeTest_Event_message_type_support_handle;
}

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_cpp, dobot_msgs, srv, StartSmokeTest_Event)() {
  return get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Event>();
}

#ifdef __cplusplus
}
#endif
}  // namespace rosidl_typesupport_cpp

// already included above
// #include "cstddef"
#include "rosidl_runtime_c/service_type_support_struct.h"
#include "rosidl_typesupport_cpp/service_type_support.hpp"
// already included above
// #include "dobot_msgs/srv/detail/start_smoke_test__struct.hpp"
// already included above
// #include "rosidl_typesupport_cpp/identifier.hpp"
// already included above
// #include "rosidl_typesupport_c/type_support_map.h"
#include "rosidl_typesupport_cpp/service_type_support_dispatch.hpp"
// already included above
// #include "rosidl_typesupport_cpp/visibility_control.h"
// already included above
// #include "rosidl_typesupport_interface/macros.h"

namespace dobot_msgs
{

namespace srv
{

namespace rosidl_typesupport_cpp
{

typedef struct _StartSmokeTest_type_support_ids_t
{
  const char * typesupport_identifier[2];
} _StartSmokeTest_type_support_ids_t;

static const _StartSmokeTest_type_support_ids_t _StartSmokeTest_service_typesupport_ids = {
  {
    "rosidl_typesupport_fastrtps_cpp",  // ::rosidl_typesupport_fastrtps_cpp::typesupport_identifier,
    "rosidl_typesupport_introspection_cpp",  // ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  }
};

typedef struct _StartSmokeTest_type_support_symbol_names_t
{
  const char * symbol_name[2];
} _StartSmokeTest_type_support_symbol_names_t;
#define STRINGIFY_(s) #s
#define STRINGIFY(s) STRINGIFY_(s)

static const _StartSmokeTest_type_support_symbol_names_t _StartSmokeTest_service_typesupport_symbol_names = {
  {
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_fastrtps_cpp, dobot_msgs, srv, StartSmokeTest)),
    STRINGIFY(ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, dobot_msgs, srv, StartSmokeTest)),
  }
};

typedef struct _StartSmokeTest_type_support_data_t
{
  void * data[2];
} _StartSmokeTest_type_support_data_t;

static _StartSmokeTest_type_support_data_t _StartSmokeTest_service_typesupport_data = {
  {
    0,  // will store the shared library later
    0,  // will store the shared library later
  }
};

static const type_support_map_t _StartSmokeTest_service_typesupport_map = {
  2,
  "dobot_msgs",
  &_StartSmokeTest_service_typesupport_ids.typesupport_identifier[0],
  &_StartSmokeTest_service_typesupport_symbol_names.symbol_name[0],
  &_StartSmokeTest_service_typesupport_data.data[0],
};

static const rosidl_service_type_support_t StartSmokeTest_service_type_support_handle = {
  ::rosidl_typesupport_cpp::typesupport_identifier,
  reinterpret_cast<const type_support_map_t *>(&_StartSmokeTest_service_typesupport_map),
  ::rosidl_typesupport_cpp::get_service_typesupport_handle_function,
  ::rosidl_typesupport_cpp::get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Request>(),
  ::rosidl_typesupport_cpp::get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Response>(),
  ::rosidl_typesupport_cpp::get_message_type_support_handle<dobot_msgs::srv::StartSmokeTest_Event>(),
  &::rosidl_typesupport_cpp::service_create_event_message<dobot_msgs::srv::StartSmokeTest>,
  &::rosidl_typesupport_cpp::service_destroy_event_message<dobot_msgs::srv::StartSmokeTest>,
  &dobot_msgs__srv__StartSmokeTest__get_type_hash,
  &dobot_msgs__srv__StartSmokeTest__get_type_description,
  &dobot_msgs__srv__StartSmokeTest__get_type_description_sources,
};

}  // namespace rosidl_typesupport_cpp

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_typesupport_cpp
{

template<>
ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_service_type_support_t *
get_service_type_support_handle<dobot_msgs::srv::StartSmokeTest>()
{
  return &::dobot_msgs::srv::rosidl_typesupport_cpp::StartSmokeTest_service_type_support_handle;
}

}  // namespace rosidl_typesupport_cpp

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_CPP_PUBLIC
const rosidl_service_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__SERVICE_SYMBOL_NAME(rosidl_typesupport_cpp, dobot_msgs, srv, StartSmokeTest)() {
  return ::rosidl_typesupport_cpp::get_service_type_support_handle<dobot_msgs::srv::StartSmokeTest>();
}

#ifdef __cplusplus
}
#endif
