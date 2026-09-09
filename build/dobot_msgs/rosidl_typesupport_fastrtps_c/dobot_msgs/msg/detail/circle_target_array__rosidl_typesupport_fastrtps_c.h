// generated from rosidl_typesupport_fastrtps_c/resource/idl__rosidl_typesupport_fastrtps_c.h.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice
#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_


#include <stddef.h>
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_interface/macros.h"
#include "dobot_msgs/msg/rosidl_typesupport_fastrtps_c__visibility_control.h"
#include "dobot_msgs/msg/detail/circle_target_array__struct.h"
#include "fastcdr/Cdr.h"

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
bool cdr_serialize_dobot_msgs__msg__CircleTargetArray(
  const dobot_msgs__msg__CircleTargetArray * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
bool cdr_deserialize_dobot_msgs__msg__CircleTargetArray(
  eprosima::fastcdr::Cdr &,
  dobot_msgs__msg__CircleTargetArray * ros_message);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
size_t get_serialized_size_dobot_msgs__msg__CircleTargetArray(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
size_t max_serialized_size_dobot_msgs__msg__CircleTargetArray(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
bool cdr_serialize_key_dobot_msgs__msg__CircleTargetArray(
  const dobot_msgs__msg__CircleTargetArray * ros_message,
  eprosima::fastcdr::Cdr & cdr);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
size_t get_serialized_size_key_dobot_msgs__msg__CircleTargetArray(
  const void * untyped_ros_message,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
size_t max_serialized_size_key_dobot_msgs__msg__CircleTargetArray(
  bool & full_bounded,
  bool & is_plain,
  size_t current_alignment);

ROSIDL_TYPESUPPORT_FASTRTPS_C_PUBLIC_dobot_msgs
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_fastrtps_c, dobot_msgs, msg, CircleTargetArray)();

#ifdef __cplusplus
}
#endif

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__ROSIDL_TYPESUPPORT_FASTRTPS_C_H_
