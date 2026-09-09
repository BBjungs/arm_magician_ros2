# generated from rosidl_generator_py/resource/_idl.py.em
# with input from dobot_msgs:msg/CircleTargetArray.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

import builtins  # noqa: E402, I100

import math  # noqa: E402, I100

# Member 'table_plane'
import numpy  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_CircleTargetArray(type):
    """Metaclass of message 'CircleTargetArray'."""

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
                'dobot_msgs.msg.CircleTargetArray')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__msg__circle_target_array
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__msg__circle_target_array
            cls._CONVERT_TO_PY = module.convert_to_py_msg__msg__circle_target_array
            cls._TYPE_SUPPORT = module.type_support_msg__msg__circle_target_array
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__msg__circle_target_array

            from dobot_msgs.msg import CircleTarget
            if CircleTarget.__class__._TYPE_SUPPORT is None:
                CircleTarget.__class__.__import_type_support__()

            from std_msgs.msg import Header
            if Header.__class__._TYPE_SUPPORT is None:
                Header.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class CircleTargetArray(metaclass=Metaclass_CircleTargetArray):
    """Message class 'CircleTargetArray'."""

    __slots__ = [
        '_header',
        '_valid',
        '_reason',
        '_table_plane',
        '_table_inlier_ratio',
        '_table_rmse',
        '_detections',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'header': 'std_msgs/Header',
        'valid': 'boolean',
        'reason': 'string',
        'table_plane': 'double[4]',
        'table_inlier_ratio': 'double',
        'table_rmse': 'double',
        'detections': 'sequence<dobot_msgs/CircleTarget>',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['std_msgs', 'msg'], 'Header'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.UnboundedString(),  # noqa: E501
        rosidl_parser.definition.Array(rosidl_parser.definition.BasicType('double'), 4),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.BasicType('double'),  # noqa: E501
        rosidl_parser.definition.UnboundedSequence(rosidl_parser.definition.NamespacedType(['dobot_msgs', 'msg'], 'CircleTarget')),  # noqa: E501
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
        from std_msgs.msg import Header
        self.header = kwargs.get('header', Header())
        self.valid = kwargs.get('valid', bool())
        self.reason = kwargs.get('reason', str())
        if 'table_plane' not in kwargs:
            self.table_plane = numpy.zeros(4, dtype=numpy.float64)
        else:
            self.table_plane = kwargs.get('table_plane')
        self.table_inlier_ratio = kwargs.get('table_inlier_ratio', float())
        self.table_rmse = kwargs.get('table_rmse', float())
        self.detections = kwargs.get('detections', [])

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
        if self.header != other.header:
            return False
        if self.valid != other.valid:
            return False
        if self.reason != other.reason:
            return False
        if any(self.table_plane != other.table_plane):
            return False
        if self.table_inlier_ratio != other.table_inlier_ratio:
            return False
        if self.table_rmse != other.table_rmse:
            return False
        if self.detections != other.detections:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def header(self):
        """Message field 'header'."""
        return self._header

    @header.setter
    def header(self, value):
        if self._check_fields:
            from std_msgs.msg import Header
            assert \
                isinstance(value, Header), \
                "The 'header' field must be a sub message of type 'Header'"
        self._header = value

    @builtins.property
    def valid(self):
        """Message field 'valid'."""
        return self._valid

    @valid.setter
    def valid(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'valid' field must be of type 'bool'"
        self._valid = value

    @builtins.property
    def reason(self):
        """Message field 'reason'."""
        return self._reason

    @reason.setter
    def reason(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'reason' field must be of type 'str'"
        self._reason = value

    @builtins.property
    def table_plane(self):
        """Message field 'table_plane'."""
        return self._table_plane

    @table_plane.setter
    def table_plane(self, value):
        if self._check_fields:
            if isinstance(value, numpy.ndarray):
                assert value.dtype == numpy.float64, \
                    "The 'table_plane' numpy.ndarray() must have the dtype of 'numpy.float64'"
                assert value.size == 4, \
                    "The 'table_plane' numpy.ndarray() must have a size of 4"
                self._table_plane = value
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
                 len(value) == 4 and
                 all(isinstance(v, float) for v in value) and
                 all(not (val < -1.7976931348623157e+308 or val > 1.7976931348623157e+308) or math.isinf(val) for val in value)), \
                "The 'table_plane' field must be a set or sequence with length 4 and each value of type 'float' and each double in [-179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000, 179769313486231570814527423731704356798070567525844996598917476803157260780028538760589558632766878171540458953514382464234321326889464182768467546703537516986049910576551282076245490090389328944075868508455133942304583236903222948165808559332123348274797826204144723168738177180919299881250404026184124858368.000000]"
        self._table_plane = numpy.array(value, dtype=numpy.float64)

    @builtins.property
    def table_inlier_ratio(self):
        """Message field 'table_inlier_ratio'."""
        return self._table_inlier_ratio

    @table_inlier_ratio.setter
    def table_inlier_ratio(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'table_inlier_ratio' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'table_inlier_ratio' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._table_inlier_ratio = value

    @builtins.property
    def table_rmse(self):
        """Message field 'table_rmse'."""
        return self._table_rmse

    @table_rmse.setter
    def table_rmse(self, value):
        if self._check_fields:
            assert \
                isinstance(value, float), \
                "The 'table_rmse' field must be of type 'float'"
            assert not (value < -1.7976931348623157e+308 or value > 1.7976931348623157e+308) or math.isinf(value), \
                "The 'table_rmse' field must be a double in [-1.7976931348623157e+308, 1.7976931348623157e+308]"
        self._table_rmse = value

    @builtins.property
    def detections(self):
        """Message field 'detections'."""
        return self._detections

    @detections.setter
    def detections(self, value):
        if self._check_fields:
            from dobot_msgs.msg import CircleTarget
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
                 all(isinstance(v, CircleTarget) for v in value) and
                 True), \
                "The 'detections' field must be a set or sequence and each value of type 'CircleTarget'"
        self._detections = value
