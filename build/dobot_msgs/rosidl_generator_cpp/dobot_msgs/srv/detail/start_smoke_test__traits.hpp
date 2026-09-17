// generated from rosidl_generator_cpp/resource/idl__traits.hpp.em
// with input from dobot_msgs:srv/StartSmokeTest.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/start_smoke_test.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__START_SMOKE_TEST__TRAITS_HPP_
#define DOBOT_MSGS__SRV__DETAIL__START_SMOKE_TEST__TRAITS_HPP_

#include <stdint.h>

#include <sstream>
#include <string>
#include <type_traits>

#include "dobot_msgs/srv/detail/start_smoke_test__struct.hpp"
#include "rosidl_runtime_cpp/traits.hpp"

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const StartSmokeTest_Request & msg,
  std::ostream & out)
{
  out << "{";
  // member: operator_confirmed
  {
    out << "operator_confirmed: ";
    rosidl_generator_traits::value_to_yaml(msg.operator_confirmed, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const StartSmokeTest_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: operator_confirmed
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "operator_confirmed: ";
    rosidl_generator_traits::value_to_yaml(msg.operator_confirmed, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const StartSmokeTest_Request & msg, bool use_flow_style = false)
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
  const dobot_msgs::srv::StartSmokeTest_Request & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::StartSmokeTest_Request & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::StartSmokeTest_Request>()
{
  return "dobot_msgs::srv::StartSmokeTest_Request";
}

template<>
inline const char * name<dobot_msgs::srv::StartSmokeTest_Request>()
{
  return "dobot_msgs/srv/StartSmokeTest_Request";
}

template<>
struct has_fixed_size<dobot_msgs::srv::StartSmokeTest_Request>
  : std::integral_constant<bool, true> {};

template<>
struct has_bounded_size<dobot_msgs::srv::StartSmokeTest_Request>
  : std::integral_constant<bool, true> {};

template<>
struct is_message<dobot_msgs::srv::StartSmokeTest_Request>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace dobot_msgs
{

namespace srv
{

inline void to_flow_style_yaml(
  const StartSmokeTest_Response & msg,
  std::ostream & out)
{
  out << "{";
  // member: accepted
  {
    out << "accepted: ";
    rosidl_generator_traits::value_to_yaml(msg.accepted, out);
    out << ", ";
  }

  // member: report
  {
    out << "report: ";
    rosidl_generator_traits::value_to_yaml(msg.report, out);
  }
  out << "}";
}  // NOLINT(readability/fn_size)

inline void to_block_style_yaml(
  const StartSmokeTest_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  // member: accepted
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "accepted: ";
    rosidl_generator_traits::value_to_yaml(msg.accepted, out);
    out << "\n";
  }

  // member: report
  {
    if (indentation > 0) {
      out << std::string(indentation, ' ');
    }
    out << "report: ";
    rosidl_generator_traits::value_to_yaml(msg.report, out);
    out << "\n";
  }
}  // NOLINT(readability/fn_size)

inline std::string to_yaml(const StartSmokeTest_Response & msg, bool use_flow_style = false)
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
  const dobot_msgs::srv::StartSmokeTest_Response & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::StartSmokeTest_Response & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::StartSmokeTest_Response>()
{
  return "dobot_msgs::srv::StartSmokeTest_Response";
}

template<>
inline const char * name<dobot_msgs::srv::StartSmokeTest_Response>()
{
  return "dobot_msgs/srv/StartSmokeTest_Response";
}

template<>
struct has_fixed_size<dobot_msgs::srv::StartSmokeTest_Response>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::StartSmokeTest_Response>
  : std::integral_constant<bool, false> {};

template<>
struct is_message<dobot_msgs::srv::StartSmokeTest_Response>
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
  const StartSmokeTest_Event & msg,
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
  const StartSmokeTest_Event & msg,
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

inline std::string to_yaml(const StartSmokeTest_Event & msg, bool use_flow_style = false)
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
  const dobot_msgs::srv::StartSmokeTest_Event & msg,
  std::ostream & out, size_t indentation = 0)
{
  dobot_msgs::srv::to_block_style_yaml(msg, out, indentation);
}

[[deprecated("use dobot_msgs::srv::to_yaml() instead")]]
inline std::string to_yaml(const dobot_msgs::srv::StartSmokeTest_Event & msg)
{
  return dobot_msgs::srv::to_yaml(msg);
}

template<>
inline const char * data_type<dobot_msgs::srv::StartSmokeTest_Event>()
{
  return "dobot_msgs::srv::StartSmokeTest_Event";
}

template<>
inline const char * name<dobot_msgs::srv::StartSmokeTest_Event>()
{
  return "dobot_msgs/srv/StartSmokeTest_Event";
}

template<>
struct has_fixed_size<dobot_msgs::srv::StartSmokeTest_Event>
  : std::integral_constant<bool, false> {};

template<>
struct has_bounded_size<dobot_msgs::srv::StartSmokeTest_Event>
  : std::integral_constant<bool, has_bounded_size<dobot_msgs::srv::StartSmokeTest_Request>::value && has_bounded_size<dobot_msgs::srv::StartSmokeTest_Response>::value && has_bounded_size<service_msgs::msg::ServiceEventInfo>::value> {};

template<>
struct is_message<dobot_msgs::srv::StartSmokeTest_Event>
  : std::true_type {};

}  // namespace rosidl_generator_traits

namespace rosidl_generator_traits
{

template<>
inline const char * data_type<dobot_msgs::srv::StartSmokeTest>()
{
  return "dobot_msgs::srv::StartSmokeTest";
}

template<>
inline const char * name<dobot_msgs::srv::StartSmokeTest>()
{
  return "dobot_msgs/srv/StartSmokeTest";
}

template<>
struct has_fixed_size<dobot_msgs::srv::StartSmokeTest>
  : std::integral_constant<
    bool,
    has_fixed_size<dobot_msgs::srv::StartSmokeTest_Request>::value &&
    has_fixed_size<dobot_msgs::srv::StartSmokeTest_Response>::value
  >
{
};

template<>
struct has_bounded_size<dobot_msgs::srv::StartSmokeTest>
  : std::integral_constant<
    bool,
    has_bounded_size<dobot_msgs::srv::StartSmokeTest_Request>::value &&
    has_bounded_size<dobot_msgs::srv::StartSmokeTest_Response>::value
  >
{
};

template<>
struct is_service<dobot_msgs::srv::StartSmokeTest>
  : std::true_type
{
};

template<>
struct is_service_request<dobot_msgs::srv::StartSmokeTest_Request>
  : std::true_type
{
};

template<>
struct is_service_response<dobot_msgs::srv::StartSmokeTest_Response>
  : std::true_type
{
};

}  // namespace rosidl_generator_traits

#endif  // DOBOT_MSGS__SRV__DETAIL__START_SMOKE_TEST__TRAITS_HPP_
