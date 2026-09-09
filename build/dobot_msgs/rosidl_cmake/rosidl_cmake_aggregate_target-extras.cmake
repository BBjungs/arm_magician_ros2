# generated from rosidl_cmake/cmake/rosidl_cmake_aggregate_target-extras.cmake.in

# Create a convenience aggregate target dobot_msgs::dobot_msgs
# that links all generated interface targets, so downstream packages can use
# a single modern CMake target name instead of ${dobot_msgs_TARGETS}.
if(dobot_msgs_TARGETS AND NOT TARGET dobot_msgs::dobot_msgs)
  add_library(dobot_msgs::dobot_msgs INTERFACE IMPORTED)
  set_target_properties(dobot_msgs::dobot_msgs PROPERTIES
    INTERFACE_LINK_LIBRARIES "${dobot_msgs_TARGETS}")
endif()
