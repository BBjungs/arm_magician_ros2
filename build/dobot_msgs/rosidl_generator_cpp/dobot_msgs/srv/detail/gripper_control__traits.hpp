// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from dobot_msgs:srv/GripperControl.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/gripper_control.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__GRIPPER_CONTROL__TRAITS_HPP_
#define DOBOT_MSGS__SRV__DETAIL__GRIPPER_CONTROL__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "dobot_msgs/srv/detail/gripper_control__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const GripperControl_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: gripper_state
  {
    out << "gripper_state: ";
    rosidl_generator_traits::value_to_yaml(msg.gripper_state, out);
    out << ", ";
  }

  // member: keep_compressor_running
  {
    out << "keep_compressor_running: ";
    rosidl_generator_traits::value_to_yaml(msg.keep_compressor_running, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const GripperControl_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: gripper_state
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "gripper_state: ";
    rosidl_generator_traits::value_to_yaml(msg.gripper_state, out);
    out << "\n";
  }

  // member: keep_compressor_running
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "keep_compressor_running: ";
    rosidl_generator_traits::value_to_yaml(msg.keep_compressor_running, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const GripperControl_Request & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_generator_traits
{

[[deprecated("use dobot_msgs::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const dobot_msgs::srv::GripperControl_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::GripperControl_Request & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::GripperControl_Request>()
{
  return "dobot_msgs::srv::GripperControl_Request";
}

template<>
inline const char * name<dobot_msgs::srv::GripperControl_Request>()
{
  return "dobot_msgs/srv/GripperControl_Request";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GripperControl_Request>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::GripperControl_Request>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<dobot_msgs::srv::GripperControl_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const GripperControl_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: success
  {
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << ", ";
  }

  // member: message
  {
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const GripperControl_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: success
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << "\n";
  }

  // member: message
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "message: ";
    rosidl_generator_traits::value_to_yaml(msg.message, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const GripperControl_Response & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_generator_traits
{

[[deprecated("use dobot_msgs::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const dobot_msgs::srv::GripperControl_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::GripperControl_Response & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::GripperControl_Response>()
{
  return "dobot_msgs::srv::GripperControl_Response";
}

template<>
inline const char * name<dobot_msgs::srv::GripperControl_Response>()
{
  return "dobot_msgs/srv/GripperControl_Response";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GripperControl_Response>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::GripperControl_Response>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<dobot_msgs::srv::GripperControl_Response>
  : std::true_type {};

}  // namespace rosidl_generator_traits

// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__traits.hpp"

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const GripperControl_Event & msg,
  std::ostream & out)
{
  out << "{";
  // member: info
  {
    out << "info: ";
    to_flow_style_yaml(msg.info, out);
    out << ", ";
  }

  // member: request
  {
    if (msg.request.size() == 0) {
      out << "request: []";
    } else {
      out << "request: [";
      size_t pending_items = msg.request.size();
      for (auto item : msg.request) {
        to_flow_style_yaml(item, out);
        if (--pending_items > 0) {
          out << ", ";
        }
      }
      out << "]";
    }
    out << ", ";
  }

  // member: response
  {
    if (msg.response.size() == 0) {
      out << "response: []";
    } else {
      out << "response: [";
      size_t pending_items = msg.response.size();
      for (auto item : msg.response) {
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
  const GripperControl_Event & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: info
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "info:\n";
    to_block_style_yaml(msg.info, out, indentation + 2);
  }

  // member: request
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.request.size() == 0) {
      out << "request: []\n";
    } else {
      out << "request:\n";
      for (auto item : msg.request) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "-\n";
        to_block_style_yaml(item, out, indentation + 2);
      }
    }
  }

  // member: response
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    if (msg.response.size() == 0) {
      out << "response: []\n";
    } else {
      out << "response:\n";
      for (auto item : msg.response) {
        if (indentation > 0) {
          out << std::string(indentation, ' ');
        }
        out << "-\n";
        to_block_style_yaml(item, out, indentation + 2);
      }
    }
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const GripperControl_Event & msg, bool use_flow_style = false)
{
  std::ostringstream out;
  if (use_flow_style) {
    to_flow_style_yaml(msg, out);
  } else {
    to_block_style_yaml(msg, out);
  }
  return out.str();
}

}  // namespace srv

}  // namespace dobot_msgs

namespace rosidl_generator_traits
{

[[deprecated("use dobot_msgs::srv::to_block_style_yaml() instead")]]
inline void to_yaml(
  const dobot_msgs::srv::GripperControl_Event & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::GripperControl_Event & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::GripperControl_Event>()
{
  return "dobot_msgs::srv::GripperControl_Event";
}

template<>
inline const char * name<dobot_msgs::srv::GripperControl_Event>()
{
  return "dobot_msgs/srv/GripperControl_Event";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GripperControl_Event>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::GripperControl_Event>
  : std::integral_constant<bool, has_bounded_size<dobot_msgs::srv::GripperControl_Request>::value && has_bounded_size<dobot_msgs::srv::GripperControl_Response>::value && has_bounded_size<service_msgs::msg::ServiceEventInfo>::value> {};

template<>
struct is_message<dobot_msgs::srv::GripperControl_Event>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<dobot_msgs::srv::GripperControl>()
{
  return "dobot_msgs::srv::GripperControl";
}

template<>
inline const char * name<dobot_msgs::srv::GripperControl>()
{
  return "dobot_msgs/srv/GripperControl";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GripperControl>
  : std::integral_constant<
    bool,
    has_fixed_size<dobot_msgs::srv::GripperControl_Request>::value &&
    has_fixed_size<dobot_msgs::srv::GripperControl_Response>::value
  >
{
};

template<>
struct has_bounded_size<dobot_msgs::srv::GripperControl>
  : std::integral_constant<
    bool,
    has_bounded_size<dobot_msgs::srv::GripperControl_Request>::value &&
    has_bounded_size<dobot_msgs::srv::GripperControl_Response>::value
  >
{
};

template<>
struct is_service<dobot_msgs::srv::GripperControl>
  : std::true_type
{
};

template<>
struct is_service_request<dobot_msgs::srv::GripperControl_Request>
  : std::true_type
{
};

template<>
struct is_service_response<dobot_msgs::srv::GripperControl_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // DOBOT_MSGS__SRV__DETAIL__GRIPPER_CONTROL__TRAITS_HPP_
