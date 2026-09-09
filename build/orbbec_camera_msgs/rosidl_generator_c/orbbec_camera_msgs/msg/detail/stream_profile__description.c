// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from orbbec_camera_msgs:msg/StreamProfile.idl
// generated code does not contain a copyright notice

#include "orbbec_camera_msgs/msg/detail/stream_profile__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_orbbec_camera_msgs
const rosidl_type_hash_t *
orbbec_camera_msgs__msg__StreamProfile__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x19, 0xf2, 0x2c, 0xbe, 0x8b, 0xe4, 0xab, 0x39,
      0xd1, 0xd0, 0x84, 0x8e, 0xf8, 0xc1, 0x58, 0xa1,
      0x73, 0x7b, 0x6d, 0xb1, 0x93, 0xeb, 0xda, 0x55,
      0x18, 0xbd, 0x10, 0x30, 0xfb, 0x65, 0x07, 0x2b,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types

// Hashes for external referenced types
#ifndef NDEBUG
#endif

static char orbbec_camera_msgs__msg__StreamProfile__TYPE_NAME[] = "orbbec_camera_msgs/msg/StreamProfile";

// Define type names, field names, and default values
static char orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__stream_name[] = "stream_name";
static char orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__width[] = "width";
static char orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__height[] = "height";
static char orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__fps[] = "fps";
static char orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__format[] = "format";

static rosidl_runtime_c__type_description__Field orbbec_camera_msgs__msg__StreamProfile__FIELDS[] = {
  {
    {orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__stream_name, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__width, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__height, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__fps, 3, 3},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_INT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {orbbec_camera_msgs__msg__StreamProfile__FIELD_NAME__format, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
orbbec_camera_msgs__msg__StreamProfile__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {orbbec_camera_msgs__msg__StreamProfile__TYPE_NAME, 36, 36},
      {orbbec_camera_msgs__msg__StreamProfile__FIELDS, 5, 5},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "string stream_name\n"
  "int32 width\n"
  "int32 height\n"
  "int32 fps\n"
  "string format";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
orbbec_camera_msgs__msg__StreamProfile__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {orbbec_camera_msgs__msg__StreamProfile__TYPE_NAME, 36, 36},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 68, 68},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
orbbec_camera_msgs__msg__StreamProfile__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *orbbec_camera_msgs__msg__StreamProfile__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}
