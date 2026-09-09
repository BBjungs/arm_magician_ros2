// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from dobot_msgs:msg/CircleTarget.idl
// generated code does not contain a copyright notice

#include "dobot_msgs/msg/detail/circle_target__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_dobot_msgs
const rosidl_type_hash_t *
dobot_msgs__msg__CircleTarget__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x91, 0x14, 0xb4, 0xd4, 0xe8, 0x69, 0x7f, 0xb1,
      0xd3, 0x06, 0x15, 0xe7, 0x8b, 0xdc, 0x8e, 0xe8,
      0xae, 0xb7, 0x9f, 0x13, 0xa7, 0xfa, 0xd8, 0x34,
      0x79, 0x3a, 0x51, 0x75, 0x9b, 0xb8, 0x80, 0x47,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types
#include "geometry_msgs/msg/detail/point__functions.h"

// Hashes for external referenced types
#ifndef NDEBUG
static const rosidl_type_hash_t geometry_msgs__msg__Point__EXPECTED_HASH = {1, {
    0x69, 0x63, 0x08, 0x48, 0x42, 0xa9, 0xb0, 0x44,
    0x94, 0xd6, 0xb2, 0x94, 0x1d, 0x11, 0x44, 0x47,
    0x08, 0xd8, 0x92, 0xda, 0x2f, 0x4b, 0x09, 0x84,
    0x3b, 0x9c, 0x43, 0xf4, 0x2a, 0x7f, 0x68, 0x81,
  }};
#endif

static char dobot_msgs__msg__CircleTarget__TYPE_NAME[] = "dobot_msgs/msg/CircleTarget";
static char geometry_msgs__msg__Point__TYPE_NAME[] = "geometry_msgs/msg/Point";

// Define type names, field names, and default values
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__id[] = "id";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__class_name[] = "class_name";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__center_uv[] = "center_uv";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__camera_xyz[] = "camera_xyz";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__depth[] = "depth";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__size[] = "size";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__confidence[] = "confidence";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__pickable[] = "pickable";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__top_height[] = "top_height";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__depth_valid_ratio[] = "depth_valid_ratio";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__depth_mad[] = "depth_mad";
static char dobot_msgs__msg__CircleTarget__FIELD_NAME__rejection_reason[] = "rejection_reason";

static rosidl_runtime_c__type_description__Field dobot_msgs__msg__CircleTarget__FIELDS[] = {
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__id, 2, 2},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_UINT32,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__class_name, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__center_uv, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE_ARRAY,
      2,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__camera_xyz, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {geometry_msgs__msg__Point__TYPE_NAME, 23, 23},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__depth, 5, 5},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__size, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__confidence, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__pickable, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__top_height, 10, 10},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__depth_valid_ratio, 17, 17},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__depth_mad, 9, 9},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_DOUBLE,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__msg__CircleTarget__FIELD_NAME__rejection_reason, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_STRING,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription dobot_msgs__msg__CircleTarget__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {geometry_msgs__msg__Point__TYPE_NAME, 23, 23},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
dobot_msgs__msg__CircleTarget__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {dobot_msgs__msg__CircleTarget__TYPE_NAME, 27, 27},
      {dobot_msgs__msg__CircleTarget__FIELDS, 12, 12},
    },
    {dobot_msgs__msg__CircleTarget__REFERENCED_TYPE_DESCRIPTIONS, 1, 1},
  };
  if (!constructed) {
    assert(0 == memcmp(&geometry_msgs__msg__Point__EXPECTED_HASH, geometry_msgs__msg__Point__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = geometry_msgs__msg__Point__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "# ID is local to this exposure; identify a target by (array header stamp, id).\n"
  "uint32 id\n"
  "# black, white or yellow\n"
  "string class_name\n"
  "float64[2] center_uv\n"
  "# Metres, in the array header's registered optical frame.\n"
  "geometry_msgs/Point camera_xyz\n"
  "# Optical Z in metres (not Euclidean range).\n"
  "float64 depth\n"
  "# Diameter in metres, measured in the object top plane.\n"
  "float64 size\n"
  "float64 confidence\n"
  "# Visual suction suitability only; robot calibration/readiness is a separate gate.\n"
  "bool pickable\n"
  "float64 top_height\n"
  "float64 depth_valid_ratio\n"
  "float64 depth_mad\n"
  "string rejection_reason";

static char msg_encoding[] = "msg";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
dobot_msgs__msg__CircleTarget__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {dobot_msgs__msg__CircleTarget__TYPE_NAME, 27, 27},
    {msg_encoding, 3, 3},
    {toplevel_type_raw_source, 573, 573},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
dobot_msgs__msg__CircleTarget__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[2];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 2, 2};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *dobot_msgs__msg__CircleTarget__get_individual_type_description_source(NULL),
    sources[1] = *geometry_msgs__msg__Point__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}
