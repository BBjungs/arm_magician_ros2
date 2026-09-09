// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target_array.hpp"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__TRAITS_HPP_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "dobot_msgs/msg/detail/circle_target_array__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__traits.hpp"
// Member 'detections'
#include "dobot_msgs/msg/detail/circle_target__traits.hpp"

namespace dobot_msgs
{

namespace msg
{

inline void to_flow_style_yaml(
  const CircleTargetArray & msg,
  std::ostream & out)
{
  out << "{";
  // member: header
  {
    out << "header: ";
    to_flow_style_yaml(msg.header, out);
    out << ", ";
  }

  // member: valid
  {
    out << "valid: ";
    rosidl_generator_traits::value_to_yaml(msg.valid, out);
    out << ", ";
  }

  // member: reason
  {
    out << "reason: ";
    rosidl_generator_traits::value_to_yaml(msg.reason, out);
    out << ", ";
  }

  // member: table_plane
  {
    if (msg.table_plane.size() == 0) {
      out << "table_plane: []";
    } else {
      out << "table_plane: [";
      size_t pending_items = msg.table_plane.size();
      for (auto item : msg.table_plane) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: table_inlier_ratio
  {
    out << "table_inlier_ratio: ";
    rosidl_generator_traits::value_to_yaml(msg.table_inlier_ratio, out);
    out << ", ";
  }

  // member: table_rmse
  {
    out << "table_rmse: ";
    rosidl_generator_traits::value_to_yaml(msg.table_rmse, out);
    out << ", ";
  }

  // member: detections
  {
    if (msg.detections.size() == 0) {
      out << "detections: []";
    } else {
      out << "detections: [";
      size_t pending_items = msg.detections.size();
      for (auto item : msg.detections) {
        to_flow_style_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const CircleTargetArray & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: header
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "header:\n";
    to_block_style_yaml(msg.header, out, indentation + 2);
  }

  // member: valid
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "valid: ";
    rosidl_generator_traits::value_to_yaml(msg.valid, out);
    out << "\n";
  }

  // member: reason
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "reason: ";
    rosidl_generator_traits::value_to_yaml(msg.reason, out);
    out << "\n";
  }

  // member: table_plane
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.table_plane.size() == 0) {
      out << "table_plane: []\n";
    } else {
      out << "table_plane:\n";
      for (auto item : msg.table_plane) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: table_inlier_ratio
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "table_inlier_ratio: ";
    rosidl_generator_traits::value_to_yaml(msg.table_inlier_ratio, out);
    out << "\n";
  }

  // member: table_rmse
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "table_rmse: ";
    rosidl_generator_traits::value_to_yaml(msg.table_rmse, out);
    out << "\n";
  }

  // member: detections
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.detections.size() == 0) {
      out << "detections: []\n";
    } else {
      out << "detections:\n";
      for (auto item : msg.detections) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "-\n";
        to_block_style_yaml(item, out, indentation + 2);
      }
    }
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const CircleTargetArray & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace msg

}  // namespace dobot_msgs

namespace rosidl_generator_traits
{

[[deprecated("use dobot_msgs::msg::to_block_style_yaml() instead")]]
inline void to_yaml(
  const dobot_msgs::msg::CircleTargetArray & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::msg::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::msg::CircleTargetArray & msg)
{
  return dobot_msgs::msg::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::msg::CircleTargetArray>()
{
  return "dobot_msgs::msg::CircleTargetArray";
}

template<>
inline const char * name<dobot_msgs::msg::CircleTargetArray>()
{
  return "dobot_msgs/msg/CircleTargetArray";
}

template<>
struct has_fixed_size<dobot_msgs::msg::CircleTargetArray>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::msg::CircleTargetArray>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<dobot_msgs::msg::CircleTargetArray>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__TRAITS_HPP_
