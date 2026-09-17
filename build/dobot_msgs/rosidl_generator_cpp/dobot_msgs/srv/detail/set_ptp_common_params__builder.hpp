// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from dobot_msgs:srv/SetPTPCommonParams.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/set_ptp_common_params.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__SET_PTP_COMMON_PARAMS__BUILDER_HPP_
#define DOBOT_MSGS__SRV__DETAIL__SET_PTP_COMMON_PARAMS__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "dobot_msgs/srv/detail/set_ptp_common_params__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_SetPTPCommonParams_Request_acceleration_percent
{
public:
  explicit Init_SetPTPCommonParams_Request_acceleration_percent(::dobot_msgs::srv::SetPTPCommonParams_Request & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::SetPTPCommonParams_Request acceleration_percent(::dobot_msgs::srv::SetPTPCommonParams_Request::_acceleration_percent_type arg)
  {
    msg_.acceleration_percent = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Request msg_;
};

class Init_SetPTPCommonParams_Request_velocity_percent
{
public:
  Init_SetPTPCommonParams_Request_velocity_percent()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_SetPTPCommonParams_Request_acceleration_percent velocity_percent(::dobot_msgs::srv::SetPTPCommonParams_Request::_velocity_percent_type arg)
  {
    msg_.velocity_percent = std::move(arg);
    return Init_SetPTPCommonParams_Request_acceleration_percent(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Request msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::SetPTPCommonParams_Request>()
{
  return dobot_msgs::srv::builder::Init_SetPTPCommonParams_Request_velocity_percent();
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_SetPTPCommonParams_Response_error
{
public:
  explicit Init_SetPTPCommonParams_Response_error(::dobot_msgs::srv::SetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::SetPTPCommonParams_Response error(::dobot_msgs::srv::SetPTPCommonParams_Response::_error_type arg)
  {
    msg_.error = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Response msg_;
};

class Init_SetPTPCommonParams_Response_timed_out
{
public:
  explicit Init_SetPTPCommonParams_Response_timed_out(::dobot_msgs::srv::SetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_SetPTPCommonParams_Response_error timed_out(::dobot_msgs::srv::SetPTPCommonParams_Response::_timed_out_type arg)
  {
    msg_.timed_out = std::move(arg);
    return Init_SetPTPCommonParams_Response_error(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Response msg_;
};

class Init_SetPTPCommonParams_Response_acknowledged
{
public:
  explicit Init_SetPTPCommonParams_Response_acknowledged(::dobot_msgs::srv::SetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_SetPTPCommonParams_Response_timed_out acknowledged(::dobot_msgs::srv::SetPTPCommonParams_Response::_acknowledged_type arg)
  {
    msg_.acknowledged = std::move(arg);
    return Init_SetPTPCommonParams_Response_timed_out(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Response msg_;
};

class Init_SetPTPCommonParams_Response_success
{
public:
  Init_SetPTPCommonParams_Response_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_SetPTPCommonParams_Response_acknowledged success(::dobot_msgs::srv::SetPTPCommonParams_Response::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_SetPTPCommonParams_Response_acknowledged(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::SetPTPCommonParams_Response>()
{
  return dobot_msgs::srv::builder::Init_SetPTPCommonParams_Response_success();
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_SetPTPCommonParams_Event_response
{
public:
  explicit Init_SetPTPCommonParams_Event_response(::dobot_msgs::srv::SetPTPCommonParams_Event & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::SetPTPCommonParams_Event response(::dobot_msgs::srv::SetPTPCommonParams_Event::_response_type arg)
  {
    msg_.response = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Event msg_;
};

class Init_SetPTPCommonParams_Event_request
{
public:
  explicit Init_SetPTPCommonParams_Event_request(::dobot_msgs::srv::SetPTPCommonParams_Event & msg)
  : msg_(msg)
  {}
  Init_SetPTPCommonParams_Event_response request(::dobot_msgs::srv::SetPTPCommonParams_Event::_request_type arg)
  {
    msg_.request = std::move(arg);
    return Init_SetPTPCommonParams_Event_response(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Event msg_;
};

class Init_SetPTPCommonParams_Event_info
{
public:
  Init_SetPTPCommonParams_Event_info()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_SetPTPCommonParams_Event_request info(::dobot_msgs::srv::SetPTPCommonParams_Event::_info_type arg)
  {
    msg_.info = std::move(arg);
    return Init_SetPTPCommonParams_Event_request(msg_);
  }

private:
  ::dobot_msgs::srv::SetPTPCommonParams_Event msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::SetPTPCommonParams_Event>()
{
  return dobot_msgs::srv::builder::Init_SetPTPCommonParams_Event_info();
}

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__SRV__DETAIL__SET_PTP_COMMON_PARAMS__BUILDER_HPP_
