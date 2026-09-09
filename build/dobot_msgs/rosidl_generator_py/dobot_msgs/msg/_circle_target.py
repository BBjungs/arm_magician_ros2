# generated from rosidl_generator_py/resource/_idl.py.em
# with input from dobot_msgs:msg/CircleTarget.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

import builtins  # noqa: E402, I100

import math  # noqa: E402, I100

# Member 'center_uv'
import numpy  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_CircleTarget(type):
    """Metaclass of message 'CircleTarget'."""

    _CREATE_ROS_MESSAGE = None
    _CONVERT_FROM_PY = None
    _CONVERT_TO_PY = None
    _DESTROY_ROS_MESSAGE = None
    _TYPE_SUPPORT = None

    __constants = {
    }

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('dobot_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'dobot_msgs.msg.CircleTarget')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__msg__circle_target
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__msg__circle_target
            cls._CONVERT_TO_PY = module.convert_to_py_msg__msg__circle_target
            cls._TYPE_SUPPORT = module.type_support_msg__msg__circle_target
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__msg__circle_target

            from geometry_msgs.msg import Point
            if Point.__class__._TYPE_SUPPORT is None:
                Point.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class CircleTarget(metaclass=Metaclass_CircleTarget):
    """Message class 'CircleTarget'."""

    __slots__ = [
        '_id',
        '_class_name',
        '_center_uv',
        '_camera_xyz',
        '_depth',
        '_size',
        '_confidence',
        '_pickable',
        '_top_height',
        '_depth_valid_ratio',
        '_depth_mad',
        '_rejection_reason',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'id': 'uint32',
        'class_name': 'string',
        'center_uv': 'double[2]',
        'camera_xyz': 'geometry_msgs/Point',
        'depth': 'double',
        'size': 'double',
        'confidence': 'double',
        'pickable': 'boolean',
        'top_height': 'double',
        'depth_valid_ratio': 'double',
        'depth_mad': 'double',
        'rejection_reason': 'string',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('uint32'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('double'), 2),  # noqa: E501
        rosidl_parser.definition.NamespacedType(['geometry_msgs', 'msg'], 'Point'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
    )

    def __init__(self, **kwargs):
        if 'check_fields' in kwargs:
            self._check_fields = kwargs['check_fields']
        else:
            self._check_fields = ros_python_check_fields == '1'
        if self._check_fields:
            assert all('_' + key in self.__slots__ for key in kwargs.keys()), \
                'Invalid arguments passed to constructor: %s' % \
                ', '.join(sorted(k for k in kwargs.keys() if '_' + k not in self.__slots__))
        self.id = kwargs.get('id', int())
        self.class_name = kwargs.get('class_name', str())
        if 'center_uv' not in kwargs:
            self.center_uv = numpy.zeros(2, dtype=numpy.float64)
        else:
            self.center_uv = kwargs.get('center_uv')
        from geometry_msgs.msg import Point
        self.camera_xyz = kwargs.get('camera_xyz', Point())
        self.depth = kwargs.get('depth', float())
        self.size = kwargs.get('size', float())
        self.confidence = kwargs.get('confidence', float())
        self.pickable = kwargs.get('pickable', bool())
        self.top_height = kwargs.get('top_height', float())
        self.depth_valid_ratio = kwargs.get('depth_valid_ratio', float())
        self.depth_mad = kwargs.get('depth_mad', float())
        self.rejection_reason = kwargs.get('rejection_reason', str())

    def __repr__(self):
        typename = self.__class__.__module__.split('.')
        typename.pop()
        typename.append(self.__class__.__name__)
        args = []
        for s, t in zip(self.get_fields_and_field_types().keys(), self.SLOT_TYPES):
            field = getattr(self, s)
            fieldstr = repr(field)
            # We use Python array type for fields that can be directly stored
            # in them, and "normal" sequences for everything else.  If it is
            # a type that we store in an array, strip off the 'array' portion.
            if (
                isinstance(t, rosidl_parser.definition.AbstractSequence) and
                isinstance(t.value_type, rosidl_parser.definition.BasicType) and
                t.value_type.typename in ['float', 'double', 'int8', 'uint8', 'int16', 'uint16', 'int32', 'uint32', 'int64', 'uint64']
            ):
                if len(field) == 0:
                    fieldstr = '[]'
                else:
                    if self._check_fields:
                        assert fieldstr.startswith('array(')
                    prefix = "array('X', "
                    suffix = ')'
                    fieldstr = fieldstr[len(prefix):-len(suffix)]
            args.append(s + '=' + fieldstr)
        return '%s(%s)' % ('.'.join(typename), ', '.join(args))

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        if self.id != other.id:
            return False
        if self.class_name != other.class_name:
            return False
        if any(self.center_uv != other.center_uv):
            return False
        if self.camera_xyz != other.camera_xyz:
            return False
        if self.depth != other.depth:
            return False
        if self.size != other.size:
            return False
        if self.confidence != other.confidence:
            return False
        if self.pickable != other.pickable:
            return False
        if self.top_height != other.top_height:
            return False
        if self.depth_valid_ratio != other.depth_valid_ratio:
            return False
        if self.depth_mad != other.depth_mad:
            return False
        if self.rejection_reason != other.rejection_reason:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property  # noqa: A003
    def id(self):  # noqa: A003
        """Message field 'id'."""
        return self._id

    @id.setter  # noqa: A003
    def id(self, value):  # noqa: A003
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'id' field must be of type 'int'"
            assert value >= 0 and value < 4294967296, \
                "The 'id' field must be an unsigned integer in [0, 4294967295]"
        self._id = value

    @builtins.property
    def class_name(self):
        """Message field 'class_name'."""
        return self._class_name

    @class_name.setter
    def class_name(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'class_name' field must be of type 'str'"
        self._class_name = value

    @builtins.property
    def center_uv(self):
        """Message field 'center_uv'."""
        return self._center_uv

    @center_uv.setter
    def center_uv(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.float64, \
                    "The 'center_uv' numpy.ndarray() must have the dtype of 'numpy.float64'"
                assert value.size == 2, \
                    "The 'center_uv' numpy.ndarray() must have a size of 2"
                self._center_uv = value
                return
            from collections.abc import Sequence
            from collections.abc import Set
            from collections import UserList
            from collections import UserString
            assert \
                ((isinstance(value, Sequence) or
                  isinstance(value, Set) or
                  isinstance(value, UserList)) and
                 not isinstance(value, str) and
                 not isinstance(value, UserString) and
                 len(value) == 2 and
                 all(isinstance(v, float) for v in value) and
                 all(not (val < -1.7976931348623157e+308 or val > 1.7976931348623157e+308) or math.isinf(val) for val in value)), \
                "The 'center_uv' field must be a set or sequence with length 2 and each value of type 'float' and each double in [-179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000, 179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000]"
        self._center_uv = numpy.array(value, dtype=numpy.float64)

    @builtins.property
    def camera_xyz(self):
        """Message field 'camera_xyz'."""
        return self._camera_xyz

    @camera_xyz.setter
    def camera_xyz(self, value):
        if self._check_fields:
            from geometry_msgs.msg import Point
            assert \
                isinstance(value, Point), \
                "The 'camera_xyz' field must be a sub message of type 'Point'"
        self._camera_xyz = value

    @builtins.property
    def depth(self):
        """Message field 'depth'."""
        return self._depth

    @depth.setter
    def depth(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'depth' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'depth' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._depth = value

    @builtins.property
    def size(self):
        """Message field 'size'."""
        return self._size

    @size.setter
    def size(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'size' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'size' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._size = value

    @builtins.property
    def confidence(self):
        """Message field 'confidence'."""
        return self._confidence

    @confidence.setter
    def confidence(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'confidence' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'confidence' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._confidence = value

    @builtins.property
    def pickable(self):
        """Message field 'pickable'."""
        return self._pickable

    @pickable.setter
    def pickable(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'pickable' field must be of type 'bool'"
        self._pickable = value

    @builtins.property
    def top_height(self):
        """Message field 'top_height'."""
        return self._top_height

    @top_height.setter
    def top_height(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'top_height' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'top_height' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._top_height = value

    @builtins.property
    def depth_valid_ratio(self):
        """Message field 'depth_valid_ratio'."""
        return self._depth_valid_ratio

    @depth_valid_ratio.setter
    def depth_valid_ratio(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'depth_valid_ratio' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'depth_valid_ratio' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._depth_valid_ratio = value

    @builtins.property
    def depth_mad(self):
        """Message field 'depth_mad'."""
        return self._depth_mad

    @depth_mad.setter
    def depth_mad(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'depth_mad' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'depth_mad' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._depth_mad = value

    @builtins.property
    def rejection_reason(self):
        """Message field 'rejection_reason'."""
        return self._rejection_reason

    @rejection_reason.setter
    def rejection_reason(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'rejection_reason' field must be of type 'str'"
        self._rejection_reason = value
