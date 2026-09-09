cmake_minimum_required(VERSION 3.5)
project(dobot_description)

find_package(ament_cmake REQUIRED)

install(
  DIRECTORY launch meshes rviz model
  DESTINATION share/${PROJECT_NAME}
)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(display_configuration test/test_display_configuration.py)
  ament_add_pytest_test(eye_in_hand_geometry test/test_eye_in_hand_geometry.py)
  find_package(ament_lint_auto REQUIRED)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()
