// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "dobot_msgs/msg/detail/circle_target__rosidl_typesupport_introspection_c.h"
#include "dobot_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "dobot_msgs/msg/detail/circle_target__functions.h"
#include "dobot_msgs/msg/detail/circle_target__struct.h"


// Include directives for member types
// Member `class_name`
// Member `rejection_reason`
#include "rosidl_runtime_c/string_functions.h"
// Member `camera_xyz`
#include "geometry_msgs/msg/point.h"
// Member `camera_xyz`
#include "geometry_msgs/msg/detail/point__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  dobot_msgs__msg__CircleTarget__init(message_memory);
}

void dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_fini_function(void * message_memory)
{
  dobot_msgs__msg__CircleTarget__fini(message_memory);
}

size_t dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__size_function__CircleTarget__center_uv(
  const void * untyped_member)
{
  (void)untyped_member;
  return 2;
}

const void * dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__get_const_function__CircleTarget__center_uv(
  const void * untyped_member, size_t index)
{
  const double * member =
    (const double *)(untyped_member);
  return &member[index];
}

void * dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__get_function__CircleTarget__center_uv(
  void * untyped_member, size_t index)
{
  double * member =
    (double *)(untyped_member);
  return &member[index];
}

void dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__fetch_function__CircleTarget__center_uv(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const double * item =
    ((const double *)
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__get_const_function__CircleTarget__center_uv(untyped_member, index));
  double * value =
    (double *)(untyped_value);
  *value = *item;
}

void dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__assign_function__CircleTarget__center_uv(
  void * untyped_member, size_t index, const void * untyped_value)
{
  double * item =
    ((double *)
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__get_function__CircleTarget__center_uv(untyped_member, index));
  const double * value =
    (const double *)(untyped_value);
  *item = *value;
}

static rosidl_typesupport_introspection_c__MessageMember dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_member_array[12] = {
  {
    "id",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_UINT32,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, id),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "class_name",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, class_name),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "center_uv",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    2,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, center_uv),  // bytes offset in struct
    NULL,  // default value
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__size_function__CircleTarget__center_uv,  // size() function pointer
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__get_const_function__CircleTarget__center_uv,  // get_const(index) function pointer
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__get_function__CircleTarget__center_uv,  // get(index) function pointer
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__fetch_function__CircleTarget__center_uv,  // fetch(index, &value) function pointer
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__assign_function__CircleTarget__center_uv,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "camera_xyz",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, camera_xyz),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "depth",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, depth),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "size",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, size),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "confidence",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, confidence),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "pickable",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, pickable),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "top_height",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, top_height),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "depth_valid_ratio",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, depth_valid_ratio),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "depth_mad",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, depth_mad),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "rejection_reason",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTarget, rejection_reason),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_members = {
  "dobot_msgs__msg",  // message namespace
  "CircleTarget",  // message name
  12,  // number of fields
  sizeof(dobot_msgs__msg__CircleTarget),
  false,  // has_any_key_member_
  dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_member_array,  // message members
  dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_init_function,  // function to initialize message memory (memory has to be allocated)
  dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_type_support_handle = {
  0,
  &dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_members,
  get_message_typesupport_handle_function,
  &dobot_msgs__msg__CircleTarget__get_type_hash,
  &dobot_msgs__msg__CircleTarget__get_type_description,
  &dobot_msgs__msg__CircleTarget__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_dobot_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, msg, CircleTarget)() {
  dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_member_array[3].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, geometry_msgs, msg, Point)();
  if (!dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_type_support_handle.typesupport_identifier) {
    dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &dobot_msgs__msg__CircleTarget__rosidl_typesupport_introspection_c__CircleTarget_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
