// generated from rosidl_generator_c/resource/idl__description.c.em
// with input from dobot_msgs:srv/SuctionCupControl.idl
// generated code does not contain a copyright notice

#include "dobot_msgs/srv/detail/suction_cup_control__functions.h"

ROSIDL_GENERATOR_C_PUBLIC_dobot_msgs
const rosidl_type_hash_t *
dobot_msgs__srv__SuctionCupControl__get_type_hash(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xa0, 0x5c, 0xeb, 0xb7, 0xd1, 0x41, 0xb8, 0xa5,
      0x8a, 0xf3, 0xee, 0x62, 0x3c, 0xfa, 0x06, 0x3f,
      0xc1, 0xe2, 0xd0, 0xad, 0x9b, 0x18, 0xf7, 0x34,
      0xae, 0x99, 0xa1, 0x39, 0xe5, 0x1b, 0x7e, 0xb8,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_dobot_msgs
const rosidl_type_hash_t *
dobot_msgs__srv__SuctionCupControl_Request__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xfd, 0x05, 0x82, 0x73, 0xb9, 0x7c, 0x69, 0x09,
      0x02, 0xb1, 0x30, 0x5e, 0x14, 0xa4, 0xc8, 0xda,
      0xf6, 0xd2, 0x87, 0x67, 0xe4, 0x98, 0xc5, 0xab,
      0x8f, 0x3d, 0x1b, 0xcf, 0xeb, 0x35, 0x17, 0x24,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_dobot_msgs
const rosidl_type_hash_t *
dobot_msgs__srv__SuctionCupControl_Response__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0xa4, 0xd6, 0x15, 0xe4, 0xa3, 0x3a, 0xe4, 0xb8,
      0x67, 0xb3, 0xc2, 0xb1, 0xda, 0xbf, 0x0d, 0x88,
      0xd6, 0x58, 0x7f, 0x3e, 0xed, 0xb1, 0xf2, 0x95,
      0x8c, 0x45, 0x49, 0xd7, 0x49, 0x59, 0xd3, 0x75,
    }};
  return &hash;
}

ROSIDL_GENERATOR_C_PUBLIC_dobot_msgs
const rosidl_type_hash_t *
dobot_msgs__srv__SuctionCupControl_Event__get_type_hash(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_type_hash_t hash = {1, {
      0x73, 0x67, 0x78, 0xab, 0x39, 0x28, 0x5d, 0x5b,
      0x1f, 0xd6, 0xff, 0x3d, 0x16, 0x8f, 0x9d, 0x7c,
      0x7b, 0xd9, 0x7c, 0x29, 0x56, 0xc6, 0x7a, 0x47,
      0x99, 0x72, 0x36, 0x24, 0xaf, 0x4e, 0x1a, 0xd9,
    }};
  return &hash;
}

#include <assert.h>
#include <string.h>

// Include directives for referenced types
#include "builtin_interfaces/msg/detail/time__functions.h"
#include "service_msgs/msg/detail/service_event_info__functions.h"

// Hashes for external referenced types
#ifndef NDEBUG
static const rosidl_type_hash_t builtin_interfaces__msg__Time__EXPECTED_HASH = {1, {
    0xb1, 0x06, 0x23, 0x5e, 0x25, 0xa4, 0xc5, 0xed,
    0x35, 0x09, 0x8a, 0xa0, 0xa6, 0x1a, 0x3e, 0xe9,
    0xc9, 0xb1, 0x8d, 0x19, 0x7f, 0x39, 0x8b, 0x0e,
    0x42, 0x06, 0xce, 0xa9, 0xac, 0xf9, 0xc1, 0x97,
  }};
static const rosidl_type_hash_t service_msgs__msg__ServiceEventInfo__EXPECTED_HASH = {1, {
    0x41, 0xbc, 0xbb, 0xe0, 0x7a, 0x75, 0xc9, 0xb5,
    0x2b, 0xc9, 0x6b, 0xfd, 0x5c, 0x24, 0xd7, 0xf0,
    0xfc, 0x0a, 0x08, 0xc0, 0xcb, 0x79, 0x21, 0xb3,
    0x37, 0x3c, 0x57, 0x32, 0x34, 0x5a, 0x6f, 0x45,
  }};
#endif

static char dobot_msgs__srv__SuctionCupControl__TYPE_NAME[] = "dobot_msgs/srv/SuctionCupControl";
static char builtin_interfaces__msg__Time__TYPE_NAME[] = "builtin_interfaces/msg/Time";
static char dobot_msgs__srv__SuctionCupControl_Event__TYPE_NAME[] = "dobot_msgs/srv/SuctionCupControl_Event";
static char dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME[] = "dobot_msgs/srv/SuctionCupControl_Request";
static char dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME[] = "dobot_msgs/srv/SuctionCupControl_Response";
static char service_msgs__msg__ServiceEventInfo__TYPE_NAME[] = "service_msgs/msg/ServiceEventInfo";

// Define type names, field names, and default values
static char dobot_msgs__srv__SuctionCupControl__FIELD_NAME__request_message[] = "request_message";
static char dobot_msgs__srv__SuctionCupControl__FIELD_NAME__response_message[] = "response_message";
static char dobot_msgs__srv__SuctionCupControl__FIELD_NAME__event_message[] = "event_message";

static rosidl_runtime_c__type_description__Field dobot_msgs__srv__SuctionCupControl__FIELDS[] = {
  {
    {dobot_msgs__srv__SuctionCupControl__FIELD_NAME__request_message, 15, 15},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME, 40, 40},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl__FIELD_NAME__response_message, 16, 16},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME, 41, 41},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl__FIELD_NAME__event_message, 13, 13},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {dobot_msgs__srv__SuctionCupControl_Event__TYPE_NAME, 38, 38},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription dobot_msgs__srv__SuctionCupControl__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Event__TYPE_NAME, 38, 38},
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME, 40, 40},
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME, 41, 41},
    {NULL, 0, 0},
  },
  {
    {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
dobot_msgs__srv__SuctionCupControl__get_type_description(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {dobot_msgs__srv__SuctionCupControl__TYPE_NAME, 32, 32},
      {dobot_msgs__srv__SuctionCupControl__FIELDS, 3, 3},
    },
    {dobot_msgs__srv__SuctionCupControl__REFERENCED_TYPE_DESCRIPTIONS, 5, 5},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[1].fields = dobot_msgs__srv__SuctionCupControl_Event__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[2].fields = dobot_msgs__srv__SuctionCupControl_Request__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[3].fields = dobot_msgs__srv__SuctionCupControl_Response__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&service_msgs__msg__ServiceEventInfo__EXPECTED_HASH, service_msgs__msg__ServiceEventInfo__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[4].fields = service_msgs__msg__ServiceEventInfo__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char dobot_msgs__srv__SuctionCupControl_Request__FIELD_NAME__enable_suction[] = "enable_suction";

static rosidl_runtime_c__type_description__Field dobot_msgs__srv__SuctionCupControl_Request__FIELDS[] = {
  {
    {dobot_msgs__srv__SuctionCupControl_Request__FIELD_NAME__enable_suction, 14, 14},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
dobot_msgs__srv__SuctionCupControl_Request__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME, 40, 40},
      {dobot_msgs__srv__SuctionCupControl_Request__FIELDS, 1, 1},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char dobot_msgs__srv__SuctionCupControl_Response__FIELD_NAME__success[] = "success";
static char dobot_msgs__srv__SuctionCupControl_Response__FIELD_NAME__message[] = "message";

static rosidl_runtime_c__type_description__Field dobot_msgs__srv__SuctionCupControl_Response__FIELDS[] = {
  {
    {dobot_msgs__srv__SuctionCupControl_Response__FIELD_NAME__success, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_BOOLEAN,
      0,
      0,
      {NULL, 0, 0},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Response__FIELD_NAME__message, 7, 7},
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
dobot_msgs__srv__SuctionCupControl_Response__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME, 41, 41},
      {dobot_msgs__srv__SuctionCupControl_Response__FIELDS, 2, 2},
    },
    {NULL, 0, 0},
  };
  if (!constructed) {
    constructed = true;
  }
  return &description;
}
// Define type names, field names, and default values
static char dobot_msgs__srv__SuctionCupControl_Event__FIELD_NAME__info[] = "info";
static char dobot_msgs__srv__SuctionCupControl_Event__FIELD_NAME__request[] = "request";
static char dobot_msgs__srv__SuctionCupControl_Event__FIELD_NAME__response[] = "response";

static rosidl_runtime_c__type_description__Field dobot_msgs__srv__SuctionCupControl_Event__FIELDS[] = {
  {
    {dobot_msgs__srv__SuctionCupControl_Event__FIELD_NAME__info, 4, 4},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE,
      0,
      0,
      {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Event__FIELD_NAME__request, 7, 7},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_BOUNDED_SEQUENCE,
      1,
      0,
      {dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME, 40, 40},
    },
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Event__FIELD_NAME__response, 8, 8},
    {
      rosidl_runtime_c__type_description__FieldType__FIELD_TYPE_NESTED_TYPE_BOUNDED_SEQUENCE,
      1,
      0,
      {dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME, 41, 41},
    },
    {NULL, 0, 0},
  },
};

static rosidl_runtime_c__type_description__IndividualTypeDescription dobot_msgs__srv__SuctionCupControl_Event__REFERENCED_TYPE_DESCRIPTIONS[] = {
  {
    {builtin_interfaces__msg__Time__TYPE_NAME, 27, 27},
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME, 40, 40},
    {NULL, 0, 0},
  },
  {
    {dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME, 41, 41},
    {NULL, 0, 0},
  },
  {
    {service_msgs__msg__ServiceEventInfo__TYPE_NAME, 33, 33},
    {NULL, 0, 0},
  },
};

const rosidl_runtime_c__type_description__TypeDescription *
dobot_msgs__srv__SuctionCupControl_Event__get_type_description(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static bool constructed = false;
  static const rosidl_runtime_c__type_description__TypeDescription description = {
    {
      {dobot_msgs__srv__SuctionCupControl_Event__TYPE_NAME, 38, 38},
      {dobot_msgs__srv__SuctionCupControl_Event__FIELDS, 3, 3},
    },
    {dobot_msgs__srv__SuctionCupControl_Event__REFERENCED_TYPE_DESCRIPTIONS, 4, 4},
  };
  if (!constructed) {
    assert(0 == memcmp(&builtin_interfaces__msg__Time__EXPECTED_HASH, builtin_interfaces__msg__Time__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[0].fields = builtin_interfaces__msg__Time__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[1].fields = dobot_msgs__srv__SuctionCupControl_Request__get_type_description(NULL)->type_description.fields;
    description.referenced_type_descriptions.data[2].fields = dobot_msgs__srv__SuctionCupControl_Response__get_type_description(NULL)->type_description.fields;
    assert(0 == memcmp(&service_msgs__msg__ServiceEventInfo__EXPECTED_HASH, service_msgs__msg__ServiceEventInfo__get_type_hash(NULL), sizeof(rosidl_type_hash_t)));
    description.referenced_type_descriptions.data[3].fields = service_msgs__msg__ServiceEventInfo__get_type_description(NULL)->type_description.fields;
    constructed = true;
  }
  return &description;
}

static char toplevel_type_raw_source[] =
  "#request fields\n"
  "bool enable_suction\n"
  "---\n"
  "#response fields\n"
  "bool success   \n"
  "string message";

static char srv_encoding[] = "srv";
static char implicit_encoding[] = "implicit";

// Define all individual source functions

const rosidl_runtime_c__type_description__TypeSource *
dobot_msgs__srv__SuctionCupControl__get_individual_type_description_source(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {dobot_msgs__srv__SuctionCupControl__TYPE_NAME, 32, 32},
    {srv_encoding, 3, 3},
    {toplevel_type_raw_source, 87, 87},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
dobot_msgs__srv__SuctionCupControl_Request__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {dobot_msgs__srv__SuctionCupControl_Request__TYPE_NAME, 40, 40},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
dobot_msgs__srv__SuctionCupControl_Response__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {dobot_msgs__srv__SuctionCupControl_Response__TYPE_NAME, 41, 41},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource *
dobot_msgs__srv__SuctionCupControl_Event__get_individual_type_description_source(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static const rosidl_runtime_c__type_description__TypeSource source = {
    {dobot_msgs__srv__SuctionCupControl_Event__TYPE_NAME, 38, 38},
    {implicit_encoding, 8, 8},
    {NULL, 0, 0},
  };
  return &source;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
dobot_msgs__srv__SuctionCupControl__get_type_description_sources(
  const rosidl_service_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[6];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 6, 6};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *dobot_msgs__srv__SuctionCupControl__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *dobot_msgs__srv__SuctionCupControl_Event__get_individual_type_description_source(NULL);
    sources[3] = *dobot_msgs__srv__SuctionCupControl_Request__get_individual_type_description_source(NULL);
    sources[4] = *dobot_msgs__srv__SuctionCupControl_Response__get_individual_type_description_source(NULL);
    sources[5] = *service_msgs__msg__ServiceEventInfo__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
dobot_msgs__srv__SuctionCupControl_Request__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *dobot_msgs__srv__SuctionCupControl_Request__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
dobot_msgs__srv__SuctionCupControl_Response__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[1];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 1, 1};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *dobot_msgs__srv__SuctionCupControl_Response__get_individual_type_description_source(NULL),
    constructed = true;
  }
  return &source_sequence;
}

const rosidl_runtime_c__type_description__TypeSource__Sequence *
dobot_msgs__srv__SuctionCupControl_Event__get_type_description_sources(
  const rosidl_message_type_support_t * type_support)
{
  (void)type_support;
  static rosidl_runtime_c__type_description__TypeSource sources[5];
  static const rosidl_runtime_c__type_description__TypeSource__Sequence source_sequence = {sources, 5, 5};
  static bool constructed = false;
  if (!constructed) {
    sources[0] = *dobot_msgs__srv__SuctionCupControl_Event__get_individual_type_description_source(NULL),
    sources[1] = *builtin_interfaces__msg__Time__get_individual_type_description_source(NULL);
    sources[2] = *dobot_msgs__srv__SuctionCupControl_Request__get_individual_type_description_source(NULL);
    sources[3] = *dobot_msgs__srv__SuctionCupControl_Response__get_individual_type_description_source(NULL);
    sources[4] = *service_msgs__msg__ServiceEventInfo__get_individual_type_description_source(NULL);
    constructed = true;
  }
  return &source_sequence;
}
