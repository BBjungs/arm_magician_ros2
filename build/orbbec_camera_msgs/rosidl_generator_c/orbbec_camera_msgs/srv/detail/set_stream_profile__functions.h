// generated from rosidl_generator_c/resource/idl__functions.h.em
// with input from orbbec_camera_msgs:srv/SetStreamProfile.idl
// generated code does not contain a copyright notice

// IWYU pragma: private, include "orbbec_camera_msgs/srv/set_stream_profile.h"


#ifndef ORBBEC_CAMERA_MSGS__SRV__DETAIL__SET_STREAM_PROFILE__FUNCTIONS_H_
#define ORBBEC_CAMERA_MSGS__SRV__DETAIL__SET_STREAM_PROFILE__FUNCTIONS_H_

#ifdef __cplusplus
extern "C"
{
#endif

#include <stdbool.h>
#include <stdlib.h>

#include "rosidl_runtime_c/action_type_support_struct.h"
#include "rosidl_runtime_c/message_type_support_struct.h"
#include "rosidl_runtime_c/service_type_support_struct.h"
#include "rosidl_runtime_c/type_description/type_description__struct.h"
#include "rosidl_runtime_c/type_description/type_source__struct.h"
#include "rosidl_runtime_c/type_hash.h"
#include "rosidl_runtime_c/visibility_control.h"
#include "orbbec_camera_msgs/msg/rosidl_generator_c__visibility_control.h"

#include "orbbec_camera_msgs/srv/detail/set_stream_profile__struct.h"

/// Retrieve pointer to the hash of the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_type_hash_t *
orbbec_camera_msgs__srv__SetStreamProfile__get_type_hash(
  const rosidl_service_type_support_t * type_support);

/// Retrieve pointer to the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeDescription *
orbbec_camera_msgs__srv__SetStreamProfile__get_type_description(
  const rosidl_service_type_support_t * type_support);

/// Retrieve pointer to the single raw source text that defined this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource *
orbbec_camera_msgs__srv__SetStreamProfile__get_individual_type_description_source(
  const rosidl_service_type_support_t * type_support);

/// Retrieve pointer to the recursive raw sources that defined the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile__get_type_description_sources(
  const rosidl_service_type_support_t * type_support);

/// Initialize srv/SetStreamProfile message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * orbbec_camera_msgs__srv__SetStreamProfile_Request
 * )) before or use
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Request__init(orbbec_camera_msgs__srv__SetStreamProfile_Request * msg);

/// Finalize srv/SetStreamProfile message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Request__fini(orbbec_camera_msgs__srv__SetStreamProfile_Request * msg);

/// Create srv/SetStreamProfile message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
orbbec_camera_msgs__srv__SetStreamProfile_Request *
orbbec_camera_msgs__srv__SetStreamProfile_Request__create(void);

/// Destroy srv/SetStreamProfile message.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Request__destroy(orbbec_camera_msgs__srv__SetStreamProfile_Request * msg);

/// Check for srv/SetStreamProfile message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Request__are_equal(const orbbec_camera_msgs__srv__SetStreamProfile_Request * lhs, const orbbec_camera_msgs__srv__SetStreamProfile_Request * rhs);

/// Copy a srv/SetStreamProfile message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Request__copy(
  const orbbec_camera_msgs__srv__SetStreamProfile_Request * input,
  orbbec_camera_msgs__srv__SetStreamProfile_Request * output);

/// Retrieve pointer to the hash of the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_type_hash_t *
orbbec_camera_msgs__srv__SetStreamProfile_Request__get_type_hash(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeDescription *
orbbec_camera_msgs__srv__SetStreamProfile_Request__get_type_description(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the single raw source text that defined this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource *
orbbec_camera_msgs__srv__SetStreamProfile_Request__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the recursive raw sources that defined the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile_Request__get_type_description_sources(
  const rosidl_message_type_support_t * type_support);

/// Initialize array of srv/SetStreamProfile messages.
/**
 * It allocates the memory for the number of elements and calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__init(orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * array, size_t size);

/// Finalize array of srv/SetStreamProfile messages.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__fini(orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * array);

/// Create array of srv/SetStreamProfile messages.
/**
 * It allocates the memory for the array and calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__create(size_t size);

/// Destroy array of srv/SetStreamProfile messages.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__destroy(orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * array);

/// Check for srv/SetStreamProfile message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__are_equal(const orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * lhs, const orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * rhs);

/// Copy an array of srv/SetStreamProfile messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence__copy(
  const orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * input,
  orbbec_camera_msgs__srv__SetStreamProfile_Request__Sequence * output);

/// Initialize srv/SetStreamProfile message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * orbbec_camera_msgs__srv__SetStreamProfile_Response
 * )) before or use
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Response__init(orbbec_camera_msgs__srv__SetStreamProfile_Response * msg);

/// Finalize srv/SetStreamProfile message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Response__fini(orbbec_camera_msgs__srv__SetStreamProfile_Response * msg);

/// Create srv/SetStreamProfile message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
orbbec_camera_msgs__srv__SetStreamProfile_Response *
orbbec_camera_msgs__srv__SetStreamProfile_Response__create(void);

/// Destroy srv/SetStreamProfile message.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Response__destroy(orbbec_camera_msgs__srv__SetStreamProfile_Response * msg);

/// Check for srv/SetStreamProfile message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Response__are_equal(const orbbec_camera_msgs__srv__SetStreamProfile_Response * lhs, const orbbec_camera_msgs__srv__SetStreamProfile_Response * rhs);

/// Copy a srv/SetStreamProfile message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Response__copy(
  const orbbec_camera_msgs__srv__SetStreamProfile_Response * input,
  orbbec_camera_msgs__srv__SetStreamProfile_Response * output);

/// Retrieve pointer to the hash of the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_type_hash_t *
orbbec_camera_msgs__srv__SetStreamProfile_Response__get_type_hash(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeDescription *
orbbec_camera_msgs__srv__SetStreamProfile_Response__get_type_description(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the single raw source text that defined this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource *
orbbec_camera_msgs__srv__SetStreamProfile_Response__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the recursive raw sources that defined the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile_Response__get_type_description_sources(
  const rosidl_message_type_support_t * type_support);

/// Initialize array of srv/SetStreamProfile messages.
/**
 * It allocates the memory for the number of elements and calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__init(orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * array, size_t size);

/// Finalize array of srv/SetStreamProfile messages.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__fini(orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * array);

/// Create array of srv/SetStreamProfile messages.
/**
 * It allocates the memory for the array and calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__create(size_t size);

/// Destroy array of srv/SetStreamProfile messages.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__destroy(orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * array);

/// Check for srv/SetStreamProfile message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__are_equal(const orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * lhs, const orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * rhs);

/// Copy an array of srv/SetStreamProfile messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence__copy(
  const orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * input,
  orbbec_camera_msgs__srv__SetStreamProfile_Response__Sequence * output);

/// Initialize srv/SetStreamProfile message.
/**
 * If the init function is called twice for the same message without
 * calling fini inbetween previously allocated memory will be leaked.
 * \param[in,out] msg The previously allocated message pointer.
 * Fields without a default value will not be initialized by this function.
 * You might want to call memset(msg, 0, sizeof(
 * orbbec_camera_msgs__srv__SetStreamProfile_Event
 * )) before or use
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__create()
 * to allocate and initialize the message.
 * \return true if initialization was successful, otherwise false
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Event__init(orbbec_camera_msgs__srv__SetStreamProfile_Event * msg);

/// Finalize srv/SetStreamProfile message.
/**
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Event__fini(orbbec_camera_msgs__srv__SetStreamProfile_Event * msg);

/// Create srv/SetStreamProfile message.
/**
 * It allocates the memory for the message, sets the memory to zero, and
 * calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__init().
 * \return The pointer to the initialized message if successful,
 * otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
orbbec_camera_msgs__srv__SetStreamProfile_Event *
orbbec_camera_msgs__srv__SetStreamProfile_Event__create(void);

/// Destroy srv/SetStreamProfile message.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__fini()
 * and frees the memory of the message.
 * \param[in,out] msg The allocated message pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Event__destroy(orbbec_camera_msgs__srv__SetStreamProfile_Event * msg);

/// Check for srv/SetStreamProfile message equality.
/**
 * \param[in] lhs The message on the left hand size of the equality operator.
 * \param[in] rhs The message on the right hand size of the equality operator.
 * \return true if messages are equal, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Event__are_equal(const orbbec_camera_msgs__srv__SetStreamProfile_Event * lhs, const orbbec_camera_msgs__srv__SetStreamProfile_Event * rhs);

/// Copy a srv/SetStreamProfile message.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source message pointer.
 * \param[out] output The target message pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer is null
 *   or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Event__copy(
  const orbbec_camera_msgs__srv__SetStreamProfile_Event * input,
  orbbec_camera_msgs__srv__SetStreamProfile_Event * output);

/// Retrieve pointer to the hash of the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_type_hash_t *
orbbec_camera_msgs__srv__SetStreamProfile_Event__get_type_hash(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeDescription *
orbbec_camera_msgs__srv__SetStreamProfile_Event__get_type_description(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the single raw source text that defined this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource *
orbbec_camera_msgs__srv__SetStreamProfile_Event__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support);

/// Retrieve pointer to the recursive raw sources that defined the description of this type.
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_runtime_c__type_description__TypeSource__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile_Event__get_type_description_sources(
  const rosidl_message_type_support_t * type_support);

/// Initialize array of srv/SetStreamProfile messages.
/**
 * It allocates the memory for the number of elements and calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__init()
 * for each element of the array.
 * \param[in,out] array The allocated array pointer.
 * \param[in] size The size / capacity of the array.
 * \return true if initialization was successful, otherwise false
 * If the array pointer is valid and the size is zero it is guaranteed
 # to return true.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__init(orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * array, size_t size);

/// Finalize array of srv/SetStreamProfile messages.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__fini()
 * for each element of the array and frees the memory for the number of
 * elements.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__fini(orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * array);

/// Create array of srv/SetStreamProfile messages.
/**
 * It allocates the memory for the array and calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__init().
 * \param[in] size The size / capacity of the array.
 * \return The pointer to the initialized array if successful, otherwise NULL
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence *
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__create(size_t size);

/// Destroy array of srv/SetStreamProfile messages.
/**
 * It calls
 * orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__fini()
 * on the array,
 * and frees the memory of the array.
 * \param[in,out] array The initialized array pointer.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
void
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__destroy(orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * array);

/// Check for srv/SetStreamProfile message array equality.
/**
 * \param[in] lhs The message array on the left hand size of the equality operator.
 * \param[in] rhs The message array on the right hand size of the equality operator.
 * \return true if message arrays are equal in size and content, otherwise false.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__are_equal(const orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * lhs, const orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * rhs);

/// Copy an array of srv/SetStreamProfile messages.
/**
 * This functions performs a deep copy, as opposed to the shallow copy that
 * plain assignment yields.
 *
 * \param[in] input The source array pointer.
 * \param[out] output The target array pointer, which must
 *   have been initialized before calling this function.
 * \return true if successful, or false if either pointer
 *   is null or memory allocation fails.
 */
ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
bool
orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence__copy(
  const orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * input,
  orbbec_camera_msgs__srv__SetStreamProfile_Event__Sequence * output);
#ifdef __cplusplus
}
#endif

#endif  // ORBBEC_CAMERA_MSGS__SRV__DETAIL__SET_STREAM_PROFILE__FUNCTIONS_H_
