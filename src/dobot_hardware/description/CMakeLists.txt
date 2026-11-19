cmake_minimum_required(VERSION 3.8)
project(dobot_description)

find_package(ament_cmake REQUIRED)
install(DIRECTORY model meshes DESTINATION share/${PROJECT_NAME})
ament_package()
