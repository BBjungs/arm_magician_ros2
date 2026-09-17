// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from dobot_msgs:srv/GetPTPCommonParams.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/srv/get_ptp_common_params.hpp"


#ifndef DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__STRUCT_HPP_
#define DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


#ifndef _WIN32
# define DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Request __attribute__((deprecated))
#else
# define DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Request __declspec(deprecated)
#endif

namespace dobot_msgs
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetPTPCommonParams_Request_
{
  using Type = GetPTPCommonParams_Request_<ContainerAllocator>;

  explicit GetPTPCommonParams_Request_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->structure_needs_at_least_one_member = 0;
    }
  }

  explicit GetPTPCommonParams_Request_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    (void)_alloc;
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->structure_needs_at_least_one_member = 0;
    }
  }

  // field types and members
  using _structure_needs_at_least_one_member_type =
    uint8_t;
  _structure_needs_at_least_one_member_type structure_needs_at_least_one_member;


  // constant declarations

  // pointer types
  using RawPtr =
    dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator> *;
  using ConstRawPtr =
    const dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Request
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Request
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetPTPCommonParams_Request_ & other) const
  {
    if (this->structure_needs_at_least_one_member != other.structure_needs_at_least_one_member) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetPTPCommonParams_Request_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetPTPCommonParams_Request_

// alias to use template instance with default allocator
using GetPTPCommonParams_Request =
  dobot_msgs::srv::GetPTPCommonParams_Request_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace dobot_msgs


#ifndef _WIN32
# define DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Response __attribute__((deprecated))
#else
# define DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Response __declspec(deprecated)
#endif

namespace dobot_msgs
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetPTPCommonParams_Response_
{
  using Type = GetPTPCommonParams_Response_<ContainerAllocator>;

  explicit GetPTPCommonParams_Response_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->velocity_percent = 0;
      this->acceleration_percent = 0;
      this->raw_velocity_percent = 0;
      this->raw_acceleration_percent = 0;
      this->timed_out = false;
      this->error = "";
    }
  }

  explicit GetPTPCommonParams_Response_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : error(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->success = false;
      this->velocity_percent = 0;
      this->acceleration_percent = 0;
      this->raw_velocity_percent = 0;
      this->raw_acceleration_percent = 0;
      this->timed_out = false;
      this->error = "";
    }
  }

  // field types and members
  using _success_type =
    bool;
  _success_type success;
  using _velocity_percent_type =
    uint8_t;
  _velocity_percent_type velocity_percent;
  using _acceleration_percent_type =
    uint8_t;
  _acceleration_percent_type acceleration_percent;
  using _raw_velocity_percent_type =
    uint8_t;
  _raw_velocity_percent_type raw_velocity_percent;
  using _raw_acceleration_percent_type =
    uint8_t;
  _raw_acceleration_percent_type raw_acceleration_percent;
  using _timed_out_type =
    bool;
  _timed_out_type timed_out;
  using _error_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _error_type error;

  // setters for named parameter idiom
  Type & set__success(
    const bool & _arg)
  {
    this->success = _arg;
    return *this;
  }
  Type & set__velocity_percent(
    const uint8_t & _arg)
  {
    this->velocity_percent = _arg;
    return *this;
  }
  Type & set__acceleration_percent(
    const uint8_t & _arg)
  {
    this->acceleration_percent = _arg;
    return *this;
  }
  Type & set__raw_velocity_percent(
    const uint8_t & _arg)
  {
    this->raw_velocity_percent = _arg;
    return *this;
  }
  Type & set__raw_acceleration_percent(
    const uint8_t & _arg)
  {
    this->raw_acceleration_percent = _arg;
    return *this;
  }
  Type & set__timed_out(
    const bool & _arg)
  {
    this->timed_out = _arg;
    return *this;
  }
  Type & set__error(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->error = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator> *;
  using ConstRawPtr =
    const dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Response
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Response
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetPTPCommonParams_Response_ & other) const
  {
    if (this->success != other.success) {
      return false;
    }
    if (this->velocity_percent != other.velocity_percent) {
      return false;
    }
    if (this->acceleration_percent != other.acceleration_percent) {
      return false;
    }
    if (this->raw_velocity_percent != other.raw_velocity_percent) {
      return false;
    }
    if (this->raw_acceleration_percent != other.raw_acceleration_percent) {
      return false;
    }
    if (this->timed_out != other.timed_out) {
      return false;
    }
    if (this->error != other.error) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetPTPCommonParams_Response_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetPTPCommonParams_Response_

// alias to use template instance with default allocator
using GetPTPCommonParams_Response =
  dobot_msgs::srv::GetPTPCommonParams_Response_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace dobot_msgs


// Include directives for member types
// Member 'info'
#include "service_msgs/msg/detail/service_event_info__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Event __attribute__((deprecated))
#else
# define DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Event __declspec(deprecated)
#endif

namespace dobot_msgs
{

namespace srv
{

// message struct
template<class ContainerAllocator>
struct GetPTPCommonParams_Event_
{
  using Type = GetPTPCommonParams_Event_<ContainerAllocator>;

  explicit GetPTPCommonParams_Event_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : info(_init)
  {
    (void)_init;
  }

  explicit GetPTPCommonParams_Event_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : info(_alloc, _init)
  {
    (void)_init;
  }

  // field types and members
  using _info_type =
    service_msgs::msg::ServiceEventInfo_<ContainerAllocator>;
  _info_type info;
  using _request_type =
    rosidl_runtime_cpp::BoundedVector<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>>;
  _request_type request;
  using _response_type =
    rosidl_runtime_cpp::BoundedVector<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>>;
  _response_type response;

  // setters for named parameter idiom
  Type & set__info(
    const service_msgs::msg::ServiceEventInfo_<ContainerAllocator> & _arg)
  {
    this->info = _arg;
    return *this;
  }
  Type & set__request(
    const rosidl_runtime_cpp::BoundedVector<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<dobot_msgs::srv::GetPTPCommonParams_Request_<ContainerAllocator>>> & _arg)
  {
    this->request = _arg;
    return *this;
  }
  Type & set__response(
    const rosidl_runtime_cpp::BoundedVector<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>, 1, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<dobot_msgs::srv::GetPTPCommonParams_Response_<ContainerAllocator>>> & _arg)
  {
    this->response = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator> *;
  using ConstRawPtr =
    const dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Event
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__dobot_msgs__srv__GetPTPCommonParams_Event
    std::shared_ptr<dobot_msgs::srv::GetPTPCommonParams_Event_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const GetPTPCommonParams_Event_ & other) const
  {
    if (this->info != other.info) {
      return false;
    }
    if (this->request != other.request) {
      return false;
    }
    if (this->response != other.response) {
      return false;
    }
    return true;
  }
  bool operator!=(const GetPTPCommonParams_Event_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct GetPTPCommonParams_Event_

// alias to use template instance with default allocator
using GetPTPCommonParams_Event =
  dobot_msgs::srv::GetPTPCommonParams_Event_<std::allocator<void>>;

// constant definitions

}  // namespace srv

}  // namespace dobot_msgs

namespace dobot_msgs
{

namespace srv
{

struct GetPTPCommonParams
{
  using Request = dobot_msgs::srv::GetPTPCommonParams_Request;
  using Response = dobot_msgs::srv::GetPTPCommonParams_Response;
  using Event = dobot_msgs::srv::GetPTPCommonParams_Event;
};

}  // namespace srv

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__SRV__DETAIL__GET_PTP_COMMON_PARAMS__STRUCT_HPP_
