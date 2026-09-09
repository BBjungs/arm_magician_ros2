// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target.hpp"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__BUILDER_HPP_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "dobot_msgs/msg/detail/circle_target__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace dobot_msgs
{

namespace msg
{

namespace builder
{

class Init_CircleTarget_rejection_reason
{
public:
  explicit Init_CircleTarget_rejection_reason(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::msg::CircleTarget rejection_reason(::dobot_msgs::msg::CircleTarget::_rejection_reason_type arg)
  {
    msg_.rejection_reason = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_depth_mad
{
public:
  explicit Init_CircleTarget_depth_mad(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_rejection_reason depth_mad(::dobot_msgs::msg::CircleTarget::_depth_mad_type arg)
  {
    msg_.depth_mad = std::move(arg);
    return Init_CircleTarget_rejection_reason(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_depth_valid_ratio
{
public:
  explicit Init_CircleTarget_depth_valid_ratio(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_depth_mad depth_valid_ratio(::dobot_msgs::msg::CircleTarget::_depth_valid_ratio_type arg)
  {
    msg_.depth_valid_ratio = std::move(arg);
    return Init_CircleTarget_depth_mad(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_top_height
{
public:
  explicit Init_CircleTarget_top_height(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_depth_valid_ratio top_height(::dobot_msgs::msg::CircleTarget::_top_height_type arg)
  {
    msg_.top_height = std::move(arg);
    return Init_CircleTarget_depth_valid_ratio(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_pickable
{
public:
  explicit Init_CircleTarget_pickable(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_top_height pickable(::dobot_msgs::msg::CircleTarget::_pickable_type arg)
  {
    msg_.pickable = std::move(arg);
    return Init_CircleTarget_top_height(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_confidence
{
public:
  explicit Init_CircleTarget_confidence(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_pickable confidence(::dobot_msgs::msg::CircleTarget::_confidence_type arg)
  {
    msg_.confidence = std::move(arg);
    return Init_CircleTarget_pickable(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_size
{
public:
  explicit Init_CircleTarget_size(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_confidence size(::dobot_msgs::msg::CircleTarget::_size_type arg)
  {
    msg_.size = std::move(arg);
    return Init_CircleTarget_confidence(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_depth
{
public:
  explicit Init_CircleTarget_depth(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_size depth(::dobot_msgs::msg::CircleTarget::_depth_type arg)
  {
    msg_.depth = std::move(arg);
    return Init_CircleTarget_size(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_camera_xyz
{
public:
  explicit Init_CircleTarget_camera_xyz(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_depth camera_xyz(::dobot_msgs::msg::CircleTarget::_camera_xyz_type arg)
  {
    msg_.camera_xyz = std::move(arg);
    return Init_CircleTarget_depth(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_center_uv
{
public:
  explicit Init_CircleTarget_center_uv(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_camera_xyz center_uv(::dobot_msgs::msg::CircleTarget::_center_uv_type arg)
  {
    msg_.center_uv = std::move(arg);
    return Init_CircleTarget_camera_xyz(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_class_name
{
public:
  explicit Init_CircleTarget_class_name(::dobot_msgs::msg::CircleTarget & msg)
  : msg_(msg)
  {}
  Init_CircleTarget_center_uv class_name(::dobot_msgs::msg::CircleTarget::_class_name_type arg)
  {
    msg_.class_name = std::move(arg);
    return Init_CircleTarget_center_uv(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

class Init_CircleTarget_id
{
public:
  Init_CircleTarget_id()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_CircleTarget_class_name id(::dobot_msgs::msg::CircleTarget::_id_type arg)
  {
    msg_.id = std::move(arg);
    return Init_CircleTarget_class_name(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTarget msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::msg::CircleTarget>()
{
  return dobot_msgs::msg::builder::Init_CircleTarget_id();
}

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__BUILDER_HPP_
