// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice
#include "dobot_msgs/msg/detail/circle_target__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `class_name`
// Member `rejection_reason`
#include "rosidl_runtime_c/string_functions.h"
// Member `camera_xyz`
#include "geometry_msgs/msg/detail/point__functions.h"

bool
dobot_msgs__msg__CircleTarget__init(dobot_msgs__msg__CircleTarget * msg)
{
  if (!msg) {
    return false;
  }
  // id
  // class_name
  if (!rosidl_runtime_c__String__init(&msg->class_name)) {
    dobot_msgs__msg__CircleTarget__fini(msg);
    return false;
  }
  // center_uv
  // camera_xyz
  if (!geometry_msgs__msg__Point__init(&msg->camera_xyz)) {
    dobot_msgs__msg__CircleTarget__fini(msg);
    return false;
  }
  // depth
  // size
  // confidence
  // pickable
  // top_height
  // depth_valid_ratio
  // depth_mad
  // rejection_reason
  if (!rosidl_runtime_c__String__init(&msg->rejection_reason)) {
    dobot_msgs__msg__CircleTarget__fini(msg);
    return false;
  }
  return true;
}

void
dobot_msgs__msg__CircleTarget__fini(dobot_msgs__msg__CircleTarget * msg)
{
  if (!msg) {
    return;
  }
  // id
  // class_name
  rosidl_runtime_c__String__fini(&msg->class_name);
  // center_uv
  // camera_xyz
  geometry_msgs__msg__Point__fini(&msg->camera_xyz);
  // depth
  // size
  // confidence
  // pickable
  // top_height
  // depth_valid_ratio
  // depth_mad
  // rejection_reason
  rosidl_runtime_c__String__fini(&msg->rejection_reason);
}

bool
dobot_msgs__msg__CircleTarget__are_equal(const dobot_msgs__msg__CircleTarget * lhs, const dobot_msgs__msg__CircleTarget * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // id
  if (lhs->id != rhs->id) {
    return false;
  }
  // class_name
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->class_name), &(rhs->class_name)))
  {
    return false;
  }
  // center_uv
  for (size_t i = 0; i < 2; ++i) {
    if (lhs->center_uv[i] != rhs->center_uv[i]) {
      return false;
    }
  }
  // camera_xyz
  if (!geometry_msgs__msg__Point__are_equal(
      &(lhs->camera_xyz), &(rhs->camera_xyz)))
  {
    return false;
  }
  // depth
  if (lhs->depth != rhs->depth) {
    return false;
  }
  // size
  if (lhs->size != rhs->size) {
    return false;
  }
  // confidence
  if (lhs->confidence != rhs->confidence) {
    return false;
  }
  // pickable
  if (lhs->pickable != rhs->pickable) {
    return false;
  }
  // top_height
  if (lhs->top_height != rhs->top_height) {
    return false;
  }
  // depth_valid_ratio
  if (lhs->depth_valid_ratio != rhs->depth_valid_ratio) {
    return false;
  }
  // depth_mad
  if (lhs->depth_mad != rhs->depth_mad) {
    return false;
  }
  // rejection_reason
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->rejection_reason), &(rhs->rejection_reason)))
  {
    return false;
  }
  return true;
}

bool
dobot_msgs__msg__CircleTarget__copy(
  const dobot_msgs__msg__CircleTarget * input,
  dobot_msgs__msg__CircleTarget * output)
{
  if (!input || !output) {
    return false;
  }
  // id
  output->id = input->id;
  // class_name
  if (!rosidl_runtime_c__String__copy(
      &(input->class_name), &(output->class_name)))
  {
    return false;
  }
  // center_uv
  for (size_t i = 0; i < 2; ++i) {
    output->center_uv[i] = input->center_uv[i];
  }
  // camera_xyz
  if (!geometry_msgs__msg__Point__copy(
      &(input->camera_xyz), &(output->camera_xyz)))
  {
    return false;
  }
  // depth
  output->depth = input->depth;
  // size
  output->size = input->size;
  // confidence
  output->confidence = input->confidence;
  // pickable
  output->pickable = input->pickable;
  // top_height
  output->top_height = input->top_height;
  // depth_valid_ratio
  output->depth_valid_ratio = input->depth_valid_ratio;
  // depth_mad
  output->depth_mad = input->depth_mad;
  // rejection_reason
  if (!rosidl_runtime_c__String__copy(
      &(input->rejection_reason), &(output->rejection_reason)))
  {
    return false;
  }
  return true;
}

dobot_msgs__msg__CircleTarget *
dobot_msgs__msg__CircleTarget__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__msg__CircleTarget * msg = (dobot_msgs__msg__CircleTarget *)allocator.allocate(sizeof(dobot_msgs__msg__CircleTarget), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(dobot_msgs__msg__CircleTarget));
  bool success = dobot_msgs__msg__CircleTarget__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
dobot_msgs__msg__CircleTarget__destroy(dobot_msgs__msg__CircleTarget * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    dobot_msgs__msg__CircleTarget__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
dobot_msgs__msg__CircleTarget__Sequence__init(dobot_msgs__msg__CircleTarget__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__msg__CircleTarget * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(dobot_msgs__msg__CircleTarget)) {
      return false;
    }
    data = (dobot_msgs__msg__CircleTarget *)allocator.zero_allocate(size, sizeof(dobot_msgs__msg__CircleTarget), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = dobot_msgs__msg__CircleTarget__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        dobot_msgs__msg__CircleTarget__fini(&data[i - 1]);
      }
      allocator.deallocate(data, allocator.state);
      return false;
    }
  }
  array->data = data;
  array->size = size;
  array->capacity = size;
  return true;
}

void
dobot_msgs__msg__CircleTarget__Sequence__fini(dobot_msgs__msg__CircleTarget__Sequence * array)
{
  if (!array) {
    return;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();

  if (array->data) {
    // ensure that data and capacity values are consistent
    assert(array->capacity > 0);
    // finalize all array elements
    for (size_t i = 0; i < array->capacity; ++i) {
      dobot_msgs__msg__CircleTarget__fini(&array->data[i]);
    }
    allocator.deallocate(array->data, allocator.state);
    array->data = NULL;
    array->size = 0;
    array->capacity = 0;
  } else {
    // ensure that data, size, and capacity values are consistent
    assert(0 == array->size);
    assert(0 == array->capacity);
  }
}

dobot_msgs__msg__CircleTarget__Sequence *
dobot_msgs__msg__CircleTarget__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__msg__CircleTarget__Sequence * array = (dobot_msgs__msg__CircleTarget__Sequence *)allocator.allocate(sizeof(dobot_msgs__msg__CircleTarget__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = dobot_msgs__msg__CircleTarget__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
dobot_msgs__msg__CircleTarget__Sequence__destroy(dobot_msgs__msg__CircleTarget__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    dobot_msgs__msg__CircleTarget__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
dobot_msgs__msg__CircleTarget__Sequence__are_equal(const dobot_msgs__msg__CircleTarget__Sequence * lhs, const dobot_msgs__msg__CircleTarget__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!dobot_msgs__msg__CircleTarget__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
dobot_msgs__msg__CircleTarget__Sequence__copy(
  const dobot_msgs__msg__CircleTarget__Sequence * input,
  dobot_msgs__msg__CircleTarget__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(dobot_msgs__msg__CircleTarget)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(dobot_msgs__msg__CircleTarget);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    dobot_msgs__msg__CircleTarget * data =
      (dobot_msgs__msg__CircleTarget *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!dobot_msgs__msg__CircleTarget__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          dobot_msgs__msg__CircleTarget__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!dobot_msgs__msg__CircleTarget__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
