#[cfg(feature = "serde")]
use serde::{Deserialize, Serialize};



// Corresponds to dobot_msgs__msg__DobotAlarmCodes

// This struct is not documented.
#[allow(missing_docs)]

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct DobotAlarmCodes {
    /// for timestamp
    pub header: std_msgs::msg::Header,

    /// list of alarm codes as hex values
    pub alarms_list: Vec<i32>,

}



impl Default for DobotAlarmCodes {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::DobotAlarmCodes::default())
  }
}

impl rosidl_runtime_rs::Message for DobotAlarmCodes {
  type RmwMsg = super::msg::rmw::DobotAlarmCodes;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        alarms_list: msg.alarms_list.as_slice().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
        alarms_list: msg.alarms_list.as_slice().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      alarms_list: msg.alarms_list.into(),
    }
  }
}


// Corresponds to dobot_msgs__msg__GripperStatus

// This struct is not documented.
#[allow(missing_docs)]

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct GripperStatus {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::Header,

    /// either opened or closed
    pub status: std::string::String,

}



impl Default for GripperStatus {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::GripperStatus::default())
  }
}

impl rosidl_runtime_rs::Message for GripperStatus {
  type RmwMsg = super::msg::rmw::GripperStatus;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        status: msg.status.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
        status: msg.status.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      status: msg.status.to_string(),
    }
  }
}


// Corresponds to dobot_msgs__msg__CircleTarget
/// ID is local to this exposure; identify a target by (array header stamp, id).

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct CircleTarget {

    // This member is not documented.
    #[allow(missing_docs)]
    pub id: u32,

    /// black, white or yellow
    pub class_name: std::string::String,


    // This member is not documented.
    #[allow(missing_docs)]
    pub center_uv: [f64; 2],

    /// Metres, in the array header's registered optical frame.
    pub camera_xyz: geometry_msgs::msg::Point,

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
    pub rejection_reason: std::string::String,

}



impl Default for CircleTarget {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::CircleTarget::default())
  }
}

impl rosidl_runtime_rs::Message for CircleTarget {
  type RmwMsg = super::msg::rmw::CircleTarget;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        id: msg.id,
        class_name: msg.class_name.as_str().into(),
        center_uv: msg.center_uv,
        camera_xyz: geometry_msgs::msg::Point::into_rmw_message(std::borrow::Cow::Owned(msg.camera_xyz)).into_owned(),
        depth: msg.depth,
        size: msg.size,
        confidence: msg.confidence,
        pickable: msg.pickable,
        top_height: msg.top_height,
        depth_valid_ratio: msg.depth_valid_ratio,
        depth_mad: msg.depth_mad,
        rejection_reason: msg.rejection_reason.as_str().into(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
      id: msg.id,
        class_name: msg.class_name.as_str().into(),
        center_uv: msg.center_uv,
        camera_xyz: geometry_msgs::msg::Point::into_rmw_message(std::borrow::Cow::Borrowed(&msg.camera_xyz)).into_owned(),
      depth: msg.depth,
      size: msg.size,
      confidence: msg.confidence,
      pickable: msg.pickable,
      top_height: msg.top_height,
      depth_valid_ratio: msg.depth_valid_ratio,
      depth_mad: msg.depth_mad,
        rejection_reason: msg.rejection_reason.as_str().into(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      id: msg.id,
      class_name: msg.class_name.to_string(),
      center_uv: msg.center_uv,
      camera_xyz: geometry_msgs::msg::Point::from_rmw_message(msg.camera_xyz),
      depth: msg.depth,
      size: msg.size,
      confidence: msg.confidence,
      pickable: msg.pickable,
      top_height: msg.top_height,
      depth_valid_ratio: msg.depth_valid_ratio,
      depth_mad: msg.depth_mad,
      rejection_reason: msg.rejection_reason.to_string(),
    }
  }
}


// Corresponds to dobot_msgs__msg__CircleTargetArray
/// RGB exposure stamp and registered optical frame; never the processing time.

#[cfg_attr(feature = "serde", derive(Deserialize, Serialize))]
#[derive(Clone, Debug, PartialEq, PartialOrd)]
pub struct CircleTargetArray {

    // This member is not documented.
    #[allow(missing_docs)]
    pub header: std_msgs::msg::Header,


    // This member is not documented.
    #[allow(missing_docs)]
    pub valid: bool,


    // This member is not documented.
    #[allow(missing_docs)]
    pub reason: std::string::String,

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
    pub detections: Vec<super::msg::CircleTarget>,

}



impl Default for CircleTargetArray {
  fn default() -> Self {
    <Self as rosidl_runtime_rs::Message>::from_rmw_message(super::msg::rmw::CircleTargetArray::default())
  }
}

impl rosidl_runtime_rs::Message for CircleTargetArray {
  type RmwMsg = super::msg::rmw::CircleTargetArray;

  fn into_rmw_message(msg_cow: std::borrow::Cow<'_, Self>) -> std::borrow::Cow<'_, Self::RmwMsg> {
    match msg_cow {
      std::borrow::Cow::Owned(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Owned(msg.header)).into_owned(),
        valid: msg.valid,
        reason: msg.reason.as_str().into(),
        table_plane: msg.table_plane,
        table_inlier_ratio: msg.table_inlier_ratio,
        table_rmse: msg.table_rmse,
        detections: msg.detections
          .into_iter()
          .map(|elem| super::msg::CircleTarget::into_rmw_message(std::borrow::Cow::Owned(elem)).into_owned())
          .collect(),
      }),
      std::borrow::Cow::Borrowed(msg) => std::borrow::Cow::Owned(Self::RmwMsg {
        header: std_msgs::msg::Header::into_rmw_message(std::borrow::Cow::Borrowed(&msg.header)).into_owned(),
      valid: msg.valid,
        reason: msg.reason.as_str().into(),
        table_plane: msg.table_plane,
      table_inlier_ratio: msg.table_inlier_ratio,
      table_rmse: msg.table_rmse,
        detections: msg.detections
          .iter()
          .map(|elem| super::msg::CircleTarget::into_rmw_message(std::borrow::Cow::Borrowed(elem)).into_owned())
          .collect(),
      })
    }
  }

  fn from_rmw_message(msg: Self::RmwMsg) -> Self {
    Self {
      header: std_msgs::msg::Header::from_rmw_message(msg.header),
      valid: msg.valid,
      reason: msg.reason.to_string(),
      table_plane: msg.table_plane,
      table_inlier_ratio: msg.table_inlier_ratio,
      table_rmse: msg.table_rmse,
      detections: msg.detections
          .into_iter()
          .map(super::msg::CircleTarget::from_rmw_message)
          .collect(),
    }
  }
}


