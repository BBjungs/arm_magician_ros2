// generated from rosidl_generator_c/resource/idl__functions.c.em
// with input from dobot_msgs:srv/GripperControl.idl
// generated code does not contain a copyright notice
#include "dobot_msgs/srv/detail/gripper_control__functions.h"

#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>

#include "rcutils/allocator.h"

// Include directives for member types
// Member `gripper_state`
#include "rosidl_runtime_c/string_functions.h"

bool
dobot_msgs__srv__GripperControl_Request__init(dobot_msgs__srv__GripperControl_Request * msg)
{
  if (!msg) {
    return false;
  }
  // gripper_state
  if (!rosidl_runtime_c__String__init(&msg->gripper_state)) {
    dobot_msgs__srv__GripperControl_Request__fini(msg);
    return false;
  }
  // keep_compressor_running
  return true;
}

void
dobot_msgs__srv__GripperControl_Request__fini(dobot_msgs__srv__GripperControl_Request * msg)
{
  if (!msg) {
    return;
  }
  // gripper_state
  rosidl_runtime_c__String__fini(&msg->gripper_state);
  // keep_compressor_running
}

bool
dobot_msgs__srv__GripperControl_Request__are_equal(const dobot_msgs__srv__GripperControl_Request * lhs, const dobot_msgs__srv__GripperControl_Request * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // gripper_state
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->gripper_state), &(rhs->gripper_state)))
  {
    return false;
  }
  // keep_compressor_running
  if (lhs->keep_compressor_running != rhs->keep_compressor_running) {
    return false;
  }
  return true;
}

bool
dobot_msgs__srv__GripperControl_Request__copy(
  const dobot_msgs__srv__GripperControl_Request * input,
  dobot_msgs__srv__GripperControl_Request * output)
{
  if (!input || !output) {
    return false;
  }
  // gripper_state
  if (!rosidl_runtime_c__String__copy(
      &(input->gripper_state), &(output->gripper_state)))
  {
    return false;
  }
  // keep_compressor_running
  output->keep_compressor_running = input->keep_compressor_running;
  return true;
}

dobot_msgs__srv__GripperControl_Request *
dobot_msgs__srv__GripperControl_Request__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Request * msg = (dobot_msgs__srv__GripperControl_Request *)allocator.allocate(sizeof(dobot_msgs__srv__GripperControl_Request), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(dobot_msgs__srv__GripperControl_Request));
  bool success = dobot_msgs__srv__GripperControl_Request__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
dobot_msgs__srv__GripperControl_Request__destroy(dobot_msgs__srv__GripperControl_Request * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    dobot_msgs__srv__GripperControl_Request__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
dobot_msgs__srv__GripperControl_Request__Sequence__init(dobot_msgs__srv__GripperControl_Request__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Request * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(dobot_msgs__srv__GripperControl_Request)) {
      return false;
    }
    data = (dobot_msgs__srv__GripperControl_Request *)allocator.zero_allocate(size, sizeof(dobot_msgs__srv__GripperControl_Request), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = dobot_msgs__srv__GripperControl_Request__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        dobot_msgs__srv__GripperControl_Request__fini(&data[i - 1]);
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
dobot_msgs__srv__GripperControl_Request__Sequence__fini(dobot_msgs__srv__GripperControl_Request__Sequence * array)
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
      dobot_msgs__srv__GripperControl_Request__fini(&array->data[i]);
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

dobot_msgs__srv__GripperControl_Request__Sequence *
dobot_msgs__srv__GripperControl_Request__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Request__Sequence * array = (dobot_msgs__srv__GripperControl_Request__Sequence *)allocator.allocate(sizeof(dobot_msgs__srv__GripperControl_Request__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = dobot_msgs__srv__GripperControl_Request__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
dobot_msgs__srv__GripperControl_Request__Sequence__destroy(dobot_msgs__srv__GripperControl_Request__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    dobot_msgs__srv__GripperControl_Request__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
dobot_msgs__srv__GripperControl_Request__Sequence__are_equal(const dobot_msgs__srv__GripperControl_Request__Sequence * lhs, const dobot_msgs__srv__GripperControl_Request__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!dobot_msgs__srv__GripperControl_Request__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
dobot_msgs__srv__GripperControl_Request__Sequence__copy(
  const dobot_msgs__srv__GripperControl_Request__Sequence * input,
  dobot_msgs__srv__GripperControl_Request__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(dobot_msgs__srv__GripperControl_Request)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(dobot_msgs__srv__GripperControl_Request);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    dobot_msgs__srv__GripperControl_Request * data =
      (dobot_msgs__srv__GripperControl_Request *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!dobot_msgs__srv__GripperControl_Request__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          dobot_msgs__srv__GripperControl_Request__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!dobot_msgs__srv__GripperControl_Request__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `message`
// already included above
// #include "rosidl_runtime_c/string_functions.h"

bool
dobot_msgs__srv__GripperControl_Response__init(dobot_msgs__srv__GripperControl_Response * msg)
{
  if (!msg) {
    return false;
  }
  // success
  // message
  if (!rosidl_runtime_c__String__init(&msg->message)) {
    dobot_msgs__srv__GripperControl_Response__fini(msg);
    return false;
  }
  return true;
}

void
dobot_msgs__srv__GripperControl_Response__fini(dobot_msgs__srv__GripperControl_Response * msg)
{
  if (!msg) {
    return;
  }
  // success
  // message
  rosidl_runtime_c__String__fini(&msg->message);
}

bool
dobot_msgs__srv__GripperControl_Response__are_equal(const dobot_msgs__srv__GripperControl_Response * lhs, const dobot_msgs__srv__GripperControl_Response * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // success
  if (lhs->success != rhs->success) {
    return false;
  }
  // message
  if (!rosidl_runtime_c__String__are_equal(
      &(lhs->message), &(rhs->message)))
  {
    return false;
  }
  return true;
}

bool
dobot_msgs__srv__GripperControl_Response__copy(
  const dobot_msgs__srv__GripperControl_Response * input,
  dobot_msgs__srv__GripperControl_Response * output)
{
  if (!input || !output) {
    return false;
  }
  // success
  output->success = input->success;
  // message
  if (!rosidl_runtime_c__String__copy(
      &(input->message), &(output->message)))
  {
    return false;
  }
  return true;
}

dobot_msgs__srv__GripperControl_Response *
dobot_msgs__srv__GripperControl_Response__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Response * msg = (dobot_msgs__srv__GripperControl_Response *)allocator.allocate(sizeof(dobot_msgs__srv__GripperControl_Response), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(dobot_msgs__srv__GripperControl_Response));
  bool success = dobot_msgs__srv__GripperControl_Response__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
dobot_msgs__srv__GripperControl_Response__destroy(dobot_msgs__srv__GripperControl_Response * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    dobot_msgs__srv__GripperControl_Response__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
dobot_msgs__srv__GripperControl_Response__Sequence__init(dobot_msgs__srv__GripperControl_Response__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Response * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(dobot_msgs__srv__GripperControl_Response)) {
      return false;
    }
    data = (dobot_msgs__srv__GripperControl_Response *)allocator.zero_allocate(size, sizeof(dobot_msgs__srv__GripperControl_Response), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = dobot_msgs__srv__GripperControl_Response__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        dobot_msgs__srv__GripperControl_Response__fini(&data[i - 1]);
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
dobot_msgs__srv__GripperControl_Response__Sequence__fini(dobot_msgs__srv__GripperControl_Response__Sequence * array)
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
      dobot_msgs__srv__GripperControl_Response__fini(&array->data[i]);
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

dobot_msgs__srv__GripperControl_Response__Sequence *
dobot_msgs__srv__GripperControl_Response__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Response__Sequence * array = (dobot_msgs__srv__GripperControl_Response__Sequence *)allocator.allocate(sizeof(dobot_msgs__srv__GripperControl_Response__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = dobot_msgs__srv__GripperControl_Response__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
dobot_msgs__srv__GripperControl_Response__Sequence__destroy(dobot_msgs__srv__GripperControl_Response__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    dobot_msgs__srv__GripperControl_Response__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
dobot_msgs__srv__GripperControl_Response__Sequence__are_equal(const dobot_msgs__srv__GripperControl_Response__Sequence * lhs, const dobot_msgs__srv__GripperControl_Response__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!dobot_msgs__srv__GripperControl_Response__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
dobot_msgs__srv__GripperControl_Response__Sequence__copy(
  const dobot_msgs__srv__GripperControl_Response__Sequence * input,
  dobot_msgs__srv__GripperControl_Response__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(dobot_msgs__srv__GripperControl_Response)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(dobot_msgs__srv__GripperControl_Response);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    dobot_msgs__srv__GripperControl_Response * data =
      (dobot_msgs__srv__GripperControl_Response *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!dobot_msgs__srv__GripperControl_Response__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          dobot_msgs__srv__GripperControl_Response__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!dobot_msgs__srv__GripperControl_Response__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}


// Include directives for member types
// Member `info`
#include "service_msgs/msg/detail/service_event_info__functions.h"
// Member `request`
// Member `response`
// already included above
// #include "dobot_msgs/srv/detail/gripper_control__functions.h"

bool
dobot_msgs__srv__GripperControl_Event__init(dobot_msgs__srv__GripperControl_Event * msg)
{
  if (!msg) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__init(&msg->info)) {
    dobot_msgs__srv__GripperControl_Event__fini(msg);
    return false;
  }
  // request
  if (!dobot_msgs__srv__GripperControl_Request__Sequence__init(&msg->request, 0)) {
    dobot_msgs__srv__GripperControl_Event__fini(msg);
    return false;
  }
  // response
  if (!dobot_msgs__srv__GripperControl_Response__Sequence__init(&msg->response, 0)) {
    dobot_msgs__srv__GripperControl_Event__fini(msg);
    return false;
  }
  return true;
}

void
dobot_msgs__srv__GripperControl_Event__fini(dobot_msgs__srv__GripperControl_Event * msg)
{
  if (!msg) {
    return;
  }
  // info
  service_msgs__msg__ServiceEventInfo__fini(&msg->info);
  // request
  dobot_msgs__srv__GripperControl_Request__Sequence__fini(&msg->request);
  // response
  dobot_msgs__srv__GripperControl_Response__Sequence__fini(&msg->response);
}

bool
dobot_msgs__srv__GripperControl_Event__are_equal(const dobot_msgs__srv__GripperControl_Event * lhs, const dobot_msgs__srv__GripperControl_Event * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__are_equal(
      &(lhs->info), &(rhs->info)))
  {
    return false;
  }
  // request
  if (!dobot_msgs__srv__GripperControl_Request__Sequence__are_equal(
      &(lhs->request), &(rhs->request)))
  {
    return false;
  }
  // response
  if (!dobot_msgs__srv__GripperControl_Response__Sequence__are_equal(
      &(lhs->response), &(rhs->response)))
  {
    return false;
  }
  return true;
}

bool
dobot_msgs__srv__GripperControl_Event__copy(
  const dobot_msgs__srv__GripperControl_Event * input,
  dobot_msgs__srv__GripperControl_Event * output)
{
  if (!input || !output) {
    return false;
  }
  // info
  if (!service_msgs__msg__ServiceEventInfo__copy(
      &(input->info), &(output->info)))
  {
    return false;
  }
  // request
  if (!dobot_msgs__srv__GripperControl_Request__Sequence__copy(
      &(input->request), &(output->request)))
  {
    return false;
  }
  // response
  if (!dobot_msgs__srv__GripperControl_Response__Sequence__copy(
      &(input->response), &(output->response)))
  {
    return false;
  }
  return true;
}

dobot_msgs__srv__GripperControl_Event *
dobot_msgs__srv__GripperControl_Event__create(void)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Event * msg = (dobot_msgs__srv__GripperControl_Event *)allocator.allocate(sizeof(dobot_msgs__srv__GripperControl_Event), allocator.state);
  if (!msg) {
    return NULL;
  }
  memset(msg, 0, sizeof(dobot_msgs__srv__GripperControl_Event));
  bool success = dobot_msgs__srv__GripperControl_Event__init(msg);
  if (!success) {
    allocator.deallocate(msg, allocator.state);
    return NULL;
  }
  return msg;
}

void
dobot_msgs__srv__GripperControl_Event__destroy(dobot_msgs__srv__GripperControl_Event * msg)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (msg) {
    dobot_msgs__srv__GripperControl_Event__fini(msg);
  }
  allocator.deallocate(msg, allocator.state);
}


bool
dobot_msgs__srv__GripperControl_Event__Sequence__init(dobot_msgs__srv__GripperControl_Event__Sequence * array, size_t size)
{
  if (!array) {
    return false;
  }
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Event * data = NULL;

  if (size) {
    if (size > SIZE_MAX / sizeof(dobot_msgs__srv__GripperControl_Event)) {
      return false;
    }
    data = (dobot_msgs__srv__GripperControl_Event *)allocator.zero_allocate(size, sizeof(dobot_msgs__srv__GripperControl_Event), allocator.state);
    if (!data) {
      return false;
    }
    // initialize all array elements
    size_t i;
    for (i = 0; i < size; ++i) {
      bool success = dobot_msgs__srv__GripperControl_Event__init(&data[i]);
      if (!success) {
        break;
      }
    }
    if (i < size) {
      // if initialization failed finalize the already initialized array elements
      for (; i > 0; --i) {
        dobot_msgs__srv__GripperControl_Event__fini(&data[i - 1]);
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
dobot_msgs__srv__GripperControl_Event__Sequence__fini(dobot_msgs__srv__GripperControl_Event__Sequence * array)
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
      dobot_msgs__srv__GripperControl_Event__fini(&array->data[i]);
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

dobot_msgs__srv__GripperControl_Event__Sequence *
dobot_msgs__srv__GripperControl_Event__Sequence__create(size_t size)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  dobot_msgs__srv__GripperControl_Event__Sequence * array = (dobot_msgs__srv__GripperControl_Event__Sequence *)allocator.allocate(sizeof(dobot_msgs__srv__GripperControl_Event__Sequence), allocator.state);
  if (!array) {
    return NULL;
  }
  bool success = dobot_msgs__srv__GripperControl_Event__Sequence__init(array, size);
  if (!success) {
    allocator.deallocate(array, allocator.state);
    return NULL;
  }
  return array;
}

void
dobot_msgs__srv__GripperControl_Event__Sequence__destroy(dobot_msgs__srv__GripperControl_Event__Sequence * array)
{
  rcutils_allocator_t allocator = rcutils_get_default_allocator();
  if (array) {
    dobot_msgs__srv__GripperControl_Event__Sequence__fini(array);
  }
  allocator.deallocate(array, allocator.state);
}

bool
dobot_msgs__srv__GripperControl_Event__Sequence__are_equal(const dobot_msgs__srv__GripperControl_Event__Sequence * lhs, const dobot_msgs__srv__GripperControl_Event__Sequence * rhs)
{
  if (!lhs || !rhs) {
    return false;
  }
  if (lhs->size != rhs->size) {
    return false;
  }
  for (size_t i = 0; i < lhs->size; ++i) {
    if (!dobot_msgs__srv__GripperControl_Event__are_equal(&(lhs->data[i]), &(rhs->data[i]))) {
      return false;
    }
  }
  return true;
}

bool
dobot_msgs__srv__GripperControl_Event__Sequence__copy(
  const dobot_msgs__srv__GripperControl_Event__Sequence * input,
  dobot_msgs__srv__GripperControl_Event__Sequence * output)
{
  if (!input || !output) {
    return false;
  }
  if (output->capacity < input->size) {
    if (input->size > SIZE_MAX / sizeof(dobot_msgs__srv__GripperControl_Event)) {
      return false;
    }
    const size_t allocation_size =
      input->size * sizeof(dobot_msgs__srv__GripperControl_Event);
    rcutils_allocator_t allocator = rcutils_get_default_allocator();
    dobot_msgs__srv__GripperControl_Event * data =
      (dobot_msgs__srv__GripperControl_Event *)allocator.reallocate(
      output->data, allocation_size, allocator.state);
    if (!data) {
      return false;
    }
    // If reallocation succeeded, memory may or may not have been moved
    // to fulfill the allocation request, invalidating output->data.
    output->data = data;
    for (size_t i = output->capacity; i < input->size; ++i) {
      if (!dobot_msgs__srv__GripperControl_Event__init(&output->data[i])) {
        // If initialization of any new item fails, roll back
        // all previously initialized items. Existing items
        // in output are to be left unmodified.
        for (; i-- > output->capacity; ) {
          dobot_msgs__srv__GripperControl_Event__fini(&output->data[i]);
        }
        return false;
      }
    }
    output->capacity = input->size;
  }
  output->size = input->size;
  for (size_t i = 0; i < input->size; ++i) {
    if (!dobot_msgs__srv__GripperControl_Event__copy(
        &(input->data[i]), &(output->data[i])))
    {
      return false;
    }
  }
  return true;
}
