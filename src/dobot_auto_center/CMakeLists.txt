cmake_minimum_required(VERSION 3.16)
project(dobot_auto_center)
find_package(ament_cmake REQUIRED)
find_package(ament_cmake_python REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(action_msgs REQUIRED)

rosidl_generate_interfaces(${PROJECT_NAME} "action/GuardedMove.action"
  DEPENDENCIES action_msgs)

# rosidl installs the parent namespace. Install our Python modules beside its
# generated action package without creating a duplicate ament Python target.
ament_get_python_install_dir(PYTHON_INSTALL_DIR)
install(DIRECTORY dobot_auto_center/ DESTINATION "${PYTHON_INSTALL_DIR}/${PROJECT_NAME}"
  FILES_MATCHING PATTERN "*.py" PATTERN "__pycache__" EXCLUDE)
install(PROGRAMS scripts/auto_center scripts/auto_center_readiness DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY web DESTINATION share/${PROJECT_NAME})
install(FILES ../../config/hardware.yaml ../../config/camera.yaml ../../config/vision.yaml
  ../../config/visual_servo.yaml ../../config/motion.yaml ../../config/safety.yaml ../../config/web.yaml
  DESTINATION share/${PROJECT_NAME}/config)
install(FILES ../../launch/auto_center.launch.py DESTINATION share/${PROJECT_NAME}/launch)
ament_export_dependencies(rosidl_default_runtime)
ament_package()
