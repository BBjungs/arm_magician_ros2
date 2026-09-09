// generated from rosidl_typesupport_introspection_c/resource/idl__type_support.c.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

#include <stddef.h>
#include "dobot_msgs/msg/detail/circle_target_array__rosidl_typesupport_introspection_c.h"
#include "dobot_msgs/msg/rosidl_typesupport_introspection_c__visibility_control.h"
#include "rosidl_typesupport_introspection_c/field_types.h"
#include "rosidl_typesupport_introspection_c/identifier.h"
#include "rosidl_typesupport_introspection_c/message_introspection.h"
#include "dobot_msgs/msg/detail/circle_target_array__functions.h"
#include "dobot_msgs/msg/detail/circle_target_array__struct.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/header.h"
// Member `header`
#include "std_msgs/msg/detail/header__rosidl_typesupport_introspection_c.h"
// Member `reason`
#include "rosidl_runtime_c/string_functions.h"
// Member `detections`
#include "dobot_msgs/msg/circle_target.h"
// Member `detections`
#include "dobot_msgs/msg/detail/circle_target__rosidl_typesupport_introspection_c.h"

#ifdef __cplusplus
extern "C"
{
#endif

void dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_init_function(
  void * message_memory, enum rosidl_runtime_c__message_initialization _init)
{
  // TODO(karsten1987): initializers are not yet implemented for typesupport c
  // see https://github.com/ros2/ros2/issues/397
  (void) _init;
  dobot_msgs__msg__CircleTargetArray__init(message_memory);
}

void dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_fini_function(void * message_memory)
{
  dobot_msgs__msg__CircleTargetArray__fini(message_memory);
}

size_t dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__size_function__CircleTargetArray__table_plane(
  const void * untyped_member)
{
  (void)untyped_member;
  return 4;
}

const void * dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_const_function__CircleTargetArray__table_plane(
  const void * untyped_member, size_t index)
{
  const double * member =
    (const double *)(untyped_member);
  return &member[index];
}

void * dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_function__CircleTargetArray__table_plane(
  void * untyped_member, size_t index)
{
  double * member =
    (double *)(untyped_member);
  return &member[index];
}

void dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__fetch_function__CircleTargetArray__table_plane(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const double * item =
    ((const double *)
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_const_function__CircleTargetArray__table_plane(untyped_member, index));
  double * value =
    (double *)(untyped_value);
  *value = *item;
}

void dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__assign_function__CircleTargetArray__table_plane(
  void * untyped_member, size_t index, const void * untyped_value)
{
  double * item =
    ((double *)
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_function__CircleTargetArray__table_plane(untyped_member, index));
  const double * value =
    (const double *)(untyped_value);
  *item = *value;
}

size_t dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__size_function__CircleTargetArray__detections(
  const void * untyped_member)
{
  const dobot_msgs__msg__CircleTarget__Sequence * member =
    (const dobot_msgs__msg__CircleTarget__Sequence *)(untyped_member);
  return member->size;
}

const void * dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_const_function__CircleTargetArray__detections(
  const void * untyped_member, size_t index)
{
  const dobot_msgs__msg__CircleTarget__Sequence * member =
    (const dobot_msgs__msg__CircleTarget__Sequence *)(untyped_member);
  return &member->data[index];
}

void * dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_function__CircleTargetArray__detections(
  void * untyped_member, size_t index)
{
  dobot_msgs__msg__CircleTarget__Sequence * member =
    (dobot_msgs__msg__CircleTarget__Sequence *)(untyped_member);
  return &member->data[index];
}

void dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__fetch_function__CircleTargetArray__detections(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const dobot_msgs__msg__CircleTarget * item =
    ((const dobot_msgs__msg__CircleTarget *)
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_const_function__CircleTargetArray__detections(untyped_member, index));
  dobot_msgs__msg__CircleTarget * value =
    (dobot_msgs__msg__CircleTarget *)(untyped_value);
  *value = *item;
}

void dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__assign_function__CircleTargetArray__detections(
  void * untyped_member, size_t index, const void * untyped_value)
{
  dobot_msgs__msg__CircleTarget * item =
    ((dobot_msgs__msg__CircleTarget *)
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_function__CircleTargetArray__detections(untyped_member, index));
  const dobot_msgs__msg__CircleTarget * value =
    (const dobot_msgs__msg__CircleTarget *)(untyped_value);
  *item = *value;
}

bool dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__resize_function__CircleTargetArray__detections(
  void * untyped_member, size_t size)
{
  dobot_msgs__msg__CircleTarget__Sequence * member =
    (dobot_msgs__msg__CircleTarget__Sequence *)(untyped_member);
  dobot_msgs__msg__CircleTarget__Sequence__fini(member);
  return dobot_msgs__msg__CircleTarget__Sequence__init(member, size);
}

static rosidl_typesupport_introspection_c__MessageMember dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_member_array[7] = {
  {
    "header",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, header),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "valid",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, valid),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "reason",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, reason),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "table_plane",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    true,  // is array
    4,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, table_plane),  // bytes offset in struct
    NULL,  // default value
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__size_function__CircleTargetArray__table_plane,  // size() function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_const_function__CircleTargetArray__table_plane,  // get_const(index) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_function__CircleTargetArray__table_plane,  // get(index) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__fetch_function__CircleTargetArray__table_plane,  // fetch(index, &value) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__assign_function__CircleTargetArray__table_plane,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "table_inlier_ratio",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, table_inlier_ratio),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "table_rmse",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, table_rmse),  // bytes offset in struct
    NULL,  // default value
    NULL,  // size() function pointer
    NULL,  // get_const(index) function pointer
    NULL,  // get(index) function pointer
    NULL,  // fetch(index, &value) function pointer
    NULL,  // assign(index, value) function pointer
    NULL  // resize(index) function pointer
  },
  {
    "detections",  // name
    rosidl_typesupport_introspection_c__ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    NULL,  // members of sub message (initialized later)
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs__msg__CircleTargetArray, detections),  // bytes offset in struct
    NULL,  // default value
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__size_function__CircleTargetArray__detections,  // size() function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_const_function__CircleTargetArray__detections,  // get_const(index) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__get_function__CircleTargetArray__detections,  // get(index) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__fetch_function__CircleTargetArray__detections,  // fetch(index, &value) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__assign_function__CircleTargetArray__detections,  // assign(index, value) function pointer
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__resize_function__CircleTargetArray__detections  // resize(index) function pointer
  }
};

static const rosidl_typesupport_introspection_c__MessageMembers dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_members = {
  "dobot_msgs__msg",  // message namespace
  "CircleTargetArray",  // message name
  7,  // number of fields
  sizeof(dobot_msgs__msg__CircleTargetArray),
  false,  // has_any_key_member_
  dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_member_array,  // message members
  dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_init_function,  // function to initialize message memory (memory has to be allocated)
  dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_fini_function  // function to terminate message instance (will not free memory)
};

// this is not const since it must be initialized on first access
// since C does not allow non-integral compile-time constants
static rosidl_message_type_support_t dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_type_support_handle = {
  0,
  &dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_members,
  get_message_typesupport_handle_function,
  &dobot_msgs__msg__CircleTargetArray__get_type_hash,
  &dobot_msgs__msg__CircleTargetArray__get_type_description,
  &dobot_msgs__msg__CircleTargetArray__get_type_description_sources,
};

ROSIDL_TYPESUPPORT_INTROSPECTION_C_EXPORT_dobot_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, msg, CircleTargetArray)() {
  dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_member_array[0].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, std_msgs, msg, Header)();
  dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_member_array[6].members_ =
    ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_c, dobot_msgs, msg, CircleTarget)();
  if (!dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_type_support_handle.typesupport_identifier) {
    dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_type_support_handle.typesupport_identifier =
      rosidl_typesupport_introspection_c__identifier;
  }
  return &dobot_msgs__msg__CircleTargetArray__rosidl_typesupport_introspection_c__CircleTargetArray_message_type_support_handle;
}
#ifdef __cplusplus
}
#endif
