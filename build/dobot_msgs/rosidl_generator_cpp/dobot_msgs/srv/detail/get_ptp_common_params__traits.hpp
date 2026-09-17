// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from dobot_msgs:srv/GetPTPCommonParams.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/get_ptp_common_params.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__TRAITS_HPP_
#define DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "dobot_msgs/srv/detail/get_ptp_common_params__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const GetPTPCommonParams_Request & msg,
  std::ostream & out)
{
  (void)msg;
  out << "null";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const GetPTPCommonParams_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  (void)msg;
  (void)indentation;
  out << "null\n";
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const GetPTPCommonParams_Request & msg, bool use_flow_style = false)
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
  const dobot_msgs::srv::GetPTPCommonParams_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::GetPTPCommonParams_Request & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::GetPTPCommonParams_Request>()
{
  return "dobot_msgs::srv::GetPTPCommonParams_Request";
}

template<>
inline const char * name<dobot_msgs::srv::GetPTPCommonParams_Request>()
{
  return "dobot_msgs/srv/GetPTPCommonParams_Request";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GetPTPCommonParams_Request>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Request>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<dobot_msgs::srv::GetPTPCommonParams_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const GetPTPCommonParams_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: success
  {
    out << "success: ";
    rosidl_generator_traits::value_to_yaml(msg.success, out);
    out << ", ";
  }

  // member: velocity_percent
  {
    out << "velocity_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.velocity_percent, out);
    out << ", ";
  }

  // member: acceleration_percent
  {
    out << "acceleration_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.acceleration_percent, out);
    out << ", ";
  }

  // member: raw_velocity_percent
  {
    out << "raw_velocity_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.raw_velocity_percent, out);
    out << ", ";
  }

  // member: raw_acceleration_percent
  {
    out << "raw_acceleration_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.raw_acceleration_percent, out);
    out << ", ";
  }

  // member: timed_out
  {
    out << "timed_out: ";
    rosidl_generator_traits::value_to_yaml(msg.timed_out, out);
    out << ", ";
  }

  // member: error
  {
    out << "error: ";
    rosidl_generator_traits::value_to_yaml(msg.error, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const GetPTPCommonParams_Response & msg,
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

  // member: velocity_percent
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "velocity_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.velocity_percent, out);
    out << "\n";
  }

  // member: acceleration_percent
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "acceleration_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.acceleration_percent, out);
    out << "\n";
  }

  // member: raw_velocity_percent
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "raw_velocity_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.raw_velocity_percent, out);
    out << "\n";
  }

  // member: raw_acceleration_percent
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "raw_acceleration_percent: ";
    rosidl_generator_traits::value_to_yaml(msg.raw_acceleration_percent, out);
    out << "\n";
  }

  // member: timed_out
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "timed_out: ";
    rosidl_generator_traits::value_to_yaml(msg.timed_out, out);
    out << "\n";
  }

  // member: error
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "error: ";
    rosidl_generator_traits::value_to_yaml(msg.error, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const GetPTPCommonParams_Response & msg, bool use_flow_style = false)
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
  const dobot_msgs::srv::GetPTPCommonParams_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::GetPTPCommonParams_Response & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::GetPTPCommonParams_Response>()
{
  return "dobot_msgs::srv::GetPTPCommonParams_Response";
}

template<>
inline const char * name<dobot_msgs::srv::GetPTPCommonParams_Response>()
{
  return "dobot_msgs/srv/GetPTPCommonParams_Response";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GetPTPCommonParams_Response>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Response>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<dobot_msgs::srv::GetPTPCommonParams_Response>
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
  const GetPTPCommonParams_Event & msg,
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
  const GetPTPCommonParams_Event & msg,
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

inline std::string to_yaml(const GetPTPCommonParams_Event & msg, bool use_flow_style = false)
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
  const dobot_msgs::srv::GetPTPCommonParams_Event & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::GetPTPCommonParams_Event & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::GetPTPCommonParams_Event>()
{
  return "dobot_msgs::srv::GetPTPCommonParams_Event";
}

template<>
inline const char * name<dobot_msgs::srv::GetPTPCommonParams_Event>()
{
  return "dobot_msgs/srv/GetPTPCommonParams_Event";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GetPTPCommonParams_Event>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Event>
  : std::integral_constant<bool, has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Request>::value && has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Response>::value && has_bounded_size<service_msgs::msg::ServiceEventInfo>::value> {};

template<>
struct is_message<dobot_msgs::srv::GetPTPCommonParams_Event>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<dobot_msgs::srv::GetPTPCommonParams>()
{
  return "dobot_msgs::srv::GetPTPCommonParams";
}

template<>
inline const char * name<dobot_msgs::srv::GetPTPCommonParams>()
{
  return "dobot_msgs/srv/GetPTPCommonParams";
}

template<>
struct has_fixed_size<dobot_msgs::srv::GetPTPCommonParams>
  : std::integral_constant<
    bool,
    has_fixed_size<dobot_msgs::srv::GetPTPCommonParams_Request>::value &&
    has_fixed_size<dobot_msgs::srv::GetPTPCommonParams_Response>::value
  >
{
};

template<>
struct has_bounded_size<dobot_msgs::srv::GetPTPCommonParams>
  : std::integral_constant<
    bool,
    has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Request>::value &&
    has_bounded_size<dobot_msgs::srv::GetPTPCommonParams_Response>::value
  >
{
};

template<>
struct is_service<dobot_msgs::srv::GetPTPCommonParams>
  : std::true_type
{
};

template<>
struct is_service_request<dobot_msgs::srv::GetPTPCommonParams_Request>
  : std::true_type
{
};

template<>
struct is_service_response<dobot_msgs::srv::GetPTPCommonParams_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__TRAITS_HPP_
