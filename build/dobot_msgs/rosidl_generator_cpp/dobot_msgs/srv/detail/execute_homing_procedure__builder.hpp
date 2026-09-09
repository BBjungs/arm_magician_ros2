// generated from rosidl_generator_cpp/resource/idl__builder.hpp.em
// with input from dobot_msgs:srv/ExecuteHomingProcedure.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/execute_homing_procedure.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__EXECUTE_HOMING_PROCEDURE__BUILDER_HPP_
#define DOBOT_MSGS__SRV__DETAIL__EXECUTE_HOMING_PROCEDURE__BUILDER_HPP_

#include <algorithm>
#include <utility>

#include "dobot_msgs/srv/detail/execute_homing_procedure__struct.hpp"
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
auto build<::dobot_msgs::srv::ExecuteHomingProcedure_Request>()
{
  return ::dobot_msgs::srv::ExecuteHomingProcedure_Request(rosidl_runtime_cpp::MessageInitialization::ZERO);
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_ExecuteHomingProcedure_Response_instruction
{
public:
  explicit Init_ExecuteHomingProcedure_Response_instruction(::dobot_msgs::srv::ExecuteHomingProcedure_Response & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::ExecuteHomingProcedure_Response instruction(::dobot_msgs::srv::ExecuteHomingProcedure_Response::_instruction_type arg)
  {
    msg_.instruction = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::ExecuteHomingProcedure_Response msg_;
};

class Init_ExecuteHomingProcedure_Response_success
{
public:
  Init_ExecuteHomingProcedure_Response_success()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_ExecuteHomingProcedure_Response_instruction success(::dobot_msgs::srv::ExecuteHomingProcedure_Response::_success_type arg)
  {
    msg_.success = std::move(arg);
    return Init_ExecuteHomingProcedure_Response_instruction(msg_);
  }

private:
  ::dobot_msgs::srv::ExecuteHomingProcedure_Response msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::ExecuteHomingProcedure_Response>()
{
  return dobot_msgs::srv::builder::Init_ExecuteHomingProcedure_Response_success();
}

}  // namespace dobot_msgs


namespace dobot_msgs
{

namespace srv
{

namespace builder
{

class Init_ExecuteHomingProcedure_Event_response
{
public:
  explicit Init_ExecuteHomingProcedure_Event_response(::dobot_msgs::srv::ExecuteHomingProcedure_Event & msg)
  : msg_(msg)
  {}
  ::dobot_msgs::srv::ExecuteHomingProcedure_Event response(::dobot_msgs::srv::ExecuteHomingProcedure_Event::_response_type arg)
  {
    msg_.response = std::move(arg);
    return std::move(msg_);
  }

private:
  ::dobot_msgs::srv::ExecuteHomingProcedure_Event msg_;
};

class Init_ExecuteHomingProcedure_Event_request
{
public:
  explicit Init_ExecuteHomingProcedure_Event_request(::dobot_msgs::srv::ExecuteHomingProcedure_Event & msg)
  : msg_(msg)
  {}
  Init_ExecuteHomingProcedure_Event_response request(::dobot_msgs::srv::ExecuteHomingProcedure_Event::_request_type arg)
  {
    msg_.request = std::move(arg);
    return Init_ExecuteHomingProcedure_Event_response(msg_);
  }

private:
  ::dobot_msgs::srv::ExecuteHomingProcedure_Event msg_;
};

class Init_ExecuteHomingProcedure_Event_info
{
public:
  Init_ExecuteHomingProcedure_Event_info()
  : msg_(::rosidl_runtime_cpp::MessageInitialization::SKIP)
  {}
  Init_ExecuteHomingProcedure_Event_request info(::dobot_msgs::srv::ExecuteHomingProcedure_Event::_info_type arg)
  {
    msg_.info = std::move(arg);
    return Init_ExecuteHomingProcedure_Event_request(msg_);
  }

private:
  ::dobot_msgs::srv::ExecuteHomingProcedure_Event msg_;
};

}  // namespace builder

}  // namespace srv

template<typename MessageType>
auto build();

template<>
inline
auto build<::dobot_msgs::srv::ExecuteHomingProcedure_Event>()
{
  return dobot_msgs::srv::builder::Init_ExecuteHomingProcedure_Event_info();
}

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__SRV__DETAIL__EXECUTE_HOMING_PROCEDURE__BUILDER_HPP_
