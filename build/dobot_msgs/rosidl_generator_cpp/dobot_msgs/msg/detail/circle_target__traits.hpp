// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target.hpp"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__TRAITS_HPP_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "dobot_msgs/msg/detail/circle_target__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

// Include directives for member types
// Member 'camera_xyz'
#include "geometry_msgs/msg/detail/point__traits.hpp"

namespace dobot_msgs
{

namespace msg
{

inline void to_flow_style_yaml(
  const CircleTarget & msg,
  std::ostream & out)
{
  out << "{";
  // member: id
  {
    out << "id: ";
    rosidl_generator_traits::value_to_yaml(msg.id, out);
    out << ", ";
  }

  // member: class_name
  {
    out << "class_name: ";
    rosidl_generator_traits::value_to_yaml(msg.class_name, out);
    out << ", ";
  }

  // member: center_uv
  {
    if (msg.center_uv.size() == 0) {
      out << "center_uv: []";
    } else {
      out << "center_uv: [";
      size_t pending_items = msg.center_uv.size();
      for (auto item : msg.center_uv) {
        rosidl_generator_traits::value_to_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: camera_xyz
  {
    out << "camera_xyz: ";
    to_flow_style_yaml(msg.camera_xyz, out);
    out << ", ";
  }

  // member: depth
  {
    out << "depth: ";
    rosidl_generator_traits::value_to_yaml(msg.depth, out);
    out << ", ";
  }

  // member: size
  {
    out << "size: ";
    rosidl_generator_traits::value_to_yaml(msg.size, out);
    out << ", ";
  }

  // member: confidence
  {
    out << "confidence: ";
    rosidl_generator_traits::value_to_yaml(msg.confidence, out);
    out << ", ";
  }

  // member: pickable
  {
    out << "pickable: ";
    rosidl_generator_traits::value_to_yaml(msg.pickable, out);
    out << ", ";
  }

  // member: top_height
  {
    out << "top_height: ";
    rosidl_generator_traits::value_to_yaml(msg.top_height, out);
    out << ", ";
  }

  // member: depth_valid_ratio
  {
    out << "depth_valid_ratio: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_valid_ratio, out);
    out << ", ";
  }

  // member: depth_mad
  {
    out << "depth_mad: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_mad, out);
    out << ", ";
  }

  // member: rejection_reason
  {
    out << "rejection_reason: ";
    rosidl_generator_traits::value_to_yaml(msg.rejection_reason, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const CircleTarget & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: id
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "id: ";
    rosidl_generator_traits::value_to_yaml(msg.id, out);
    out << "\n";
  }

  // member: class_name
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "class_name: ";
    rosidl_generator_traits::value_to_yaml(msg.class_name, out);
    out << "\n";
  }

  // member: center_uv
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.center_uv.size() == 0) {
      out << "center_uv: []\n";
    } else {
      out << "center_uv:\n";
      for (auto item : msg.center_uv) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "- ";
        rosidl_generator_traits::value_to_yaml(item, out);
        out << "\n";
      }
    }
  }

  // member: camera_xyz
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "camera_xyz:\n";
    to_block_style_yaml(msg.camera_xyz, out, indentation + 2);
  }

  // member: depth
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "depth: ";
    rosidl_generator_traits::value_to_yaml(msg.depth, out);
    out << "\n";
  }

  // member: size
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "size: ";
    rosidl_generator_traits::value_to_yaml(msg.size, out);
    out << "\n";
  }

  // member: confidence
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "confidence: ";
    rosidl_generator_traits::value_to_yaml(msg.confidence, out);
    out << "\n";
  }

  // member: pickable
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "pickable: ";
    rosidl_generator_traits::value_to_yaml(msg.pickable, out);
    out << "\n";
  }

  // member: top_height
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "top_height: ";
    rosidl_generator_traits::value_to_yaml(msg.top_height, out);
    out << "\n";
  }

  // member: depth_valid_ratio
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "depth_valid_ratio: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_valid_ratio, out);
    out << "\n";
  }

  // member: depth_mad
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "depth_mad: ";
    rosidl_generator_traits::value_to_yaml(msg.depth_mad, out);
    out << "\n";
  }

  // member: rejection_reason
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "rejection_reason: ";
    rosidl_generator_traits::value_to_yaml(msg.rejection_reason, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const CircleTarget & msg, bool use_flow_style = false)
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
  const dobot_msgs::msg::CircleTarget & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::msg::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::msg::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::msg::CircleTarget & msg)
{
  return dobot_msgs::msg::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::msg::CircleTarget>()
{
  return "dobot_msgs::msg::CircleTarget";
}

template<>
inline const char * name<dobot_msgs::msg::CircleTarget>()
{
  return "dobot_msgs/msg/CircleTarget";
}

template<>
struct has_fixed_size<dobot_msgs::msg::CircleTarget>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::msg::CircleTarget>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<dobot_msgs::msg::CircleTarget>
  : std::true_type {};

}  // namespace rosidl_generator_traits

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__TRAITS_HPP_
