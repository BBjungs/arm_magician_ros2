// generated from rosidl_generator_cpp/resource/idl__struct.hpp.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "dobot_msgs/msg/circle_target.hpp"


#ifndef DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__STRUCT_HPP_
#define DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__STRUCT_HPP_

#include <algorithm>
#include <array>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#include "rosidl_runtime_cpp/bounded_vector.hpp"
#include "rosidl_runtime_cpp/message_initialization.hpp"


// Include directives for member types
// Member 'camera_xyz'
#include "geometry_msgs/msg/detail/point__struct.hpp"

#ifndef _WIN32
# define DEPRECATED__dobot_msgs__msg__CircleTarget __attribute__((deprecated))
#else
# define DEPRECATED__dobot_msgs__msg__CircleTarget __declspec(deprecated)
#endif

namespace dobot_msgs
{

namespace msg
{

// message struct
template<class ContainerAllocator>
struct CircleTarget_
{
  using Type = CircleTarget_<ContainerAllocator>;

  explicit CircleTarget_(rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : camera_xyz(_init)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->id = 0ul;
      this->class_name = "";
      std::fill<typename std::array<double, 2>::iterator, double>(this->center_uv.begin(), this->center_uv.end(), 0.0);
      this->depth = 0.0;
      this->size = 0.0;
      this->confidence = 0.0;
      this->pickable = false;
      this->top_height = 0.0;
      this->depth_valid_ratio = 0.0;
      this->depth_mad = 0.0;
      this->rejection_reason = "";
    }
  }

  explicit CircleTarget_(const ContainerAllocator & _alloc, rosidl_runtime_cpp::MessageInitialization _init = rosidl_runtime_cpp::MessageInitialization::ALL)
  : class_name(_alloc),
    center_uv(_alloc),
    camera_xyz(_alloc, _init),
    rejection_reason(_alloc)
  {
    if (rosidl_runtime_cpp::MessageInitialization::ALL == _init ||
      rosidl_runtime_cpp::MessageInitialization::ZERO == _init)
    {
      this->id = 0ul;
      this->class_name = "";
      std::fill<typename std::array<double, 2>::iterator, double>(this->center_uv.begin(), this->center_uv.end(), 0.0);
      this->depth = 0.0;
      this->size = 0.0;
      this->confidence = 0.0;
      this->pickable = false;
      this->top_height = 0.0;
      this->depth_valid_ratio = 0.0;
      this->depth_mad = 0.0;
      this->rejection_reason = "";
    }
  }

  // field types and members
  using _id_type =
    uint32_t;
  _id_type id;
  using _class_name_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _class_name_type class_name;
  using _center_uv_type =
    std::array<double, 2>;
  _center_uv_type center_uv;
  using _camera_xyz_type =
    geometry_msgs::msg::Point_<ContainerAllocator>;
  _camera_xyz_type camera_xyz;
  using _depth_type =
    double;
  _depth_type depth;
  using _size_type =
    double;
  _size_type size;
  using _confidence_type =
    double;
  _confidence_type confidence;
  using _pickable_type =
    bool;
  _pickable_type pickable;
  using _top_height_type =
    double;
  _top_height_type top_height;
  using _depth_valid_ratio_type =
    double;
  _depth_valid_ratio_type depth_valid_ratio;
  using _depth_mad_type =
    double;
  _depth_mad_type depth_mad;
  using _rejection_reason_type =
    std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>>;
  _rejection_reason_type rejection_reason;

  // setters for named parameter idiom
  Type & set__id(
    const uint32_t & _arg)
  {
    this->id = _arg;
    return *this;
  }
  Type & set__class_name(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->class_name = _arg;
    return *this;
  }
  Type & set__center_uv(
    const std::array<double, 2> & _arg)
  {
    this->center_uv = _arg;
    return *this;
  }
  Type & set__camera_xyz(
    const geometry_msgs::msg::Point_<ContainerAllocator> & _arg)
  {
    this->camera_xyz = _arg;
    return *this;
  }
  Type & set__depth(
    const double & _arg)
  {
    this->depth = _arg;
    return *this;
  }
  Type & set__size(
    const double & _arg)
  {
    this->size = _arg;
    return *this;
  }
  Type & set__confidence(
    const double & _arg)
  {
    this->confidence = _arg;
    return *this;
  }
  Type & set__pickable(
    const bool & _arg)
  {
    this->pickable = _arg;
    return *this;
  }
  Type & set__top_height(
    const double & _arg)
  {
    this->top_height = _arg;
    return *this;
  }
  Type & set__depth_valid_ratio(
    const double & _arg)
  {
    this->depth_valid_ratio = _arg;
    return *this;
  }
  Type & set__depth_mad(
    const double & _arg)
  {
    this->depth_mad = _arg;
    return *this;
  }
  Type & set__rejection_reason(
    const std::basic_string<char, std::char_traits<char>, typename std::allocator_traits<ContainerAllocator>::template rebind_alloc<char>> & _arg)
  {
    this->rejection_reason = _arg;
    return *this;
  }

  // constant declarations

  // pointer types
  using RawPtr =
    dobot_msgs::msg::CircleTarget_<ContainerAllocator> *;
  using ConstRawPtr =
    const dobot_msgs::msg::CircleTarget_<ContainerAllocator> *;
  using SharedPtr =
    std::shared_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator>>;
  using ConstSharedPtr =
    std::shared_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator> const>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::msg::CircleTarget_<ContainerAllocator>>>
  using UniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator>, Deleter>;

  using UniquePtr = UniquePtrWithDeleter<>;

  template<typename Deleter = std::default_delete<
      dobot_msgs::msg::CircleTarget_<ContainerAllocator>>>
  using ConstUniquePtrWithDeleter =
    std::unique_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator> const, Deleter>;
  using ConstUniquePtr = ConstUniquePtrWithDeleter<>;

  using WeakPtr =
    std::weak_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator>>;
  using ConstWeakPtr =
    std::weak_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator> const>;

  // pointer types similar to ROS 1, use SharedPtr / ConstSharedPtr instead
  // NOTE: Can't use 'using' here because GNU C++ can't parse attributes properly
  typedef DEPRECATED__dobot_msgs__msg__CircleTarget
    std::shared_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator>>
    Ptr;
  typedef DEPRECATED__dobot_msgs__msg__CircleTarget
    std::shared_ptr<dobot_msgs::msg::CircleTarget_<ContainerAllocator> const>
    ConstPtr;

  // comparison operators
  bool operator==(const CircleTarget_ & other) const
  {
    if (this->id != other.id) {
      return false;
    }
    if (this->class_name != other.class_name) {
      return false;
    }
    if (this->center_uv != other.center_uv) {
      return false;
    }
    if (this->camera_xyz != other.camera_xyz) {
      return false;
    }
    if (this->depth != other.depth) {
      return false;
    }
    if (this->size != other.size) {
      return false;
    }
    if (this->confidence != other.confidence) {
      return false;
    }
    if (this->pickable != other.pickable) {
      return false;
    }
    if (this->top_height != other.top_height) {
      return false;
    }
    if (this->depth_valid_ratio != other.depth_valid_ratio) {
      return false;
    }
    if (this->depth_mad != other.depth_mad) {
      return false;
    }
    if (this->rejection_reason != other.rejection_reason) {
      return false;
    }
    return true;
  }
  bool operator!=(const CircleTarget_ & other) const
  {
    return !this->operator==(other);
  }
};  // struct CircleTarget_

// alias to use template instance with default allocator
using CircleTarget =
  dobot_msgs::msg::CircleTarget_<std::allocator<void>>;

// constant definitions

}  // namespace msg

}  // namespace dobot_msgs

#endif  // DOBOT_MSGS__MSG__DETAIL__CIRCLE_TARGET__STRUCT_HPP_
