// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from dobot_msgs:srv/GetPTPCommonParams.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/get_ptp_common_params.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__BUILDER_HPP_
#define DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "dobot_msgs/srv/detail/get_ptp_common_params__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace dobot_msgs
{

namespace srv
{


}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::GetPTPCommonParams_Request>()
{
  return ::dobot_msgs::srv::GetPTPCommonParams_Request(rosidl_runtime_cpp::MessageInitialization::ZERO);
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_GetPTPCommonParams_Response_error
{
public:
  explicit Init_GetPTPCommonParams_Response_error(::dobot_msgs::srv::GetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::GetPTPCommonParams_Response error(::dobot_msgs::srv::GetPTPCommonParams_Response::_error_type arg)
  {
    msg_.error = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

class Init_GetPTPCommonParams_Response_timed_out
{
public:
  explicit Init_GetPTPCommonParams_Response_timed_out(::dobot_msgs::srv::GetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_GetPTPCommonParams_Response_error timed_out(::dobot_msgs::srv::GetPTPCommonParams_Response::_timed_out_type arg)
  {
    msg_.timed_out = std::move(arg);
    return Init_GetPTPCommonParams_Response_error(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

class Init_GetPTPCommonParams_Response_raw_acceleration_percent
{
public:
  explicit Init_GetPTPCommonParams_Response_raw_acceleration_percent(::dobot_msgs::srv::GetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_GetPTPCommonParams_Response_timed_out raw_acceleration_percent(::dobot_msgs::srv::GetPTPCommonParams_Response::_raw_acceleration_percent_type arg)
  {
    msg_.raw_acceleration_percent = std::move(arg);
    return Init_GetPTPCommonParams_Response_timed_out(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

class Init_GetPTPCommonParams_Response_raw_velocity_percent
{
public:
  explicit Init_GetPTPCommonParams_Response_raw_velocity_percent(::dobot_msgs::srv::GetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_GetPTPCommonParams_Response_raw_acceleration_percent raw_velocity_percent(::dobot_msgs::srv::GetPTPCommonParams_Response::_raw_velocity_percent_type arg)
  {
    msg_.raw_velocity_percent = std::move(arg);
    return Init_GetPTPCommonParams_Response_raw_acceleration_percent(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

class Init_GetPTPCommonParams_Response_acceleration_percent
{
public:
  explicit Init_GetPTPCommonParams_Response_acceleration_percent(::dobot_msgs::srv::GetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_GetPTPCommonParams_Response_raw_velocity_percent acceleration_percent(::dobot_msgs::srv::GetPTPCommonParams_Response::_acceleration_percent_type arg)
  {
    msg_.acceleration_percent = std::move(arg);
    return Init_GetPTPCommonParams_Response_raw_velocity_percent(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

class Init_GetPTPCommonParams_Response_velocity_percent
{
public:
  explicit Init_GetPTPCommonParams_Response_velocity_percent(::dobot_msgs::srv::GetPTPCommonParams_Response & msg)
  : msg_(msg)
  {}
  Init_GetPTPCommonParams_Response_acceleration_percent velocity_percent(::dobot_msgs::srv::GetPTPCommonParams_Response::_velocity_percent_type arg)
  {
    msg_.velocity_percent = std::move(arg);
    return Init_GetPTPCommonParams_Response_acceleration_percent(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

class Init_GetPTPCommonParams_Response_success
{
public:
  Init_GetPTPCommonParams_Response_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_GetPTPCommonParams_Response_velocity_percent success(::dobot_msgs::srv::GetPTPCommonParams_Response::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_GetPTPCommonParams_Response_velocity_percent(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::GetPTPCommonParams_Response>()
{
  return dobot_msgs::srv::builder::Init_GetPTPCommonParams_Response_success();
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_GetPTPCommonParams_Event_response
{
public:
  explicit Init_GetPTPCommonParams_Event_response(::dobot_msgs::srv::GetPTPCommonParams_Event & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::GetPTPCommonParams_Event response(::dobot_msgs::srv::GetPTPCommonParams_Event::_response_type arg)
  {
    msg_.response = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Event msg_;
};

class Init_GetPTPCommonParams_Event_request
{
public:
  explicit Init_GetPTPCommonParams_Event_request(::dobot_msgs::srv::GetPTPCommonParams_Event & msg)
  : msg_(msg)
  {}
  Init_GetPTPCommonParams_Event_response request(::dobot_msgs::srv::GetPTPCommonParams_Event::_request_type arg)
  {
    msg_.request = std::move(arg);
    return Init_GetPTPCommonParams_Event_response(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Event msg_;
};

class Init_GetPTPCommonParams_Event_info
{
public:
  Init_GetPTPCommonParams_Event_info()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_GetPTPCommonParams_Event_request info(::dobot_msgs::srv::GetPTPCommonParams_Event::_info_type arg)
  {
    msg_.info = std::move(arg);
    return Init_GetPTPCommonParams_Event_request(msg_);
  }

private:
  ::dobot_msgs::srv::GetPTPCommonParams_Event msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::GetPTPCommonParams_Event>()
{
  return dobot_msgs::srv::builder::Init_GetPTPCommonParams_Event_info();
}

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__BUILDER_HPP_
