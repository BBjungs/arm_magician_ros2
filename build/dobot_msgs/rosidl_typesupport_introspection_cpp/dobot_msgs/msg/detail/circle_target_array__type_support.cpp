// generated from rosidl_typesupport_introspection_cpp/resource/idl__type_support.cpp.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

#include "array"
#include "cstddef"
#include "string"
#include "vector"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_typesupport_cpp/message_type_support.hpp"
#include "rosidl_typesupport_interface/macros.h"
#include "dobot_msgs/msg/detail/circle_target_array__functions.h"
#include "dobot_msgs/msg/detail/circle_target_array__struct.hpp"
#include "rosidl_typesupport_introspection_cpp/field_types.hpp"
#include "rosidl_typesupport_introspection_cpp/identifier.hpp"
#include "rosidl_typesupport_introspection_cpp/message_introspection.hpp"
#include "rosidl_typesupport_introspection_cpp/message_type_support_decl.hpp"
#include "rosidl_typesupport_introspection_cpp/visibility_control.h"

namespace dobot_msgs
{

namespace msg
{

namespace rosidl_typesupport_introspection_cpp
{

void CircleTargetArray_init_function(
  void * message_memory, rosidl_runtime_cpp::MessageInitialization _init)
{
  new (message_memory) dobot_msgs::msg::CircleTargetArray(_init);
}

void CircleTargetArray_fini_function(void * message_memory)
{
  auto typed_message = static_cast<dobot_msgs::msg::CircleTargetArray *>(message_memory);
  typed_message->~CircleTargetArray();
}

size_t size_function__CircleTargetArray__table_plane(const void * untyped_member)
{
  (void)untyped_member;
  return 4;
}

const void * get_const_function__CircleTargetArray__table_plane(const void * untyped_member, size_t index)
{
  const auto & member =
    *reinterpret_cast<const std::array<double, 4> *>(untyped_member);
  return &member[index];
}

void * get_function__CircleTargetArray__table_plane(void * untyped_member, size_t index)
{
  auto & member =
    *reinterpret_cast<std::array<double, 4> *>(untyped_member);
  return &member[index];
}

void fetch_function__CircleTargetArray__table_plane(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const auto & item = *reinterpret_cast<const double *>(
    get_const_function__CircleTargetArray__table_plane(untyped_member, index));
  auto & value = *reinterpret_cast<double *>(untyped_value);
  value = item;
}

void assign_function__CircleTargetArray__table_plane(
  void * untyped_member, size_t index, const void * untyped_value)
{
  auto & item = *reinterpret_cast<double *>(
    get_function__CircleTargetArray__table_plane(untyped_member, index));
  const auto & value = *reinterpret_cast<const double *>(untyped_value);
  item = value;
}

size_t size_function__CircleTargetArray__detections(const void * untyped_member)
{
  const auto * member = reinterpret_cast<const std::vector<dobot_msgs::msg::CircleTarget> *>(untyped_member);
  return member->size();
}

const void * get_const_function__CircleTargetArray__detections(const void * untyped_member, size_t index)
{
  const auto & member =
    *reinterpret_cast<const std::vector<dobot_msgs::msg::CircleTarget> *>(untyped_member);
  return &member[index];
}

void * get_function__CircleTargetArray__detections(void * untyped_member, size_t index)
{
  auto & member =
    *reinterpret_cast<std::vector<dobot_msgs::msg::CircleTarget> *>(untyped_member);
  return &member[index];
}

void fetch_function__CircleTargetArray__detections(
  const void * untyped_member, size_t index, void * untyped_value)
{
  const auto & item = *reinterpret_cast<const dobot_msgs::msg::CircleTarget *>(
    get_const_function__CircleTargetArray__detections(untyped_member, index));
  auto & value = *reinterpret_cast<dobot_msgs::msg::CircleTarget *>(untyped_value);
  value = item;
}

void assign_function__CircleTargetArray__detections(
  void * untyped_member, size_t index, const void * untyped_value)
{
  auto & item = *reinterpret_cast<dobot_msgs::msg::CircleTarget *>(
    get_function__CircleTargetArray__detections(untyped_member, index));
  const auto & value = *reinterpret_cast<const dobot_msgs::msg::CircleTarget *>(untyped_value);
  item = value;
}

void resize_function__CircleTargetArray__detections(void * untyped_member, size_t size)
{
  auto * member =
    reinterpret_cast<std::vector<dobot_msgs::msg::CircleTarget> *>(untyped_member);
  member->resize(size);
}

static const ::rosidl_typesupport_introspection_cpp::MessageMember CircleTargetArray_message_member_array[7] = {
  {
    "header",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<std_msgs::msg::Header>(),  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, header),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "valid",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_BOOLEAN,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, valid),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "reason",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_STRING,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, reason),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "table_plane",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    true,  // is array
    4,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, table_plane),  // bytes offset in struct
    nullptr,  // default value
    size_function__CircleTargetArray__table_plane,  // size() function pointer
    get_const_function__CircleTargetArray__table_plane,  // get_const(index) function pointer
    get_function__CircleTargetArray__table_plane,  // get(index) function pointer
    fetch_function__CircleTargetArray__table_plane,  // fetch(index, &value) function pointer
    assign_function__CircleTargetArray__table_plane,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "table_inlier_ratio",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, table_inlier_ratio),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "table_rmse",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_DOUBLE,  // type
    0,  // upper bound of string
    nullptr,  // members of sub message
    false,  // is key
    false,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, table_rmse),  // bytes offset in struct
    nullptr,  // default value
    nullptr,  // size() function pointer
    nullptr,  // get_const(index) function pointer
    nullptr,  // get(index) function pointer
    nullptr,  // fetch(index, &value) function pointer
    nullptr,  // assign(index, value) function pointer
    nullptr  // resize(index) function pointer
  },
  {
    "detections",  // name
    ::rosidl_typesupport_introspection_cpp::ROS_TYPE_MESSAGE,  // type
    0,  // upper bound of string
    ::rosidl_typesupport_introspection_cpp::get_message_type_support_handle<dobot_msgs::msg::CircleTarget>(),  // members of sub message
    false,  // is key
    true,  // is array
    0,  // array size
    false,  // is upper bound
    offsetof(dobot_msgs::msg::CircleTargetArray, detections),  // bytes offset in struct
    nullptr,  // default value
    size_function__CircleTargetArray__detections,  // size() function pointer
    get_const_function__CircleTargetArray__detections,  // get_const(index) function pointer
    get_function__CircleTargetArray__detections,  // get(index) function pointer
    fetch_function__CircleTargetArray__detections,  // fetch(index, &value) function pointer
    assign_function__CircleTargetArray__detections,  // assign(index, value) function pointer
    resize_function__CircleTargetArray__detections  // resize(index) function pointer
  }
};

static const ::rosidl_typesupport_introspection_cpp::MessageMembers CircleTargetArray_message_members = {
  "dobot_msgs::msg",  // message namespace
  "CircleTargetArray",  // message name
  7,  // number of fields
  sizeof(dobot_msgs::msg::CircleTargetArray),
  false,  // has_any_key_member_
  CircleTargetArray_message_member_array,  // message members
  CircleTargetArray_init_function,  // function to initialize message memory (memory has to be allocated)
  CircleTargetArray_fini_function  // function to terminate message instance (will not free memory)
};

static const rosidl_message_type_support_t CircleTargetArray_message_type_support_handle = {
  ::rosidl_typesupport_introspection_cpp::typesupport_identifier,
  &CircleTargetArray_message_members,
  get_message_typesupport_handle_function,
  &dobot_msgs__msg__CircleTargetArray__get_type_hash,
  &dobot_msgs__msg__CircleTargetArray__get_type_description,
  &dobot_msgs__msg__CircleTargetArray__get_type_description_sources,
};

}  // namespace rosidl_typesupport_introspection_cpp

}  // namespace msg

}  // namespace dobot_msgs


namespace rosidl_typesupport_introspection_cpp
{

template<>
ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
get_message_type_support_handle<dobot_msgs::msg::CircleTargetArray>()
{
  return &::dobot_msgs::msg::rosidl_typesupport_introspection_cpp::CircleTargetArray_message_type_support_handle;
}

}  // namespace rosidl_typesupport_introspection_cpp

#ifdef __cplusplus
extern "C"
{
#endif

ROSIDL_TYPESUPPORT_INTROSPECTION_CPP_PUBLIC
const rosidl_message_type_support_t *
ROSIDL_TYPESUPPORT_INTERFACE__MESSAGE_SYMBOL_NAME(rosidl_typesupport_introspection_cpp, dobot_msgs, msg, CircleTargetArray)() {
  return &::dobot_msgs::msg::rosidl_typesupport_introspection_cpp::CircleTargetArray_message_type_support_handle;
}

#ifdef __cplusplus
}
#endif
