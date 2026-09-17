// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from dobot_msgs:srv/StartSmokeTest.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/start_smoke_test.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__START_SMOKE_TEST__BUILDER_HPP_
#define DOBOT_MSGS__SRV__DETAIL__START_SMOKE_TEST__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "dobot_msgs/srv/detail/start_smoke_test__struct.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_StartSmokeTest_Request_operator_confirmed
{
public:
  Init_StartSmokeTest_Request_operator_confirmed()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  ::dobot_msgs::srv::StartSmokeTest_Request operator_confirmed(::dobot_msgs::srv::StartSmokeTest_Request::_operator_confirmed_type arg)
  {
    msg_.operator_confirmed = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::StartSmokeTest_Request msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::StartSmokeTest_Request>()
{
  return dobot_msgs::srv::builder::Init_StartSmokeTest_Request_operator_confirmed();
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_StartSmokeTest_Response_report
{
public:
  explicit Init_StartSmokeTest_Response_report(::dobot_msgs::srv::StartSmokeTest_Response & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::StartSmokeTest_Response report(::dobot_msgs::srv::StartSmokeTest_Response::_report_type arg)
  {
    msg_.report = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::StartSmokeTest_Response msg_;
};

class Init_StartSmokeTest_Response_accepted
{
public:
  Init_StartSmokeTest_Response_accepted()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_StartSmokeTest_Response_report accepted(::dobot_msgs::srv::StartSmokeTest_Response::_accepted_type arg)
  {
    msg_.accepted = std::move(arg);
    return Init_StartSmokeTest_Response_report(msg_);
  }

private:
  ::dobot_msgs::srv::StartSmokeTest_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::StartSmokeTest_Response>()
{
  return dobot_msgs::srv::builder::Init_StartSmokeTest_Response_accepted();
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_StartSmokeTest_Event_response
{
public:
  explicit Init_StartSmokeTest_Event_response(::dobot_msgs::srv::StartSmokeTest_Event & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::StartSmokeTest_Event response(::dobot_msgs::srv::StartSmokeTest_Event::_response_type arg)
  {
    msg_.response = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::StartSmokeTest_Event msg_;
};

class Init_StartSmokeTest_Event_request
{
public:
  explicit Init_StartSmokeTest_Event_request(::dobot_msgs::srv::StartSmokeTest_Event & msg)
  : msg_(msg)
  {}
  Init_StartSmokeTest_Event_response request(::dobot_msgs::srv::StartSmokeTest_Event::_request_type arg)
  {
    msg_.request = std::move(arg);
    return Init_StartSmokeTest_Event_response(msg_);
  }

private:
  ::dobot_msgs::srv::StartSmokeTest_Event msg_;
};

class Init_StartSmokeTest_Event_info
{
public:
  Init_StartSmokeTest_Event_info()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_StartSmokeTest_Event_request info(::dobot_msgs::srv::StartSmokeTest_Event::_info_type arg)
  {
    msg_.info = std::move(arg);
    return Init_StartSmokeTest_Event_request(msg_);
  }

private:
  ::dobot_msgs::srv::StartSmokeTest_Event msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::StartSmokeTest_Event>()
{
  return dobot_msgs::srv::builder::Init_StartSmokeTest_Event_info();
}

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__SRV__DETAIL__START_SMOKE_TEST__BUILDER_HPP_
