// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target_array.hpp"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__STRUCT_HPP_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


// Include directives for member types
// Member 'header'
#include "std_msgs/msg/detail/header__struct.hpp"
// Member 'detections'
#include "dobot_msgs/msg/detail/circle_target__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__dobot_msgs__msg__CircleTargetArray __attribute__((deprecated))
#else
# define DEPRECATED__dobot_msgs__msg__CircleTargetArray __declspec(deprecated)
#endif

namespace dobot_msgs
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct CircleTargetArray_
{
  using Type = CircleTargetArray_<ContainerAllocator>;

  explicit CircleTargetArray_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->valid = false;
      this->reason = "";
      std::fill<typename std::array<double, 4>::iterator, double>(this->table_plane.begin(), this->table_plane.end(), 0.0);
      this->table_inlier_ratio = 0.0;
      this->table_rmse = 0.0;
    }
  }

  explicit CircleTargetArray_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : header(_alloc, _init),
    reason(_alloc),
    table_plane(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->valid = false;
      this->reason = "";
      std::fill<typename std::array<double, 4>::iterator, double>(this->table_plane.begin(), this->table_plane.end(), 0.0);
      this->table_inlier_ratio = 0.0;
      this->table_rmse = 0.0;
    }
  }

  // field types and members
  using _header_type =
    std_msgs::msg::Header_<ContainerAllocator>;
  _header_type header;
  using _valid_type =
    bool;
  _valid_type valid;
  using _reason_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _reason_type reason;
  using _table_plane_type =
    std::array<double, 4>;
  _table_plane_type table_plane;
  using _table_inlier_ratio_type =
    double;
  _table_inlier_ratio_type table_inlier_ratio;
  using _table_rmse_type =
    double;
  _table_rmse_type table_rmse;
  using _detections_type =
    std::vector<dobot_msgs::msg::CircleTarget_<ContainerAllocator>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<dobot_msgs::msg::CircleTarget_<ContainerAllocator>>>;
  _detections_type detections;

  // setters for named parameter idiom
  Type & set__header(
    const std_msgs::msg::Header_<ContainerAllocator> & _arg)
  {
    this->header = _arg;
    return *this;
  }
  Type & set__valid(
    const bool & _arg)
  {
    this->valid = _arg;
    return *this;
  }
  Type & set__reason(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->reason = _arg;
    return *this;
  }
  Type & set__table_plane(
    const std::array<double, 4> & _arg)
  {
    this->table_plane = _arg;
    return *this;
  }
  Type & set__table_inlier_ratio(
    const double & _arg)
  {
    this->table_inlier_ratio = _arg;
    return *this;
  }
  Type & set__table_rmse(
    const double & _arg)
  {
    this->table_rmse = _arg;
    return *this;
  }
  Type & set__detections(
    const std::vector<dobot_msgs::msg::CircleTarget_<ContainerAllocator>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<dobot_msgs::msg::CircleTarget_<ContainerAllocator>>> & _arg)
  {
    this->detections = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    dobot_msgs::msg::CircleTargetArray_<ContainerAllocator> *;
  using ConstRawPtr =
    const dobot_msgs::msg::CircleTargetArray_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::msg::CircleTargetArray_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::msg::CircleTargetArray_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__dobot_msgs__msg__CircleTargetArray
    std::shared_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__dobot_msgs__msg__CircleTargetArray
    std::shared_ptr<dobot_msgs::msg::CircleTargetArray_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const CircleTargetArray_ & other) const
  {
    if (this->header != other.header) {
      return false;
    }
    if (this->valid != other.valid) {
      return false;
    }
    if (this->reason != other.reason) {
      return false;
    }
    if (this->table_plane != other.table_plane) {
      return false;
    }
    if (this->table_inlier_ratio != other.table_inlier_ratio) {
      return false;
    }
    if (this->table_rmse != other.table_rmse) {
      return false;
    }
    if (this->detections != other.detections) {
      return false;
    }
    return true;
  }
  bool operator!=(const CircleTargetArray_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct CircleTargetArray_

// alias to use template instance with default allocator
using CircleTargetArray =
  dobot_msgs::msg::CircleTargetArray_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET_ARRAY__STRUCT_HPP_
