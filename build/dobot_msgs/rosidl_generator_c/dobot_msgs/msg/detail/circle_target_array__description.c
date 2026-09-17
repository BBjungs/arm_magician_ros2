// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from dobot_msgs:msg/CircleTargetArray.idl
// generated code does not contain a copyright notice

#include "dobot_msgs/msg/detail/circle_target_array__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_dobot_msgs
const rosidl_type_hash_t *
dobot_msgs__msg__CircleTargetArray__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xab, 0x22, 0x1f, 0xdb, 0xeb, 0xd4, 0x68, 0x6e,
      0x21, 0xa3, 0x78, 0x39, 0x12, 0xb1, 0x7c, 0x90,
      0x88, 0xc6, 0x83, 0xae, 0x09, 0xda, 0xe8, 0xf6,
      0x75, 0xc9, 0x3b, 0x1b, 0x60, 0xee, 0xcb, 0x00,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types
#include "std_msgs/msg/detail/header__functions.h"
#include "builtin_interfaces/msg/detail/time__functions.h"
#include "dobot_msgs/msg/detail/circle_target__functions.h"
#include "geometry_msgs/msg/detail/point__functions.h"

// Hashes for external referenced types
#ifndef NDEBUG
static const rosidl_type_hash_t builtin_interfaces__msg__Time__EXPECTED_HASH = {1, {
    0xb1, 0x06, 0x23, 0x5e, 0x25, 0xa4, 0xc5, 0xed,
    0x35, 0x09, 0x8a, 0xa0, 0xa6, 0x1a, 0x3e, 0xe9,
    0xc9, 0xb1, 0x8d, 0x19, 0x7f, 0x39, 0x8b, 0x0e,
    0x42, 0x06, 0xce, 0xa9, 0xac, 0xf9, 0xc1, 0x97,
  }};
static const rosidl_type_hash_t dobot_msgs__msg__CircleTarget__EXPECTED_HASH = {1, {
    0x91, 0x14, 0xb4, 0xd4, 0xe8, 0x69, 0x7f, 0xb1,
    0xd3, 0x06, 0x15, 0xe7, 0x8b, 0xdc, 0x8e, 0xe8,
    0xae, 0xb7, 0x9f, 0x13, 0xa7, 0xfa, 0xd8, 0x34,
    0x79, 0x3a, 0x51, 0x75, 0x9b, 0xb8, 0x80, 0x47,
  }};
static const rosidl_type_hash_t geometry_msgs__msg__Point__EXPECTED_HASH = {1, {
    0x69, 0x63, 0x08, 0x48, 0x42, 0xa9, 0xb0, 0x44,
    0x94, 0xd6, 0xb2, 0x94, 0x1d, 0x11, 0x44, 0x47,
    0x08, 0xd8, 0x92, 0xda, 0x2f, 0x4b, 0x09, 0x84,
    0x3b, 0x9c, 0x43, 0xf4, 0x2a, 0x7f, 0x68, 0x81,
  }};
static const rosidl_type_hash_t std_msgs__msg__Header__EXPECTED_HASH = {1, {
    0xf4, 0x9f, 0xb3, 0xae, 0x2c, 0xf0, 0x70, 0xf7,
    0x93, 0x64, 0x5f, 0xf7, 0x49, 0x68, 0x3a, 0xc6,
    0xb0, 0x62, 0x03, 0xe4, 0x1c, 0x89, 0x1e, 0x17,
    0x70, 0x1b, 0x1c, 0xb5, 0x97, 0xce, 0x6a, 0x01,
  }};
#endif

static char dobot_msgs__msg__CircleTargetArray__TYPE_NAME[] = "dobot_msgs/msg/CircleTargetArray";
static char builtin_interfaces__msg__Time__TYPE_NAME[] = "builtin_interfaces/msg/Time";
static char dobot_msgs__msg__CircleTarget__TYPE_NAME[] = "dobot_msgs/msg/CircleTarget";
static char geometry_msgs__msg__Point__TYPE_NAME[] = "geometry_msgs/msg/Point";
static char std_msgs__msg__Header__TYPE_NAME[] = "std_msgs/msg/Header";

// Define type names, field names, and default values
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__header[] = "header";
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__valid[] = "valid";
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__reason[] = "reason";
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__table_plane[] = "table_plane";
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__table_inlier_ratio[] = "table_inlier_ratio";
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__table_rmse[] = "table_rmse";
static char dobot_msgs__msg__CircleTargetArray__FIELD_NAME__detections[] = "detections";

static rosidl_runtime_c__type_description__Field dobot_msgs__msg__CircleTargetArray__FIELDS[] = {
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__header, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {std_msgs__msg__Header__TYPE_NAME, 19, 19},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__valid, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__reason, 6, 6},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__table_plane, 11, 11},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE_ARRAY,
      4,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__table_inlier_ratio, 18, 18},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__table_rmse, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTargetArray__FIELD_NAME__detections, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_UNBOUNDED_SEQUENCE,
      0,
      0,
      {dobot_msgs__msg__CircleTarget__TYPE_NAME, 27, 27},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription dobot_msgs__msg__CircleTargetArray__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {geometry_msgs__msg__Point__TYPE_NAME, 23, 23},
    {NULL, 0, 0},
  },
  {
    {std_msgs__msg__Header__TYPE_NAME, 19, 19},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
dobot_msgs__msg__CircleTargetArray__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {dobot_msgs__msg__CircleTargetArray__TYPE_NAME, 32, 32},
      {dobot_msgs__msg__CircleTargetArray__FIELDS, 7, 7},
    },
    {dobot_msgs__msg__CircleTargetArray__REFERENCED_TYPE_DESCRIPTIONS, 4, 4},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&dobot_msgs__msg__CircleTarget__EXPECTED_HASH, dobot_msgs__msg__CircleTarget__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[1].fields = dobot_msgs__msg__CircleTarget__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&geometry_msgs__msg__Point__EXPECTED_HASH, geometry_msgs__msg__Point__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[2].fields = geometry_msgs__msg__Point__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&std_msgs__msg__Header__EXPECTED_HASH, std_msgs__msg__Header__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[3].fields = std_msgs__msg__Header__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "# RGB exposure stamp and registered optical frame; never the processing time.\n"
  "std_msgs/Header header\n"
  "bool valid\n"
  "string reason\n"
  "# Unit normal faces the camera; n dot camera_xyz + d = 0, metres.\n"
  "float64[4] table_plane\n"
  "float64 table_inlier_ratio\n"
  "float64 table_rmse\n"
  "CircleTarget[] detections";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
dobot_msgs__msg__CircleTargetArray__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {dobot_msgs__msg__CircleTargetArray__TYPE_NAME, 32, 32},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 287, 287},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
dobot_msgs__msg__CircleTargetArray__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[5];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 5, 5};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *dobot_msgs__msg__CircleTargetArray__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *dobot_msgs__msg__CircleTarget__get_individual_type_description_source(NULL);
    sources[3] = *geometry_msgs__msg__Point__get_individual_type_description_source(NULL);
    sources[4] = *std_msgs__msg__Header__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}
