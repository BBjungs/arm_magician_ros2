// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target_array.hpp"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__BUILDER_HPP_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "dobot_msgs/msg/detail/circle_target_array__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace dobot_msgs
{

namespace msg
{

namespace builder
{

class Init_CircleTargetArray_detections
{
public:
  explicit Init_CircleTargetArray_detections(::dobot_msgs::msg::CircleTargetArray & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::msg::CircleTargetArray detections(::dobot_msgs::msg::CircleTargetArray::_detections_type arg)
  {
    msg_.detections = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

class Init_CircleTargetArray_table_rmse
{
public:
  explicit Init_CircleTargetArray_table_rmse(::dobot_msgs::msg::CircleTargetArray & msg)
  : msg_(msg)
  {}
  Init_CircleTargetArray_detections table_rmse(::dobot_msgs::msg::CircleTargetArray::_table_rmse_type arg)
  {
    msg_.table_rmse = std::move(arg);
    return Init_CircleTargetArray_detections(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

class Init_CircleTargetArray_table_inlier_ratio
{
public:
  explicit Init_CircleTargetArray_table_inlier_ratio(::dobot_msgs::msg::CircleTargetArray & msg)
  : msg_(msg)
  {}
  Init_CircleTargetArray_table_rmse table_inlier_ratio(::dobot_msgs::msg::CircleTargetArray::_table_inlier_ratio_type arg)
  {
    msg_.table_inlier_ratio = std::move(arg);
    return Init_CircleTargetArray_table_rmse(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

class Init_CircleTargetArray_table_plane
{
public:
  explicit Init_CircleTargetArray_table_plane(::dobot_msgs::msg::CircleTargetArray & msg)
  : msg_(msg)
  {}
  Init_CircleTargetArray_table_inlier_ratio table_plane(::dobot_msgs::msg::CircleTargetArray::_table_plane_type arg)
  {
    msg_.table_plane = std::move(arg);
    return Init_CircleTargetArray_table_inlier_ratio(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

class Init_CircleTargetArray_reason
{
public:
  explicit Init_CircleTargetArray_reason(::dobot_msgs::msg::CircleTargetArray & msg)
  : msg_(msg)
  {}
  Init_CircleTargetArray_table_plane reason(::dobot_msgs::msg::CircleTargetArray::_reason_type arg)
  {
    msg_.reason = std::move(arg);
    return Init_CircleTargetArray_table_plane(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

class Init_CircleTargetArray_valid
{
public:
  explicit Init_CircleTargetArray_valid(::dobot_msgs::msg::CircleTargetArray & msg)
  : msg_(msg)
  {}
  Init_CircleTargetArray_reason valid(::dobot_msgs::msg::CircleTargetArray::_valid_type arg)
  {
    msg_.valid = std::move(arg);
    return Init_CircleTargetArray_reason(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

class Init_CircleTargetArray_header
{
public:
  Init_CircleTargetArray_header()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_CircleTargetArray_valid header(::dobot_msgs::msg::CircleTargetArray::_header_type arg)
  {
    msg_.header = std::move(arg);
    return Init_CircleTargetArray_valid(msg_);
  }

private:
  ::dobot_msgs::msg::CircleTargetArray msg_;
};

}  // namespace builder

}  // namespace msg

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::msg::CircleTargetArray>()
{
  return dobot_msgs::msg::builder::Init_CircleTargetArray_header();
}

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__BUILDER_HPP_
