// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice
#include "dobot_msgs/msg/detail/circle_target_array__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"


// Include directives for member types
// Member `header`
#include "std_msgs/msg/detail/header__functions.h"
// Member `reason`
#include "rosidl_runtime_c/string_functions.h"
// Member `detections`
#include "dobot_msgs/msg/detail/circle_target__functions.h"

bool
dobot_msgs__msg__CircleTargetArray__init(dobot_msgs__msg__CircleTargetArray * msg)
{
  if (!msg) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__init(&msg->header)) {
    dobot_msgs__msg__CircleTargetArray__fini(msg);
    return false;
  }
  // valid
  // reason
  if (!rosidl_runtime_c__String__init(&msg->reason)) {
    dobot_msgs__msg__CircleTargetArray__fini(msg);
    return false;
  }
  // table_plane
  // table_inlier_ratio
  // table_rmse
  // detections
  if (!dobot_msgs__msg__CircleTarget__Sequence__init(&msg->detections, 0)) {
    dobot_msgs__msg__CircleTargetArray__fini(msg);
    return false;
  }
  return true;
}

void
dobot_msgs__msg__CircleTargetArray__fini(dobot_msgs__msg__CircleTargetArray * msg)
{
  if (!msg) {
    return;
  }
  // header
  std_msgs__msg__Header__fini(&msg->header);
  // valid
  // reason
  rosidl_runtime_c__String__fini(&msg->reason);
  // table_plane
  // table_inlier_ratio
  // table_rmse
  // detections
  dobot_msgs__msg__CircleTarget__Sequence__fini(&msg->detections);
}

bool
dobot_msgs__msg__CircleTargetArray__are_equal(const dobot_msgs__msg__CircleTargetArray * lhs, const dobot_msgs__msg__CircleTargetArray * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__are_equal(
      &(lhs->header), &(rhs->header)))
  {
    return false;
  }
  // valid
  if (lhs->valid != rhs->valid) {
    return false;
  }
  // reason
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->reason), &(rhs->reason)))
  {
    return false;
  }
  // table_plane
  for (size_t i = 0; i < 4; ++i) {
    if (lhs->table_plane[i] != rhs->table_plane[i]) {
      return false;
    }
  }
  // table_inlier_ratio
  if (lhs->table_inlier_ratio != rhs->table_inlier_ratio) {
    return false;
  }
  // table_rmse
  if (lhs->table_rmse != rhs->table_rmse) {
    return false;
  }
  // detections
  if (!dobot_msgs__msg__CircleTarget__Sequence__are_equal(
      &(lhs->detections), &(rhs->detections)))
  {
    return false;
  }
  return true;
}

bool
dobot_msgs__msg__CircleTargetArray__copy(
  const dobot_msgs__msg__CircleTargetArray * input,
  dobot_msgs__msg__CircleTargetArray * output)
{
  if (!input || !output) {
    return false;
  }
  // header
  if (!std_msgs__msg__Header__copy(
      &(input->header), &(output->header)))
  {
    return false;
  }
  // valid
  output->valid = input->valid;
  // reason
  if (!rosidl_runtime_c__String__copy(
      &(input->reason), &(output->reason)))
  {
    return false;
  }
  // table_plane
  for (size_t i = 0; i < 4; ++i) {
    output->table_plane[i] = input->table_plane[i];
  }
  // table_inlier_ratio
  output->table_inlier_ratio = input->table_inlier_ratio;
  // table_rmse
  output->table_rmse = input->table_rmse;
  // detections
  if (!dobot_msgs__msg__CircleTarget__Sequence__copy(
      &(input->detections), &(output->detections)))
  {
    return false;
  }
  return true;
}

dobot_msgs__msg__CircleTargetArray *
dobot_msgs__msg__CircleTargetArray__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__msg__CircleTargetArray * msg = (dobot_msgs__msg__CircleTargetArray *)allocator.allocate(sizeof(dobot_msgs__msg__CircleTargetArray), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(dobot_msgs__msg__CircleTargetArray));
  bool success = dobot_msgs__msg__CircleTargetArray__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
dobot_msgs__msg__CircleTargetArray__destroy(dobot_msgs__msg__CircleTargetArray * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    dobot_msgs__msg__CircleTargetArray__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
dobot_msgs__msg__CircleTargetArray__Sequence__init(dobot_msgs__msg__CircleTargetArray__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__msg__CircleTargetArray * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(dobot_msgs__msg__CircleTargetArray)) {
      return false;
    }
    data = (dobot_msgs__msg__CircleTargetArray *)allocator.zero_allocate(size, sizeof(dobot_msgs__msg__CircleTargetArray), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = dobot_msgs__msg__CircleTargetArray__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        dobot_msgs__msg__CircleTargetArray__fini(&data[i - 1]);
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
dobot_msgs__msg__CircleTargetArray__Sequence__fini(dobot_msgs__msg__CircleTargetArray__Sequence * array)
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
      dobot_msgs__msg__CircleTargetArray__fini(&array->data[i]);
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

dobot_msgs__msg__CircleTargetArray__Sequence *
dobot_msgs__msg__CircleTargetArray__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__msg__CircleTargetArray__Sequence * array = (dobot_msgs__msg__CircleTargetArray__Sequence *)allocator.allocate(sizeof(dobot_msgs__msg__CircleTargetArray__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = dobot_msgs__msg__CircleTargetArray__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
dobot_msgs__msg__CircleTargetArray__Sequence__destroy(dobot_msgs__msg__CircleTargetArray__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    dobot_msgs__msg__CircleTargetArray__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
dobot_msgs__msg__CircleTargetArray__Sequence__are_equal(const dobot_msgs__msg__CircleTargetArray__Sequence * lhs, const dobot_msgs__msg__CircleTargetArray__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!dobot_msgs__msg__CircleTargetArray__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
dobot_msgs__msg__CircleTargetArray__Sequence__copy(
  const dobot_msgs__msg__CircleTargetArray__Sequence * input,
  dobot_msgs__msg__CircleTargetArray__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(dobot_msgs__msg__CircleTargetArray)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(dobot_msgs__msg__CircleTargetArray);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    dobot_msgs__msg__CircleTargetArray * data =
      (dobot_msgs__msg__CircleTargetArray *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!dobot_msgs__msg__CircleTargetArray__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          dobot_msgs__msg__CircleTargetArray__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!dobot_msgs__msg__CircleTargetArray__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
