#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};


#[link(name = "dobot_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__DobotAlarmCodes() -> *const std::ffi::c_void;
}

#[link(name = "dobot_msgs__rosidl_generator_c")]
extern "C" {
    fn dobot_msgs__msg__DobotAlarmCodes__init(msg: *mut DobotAlarmCodes) -> bool;
    fn dobot_msgs__msg__DobotAlarmCodes__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<DobotAlarmCodes>, size: usize) -> bool;
    fn dobot_msgs__msg__DobotAlarmCodes__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<DobotAlarmCodes>);
    fn dobot_msgs__msg__DobotAlarmCodes__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<DobotAlarmCodes>, out_seq: *mut rosidl_runtime_rs::Sequence<DobotAlarmCodes>) -> bool;
}

// Corresponds to dobot_msgs__msg__DobotAlarmCodes
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct DobotAlarmCodes {
    /// for timestamp
    pub header: std_msgs::msg::rmw::Header,

    /// list of alarm codes as hex values
    pub alarms_list: rosidl_runtime_rs::Sequence<i32>,

}



impl Default for DobotAlarmCodes {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !dobot_msgs__msg__DobotAlarmCodes__init(&mut msg as *mut _) {
        panic!("Call to dobot_msgs__msg__DobotAlarmCodes__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for DobotAlarmCodes {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__DobotAlarmCodes__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__DobotAlarmCodes__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__DobotAlarmCodes__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for DobotAlarmCodes {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for DobotAlarmCodes where Self: Sized {
  const TYPE_NAME: &'static str = "dobot_msgs/msg/DobotAlarmCodes";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__DobotAlarmCodes() }
  }
}


#[link(name = "dobot_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__GripperStatus() -> *const std::ffi::c_void;
}

#[link(name = "dobot_msgs__rosidl_generator_c")]
extern "C" {
    fn dobot_msgs__msg__GripperStatus__init(msg: *mut GripperStatus) -> bool;
    fn dobot_msgs__msg__GripperStatus__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<GripperStatus>, size: usize) -> bool;
    fn dobot_msgs__msg__GripperStatus__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<GripperStatus>);
    fn dobot_msgs__msg__GripperStatus__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<GripperStatus>, out_seq: *mut rosidl_runtime_rs::Sequence<GripperStatus>) -> bool;
}

// Corresponds to dobot_msgs__msg__GripperStatus
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]


// This struct is not documented.
#[allow(missing_docs)]

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct GripperStatus {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::rmw::Header,

    /// either opened or closed
    pub status: rosidl_runtime_rs::String,

}



impl Default for GripperStatus {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !dobot_msgs__msg__GripperStatus__init(&mut msg as *mut _) {
        panic!("Call to dobot_msgs__msg__GripperStatus__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for GripperStatus {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__GripperStatus__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__GripperStatus__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__GripperStatus__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for GripperStatus {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for GripperStatus where Self: Sized {
  const TYPE_NAME: &'static str = "dobot_msgs/msg/GripperStatus";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__GripperStatus() }
  }
}


#[link(name = "dobot_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__CircleTarget() -> *const std::ffi::c_void;
}

#[link(name = "dobot_msgs__rosidl_generator_c")]
extern "C" {
    fn dobot_msgs__msg__CircleTarget__init(msg: *mut CircleTarget) -> bool;
    fn dobot_msgs__msg__CircleTarget__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<CircleTarget>, size: usize) -> bool;
    fn dobot_msgs__msg__CircleTarget__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<CircleTarget>);
    fn dobot_msgs__msg__CircleTarget__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<CircleTarget>, out_seq: *mut rosidl_runtime_rs::Sequence<CircleTarget>) -> bool;
}

// Corresponds to dobot_msgs__msg__CircleTarget
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]

/// ID is local to this exposure; identify a target by (array header stamp, id).

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct CircleTarget {

    // This member is not documented.
    #[allow(missing_docs)]
    pub id: u32,

    /// black, white or yellow
    pub class_name: rosidl_runtime_rs::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub center_uv: [f64; 2],

    /// Metres, in the array header's registered optical frame.
    pub camera_xyz: geometry_msgs::msg::rmw::Point,

    /// Optical Z in metres (not Euclidean range).
    pub depth: f64,

    /// Diameter in metres, measured in the object top plane.
    pub size: f64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub confidence: f64,

    /// Visual suction suitability only; robot calibration/readiness is a separate gate.
    pub pickable: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub top_height: f64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub depth_valid_ratio: f64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub depth_mad: f64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub rejection_reason: rosidl_runtime_rs::String,

}



impl Default for CircleTarget {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !dobot_msgs__msg__CircleTarget__init(&mut msg as *mut _) {
        panic!("Call to dobot_msgs__msg__CircleTarget__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for CircleTarget {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__CircleTarget__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__CircleTarget__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__CircleTarget__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for CircleTarget {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for CircleTarget where Self: Sized {
  const TYPE_NAME: &'static str = "dobot_msgs/msg/CircleTarget";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__CircleTarget() }
  }
}


#[link(name = "dobot_msgs__rosidl_typesupport_c")]
extern "C" {
    fn rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__CircleTargetArray() -> *const std::ffi::c_void;
}

#[link(name = "dobot_msgs__rosidl_generator_c")]
extern "C" {
    fn dobot_msgs__msg__CircleTargetArray__init(msg: *mut CircleTargetArray) -> bool;
    fn dobot_msgs__msg__CircleTargetArray__Sequence__init(seq: *mut rosidl_runtime_rs::Sequence<CircleTargetArray>, size: usize) -> bool;
    fn dobot_msgs__msg__CircleTargetArray__Sequence__fini(seq: *mut rosidl_runtime_rs::Sequence<CircleTargetArray>);
    fn dobot_msgs__msg__CircleTargetArray__Sequence__copy(in_seq: &rosidl_runtime_rs::Sequence<CircleTargetArray>, out_seq: *mut rosidl_runtime_rs::Sequence<CircleTargetArray>) -> bool;
}

// Corresponds to dobot_msgs__msg__CircleTargetArray
#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]

/// RGB exposure stamp and registered optical frame; never the processing time.

#[repr(C)]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct CircleTargetArray {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::rmw::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub valid: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub reason: rosidl_runtime_rs::String,

    /// Unit normal faces the camera; n dot camera_xyz + d = 0, metres.
    pub table_plane: [f64; 4],


    // This member is not documented.
    #[allow(missing_docs)]
    pub table_inlier_ratio: f64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub table_rmse: f64,


    // This member is not documented.
    #[allow(missing_docs)]
    pub detections: rosidl_runtime_rs::Sequence<super::super::msg::rmw::CircleTarget>,

}



impl Default for CircleTargetArray {
  fn default() -> Self {
    unsafe {
      let mut msg = std::mem::zeroed();
      if !dobot_msgs__msg__CircleTargetArray__init(&mut msg as *mut _) {
        panic!("Call to dobot_msgs__msg__CircleTargetArray__init() failed");
      }
      msg
    }
  }
}

impl rosidl_runtime_rs::SequenceAlloc for CircleTargetArray {
  fn sequence_init(seq: &mut rosidl_runtime_rs::Sequence<Self>, size: usize) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__CircleTargetArray__Sequence__init(seq as *mut _, size) }
  }
  fn sequence_fini(seq: &mut rosidl_runtime_rs::Sequence<Self>) {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__CircleTargetArray__Sequence__fini(seq as *mut _) }
  }
  fn sequence_copy(in_seq: &rosidl_runtime_rs::Sequence<Self>, out_seq: &mut rosidl_runtime_rs::Sequence<Self>) -> bool {
    // SAFETY: This is safe since the pointer is guaranteed to be valid/initialized.
    unsafe { dobot_msgs__msg__CircleTargetArray__Sequence__copy(in_seq, out_seq as *mut _) }
  }
}

impl rosidl_runtime_rs::Message for CircleTargetArray {
  type RmwMsg = Self;
  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> { msg_cow }
  fn from_rmw_message(msg: Self::RmwMsg) -> Self { msg }
}

impl rosidl_runtime_rs::RmwMessage for CircleTargetArray where Self: Sized {
  const TYPE_NAME: &'static str = "dobot_msgs/msg/CircleTargetArray";
  fn get_type_support() -> *const std::ffi::c_void {
    // SAFETY: No preconditions for this function.
    unsafe { rosidl_typesupport_c__get_message_type_support_handle__dobot_msgs__msg__CircleTargetArray() }
  }
}


