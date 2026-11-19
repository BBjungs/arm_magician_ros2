cmake_minimum_required(VERSION 3.8)
project(dobot_driver)

find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
ament_python_install_package(${PROJECT_NAME})

install(PROGRAMS scripts/dobot_readback DESTINATION lib/${PROJECT_NAME})

set(workspace_source "${CMAKE_CURRENT_SOURCE_DIR}/../../..")
install(FILES
  "${workspace_source}/config/dobot.yaml"
  "${workspace_source}/config/orbbec.yaml"
  DESTINATION share/${PROJECT_NAME}/config)
install(FILES
  "${workspace_source}/launch/dobot_driver.launch.py"
  "${workspace_source}/launch/orbbec_camera.launch.py"
  DESTINATION share/${PROJECT_NAME}/launch)

ament_package()
