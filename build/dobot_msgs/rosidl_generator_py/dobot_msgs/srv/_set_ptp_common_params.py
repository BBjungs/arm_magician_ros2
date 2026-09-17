# generated from rosidl_generator_py/resource/_idl.py.em
# with input from dobot_msgs:srv/SetPTPCommonParams.idl
# generated code does not contain a copyright notice

# This is being done at the module level and not on the instance level to avoid looking
# for the same variable multiple times on each instance. This variable is not supposed to
# change during runtime so it makes sense to only look for it once.
from os import getenv

ros_python_check_fields = getenv('ROS_PYTHON_CHECK_FIELDS', default='')


# Import statements for member types

import builtins  # noqa: E402, I100

import rosidl_parser.definition  # noqa: E402, I100


class Metaclass_SetPTPCommonParams_Request(type):
    """Metaclass of message 'SetPTPCommonParams_Request'."""

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
                'dobot_msgs.srv.SetPTPCommonParams_Request')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__set_ptp_common_params__request
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__set_ptp_common_params__request
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__set_ptp_common_params__request
            cls._TYPE_SUPPORT = module.type_support_msg__srv__set_ptp_common_params__request
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__set_ptp_common_params__request

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class SetPTPCommonParams_Request(metaclass=Metaclass_SetPTPCommonParams_Request):
    """Message class 'SetPTPCommonParams_Request'."""

    __slots__ = [
        '_velocity_percent',
        '_acceleration_percent',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'velocity_percent': 'uint8',
        'acceleration_percent': 'uint8',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
        rosidl_parser.definition.BasicType('uint8'),  # noqa: E501
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
        self.velocity_percent = kwargs.get('velocity_percent', int())
        self.acceleration_percent = kwargs.get('acceleration_percent', int())

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
        if self.velocity_percent != other.velocity_percent:
            return False
        if self.acceleration_percent != other.acceleration_percent:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def velocity_percent(self):
        """Message field 'velocity_percent'."""
        return self._velocity_percent

    @velocity_percent.setter
    def velocity_percent(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'velocity_percent' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'velocity_percent' field must be an unsigned integer in [0, 255]"
        self._velocity_percent = value

    @builtins.property
    def acceleration_percent(self):
        """Message field 'acceleration_percent'."""
        return self._acceleration_percent

    @acceleration_percent.setter
    def acceleration_percent(self, value):
        if self._check_fields:
            assert \
                isinstance(value, int), \
                "The 'acceleration_percent' field must be of type 'int'"
            assert value >= 0 and value < 256, \
                "The 'acceleration_percent' field must be an unsigned integer in [0, 255]"
        self._acceleration_percent = value


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_SetPTPCommonParams_Response(type):
    """Metaclass of message 'SetPTPCommonParams_Response'."""

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
                'dobot_msgs.srv.SetPTPCommonParams_Response')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__set_ptp_common_params__response
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__set_ptp_common_params__response
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__set_ptp_common_params__response
            cls._TYPE_SUPPORT = module.type_support_msg__srv__set_ptp_common_params__response
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__set_ptp_common_params__response

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class SetPTPCommonParams_Response(metaclass=Metaclass_SetPTPCommonParams_Response):
    """Message class 'SetPTPCommonParams_Response'."""

    __slots__ = [
        '_success',
        '_acknowledged',
        '_timed_out',
        '_error',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'success': 'boolean',
        'acknowledged': 'boolean',
        'timed_out': 'boolean',
        'error': 'string',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
        rosidl_parser.definition.BasicType('boolean'),  # noqa: E501
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
        self.success = kwargs.get('success', bool())
        self.acknowledged = kwargs.get('acknowledged', bool())
        self.timed_out = kwargs.get('timed_out', bool())
        self.error = kwargs.get('error', str())

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
        if self.success != other.success:
            return False
        if self.acknowledged != other.acknowledged:
            return False
        if self.timed_out != other.timed_out:
            return False
        if self.error != other.error:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def success(self):
        """Message field 'success'."""
        return self._success

    @success.setter
    def success(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'success' field must be of type 'bool'"
        self._success = value

    @builtins.property
    def acknowledged(self):
        """Message field 'acknowledged'."""
        return self._acknowledged

    @acknowledged.setter
    def acknowledged(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'acknowledged' field must be of type 'bool'"
        self._acknowledged = value

    @builtins.property
    def timed_out(self):
        """Message field 'timed_out'."""
        return self._timed_out

    @timed_out.setter
    def timed_out(self, value):
        if self._check_fields:
            assert \
                isinstance(value, bool), \
                "The 'timed_out' field must be of type 'bool'"
        self._timed_out = value

    @builtins.property
    def error(self):
        """Message field 'error'."""
        return self._error

    @error.setter
    def error(self, value):
        if self._check_fields:
            assert \
                isinstance(value, str), \
                "The 'error' field must be of type 'str'"
        self._error = value


# Import statements for member types

# already imported above
# import builtins

# already imported above
# import rosidl_parser.definition


class Metaclass_SetPTPCommonParams_Event(type):
    """Metaclass of message 'SetPTPCommonParams_Event'."""

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
                'dobot_msgs.srv.SetPTPCommonParams_Event')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._CREATE_ROS_MESSAGE = module.create_ros_message_msg__srv__set_ptp_common_params__event
            cls._CONVERT_FROM_PY = module.convert_from_py_msg__srv__set_ptp_common_params__event
            cls._CONVERT_TO_PY = module.convert_to_py_msg__srv__set_ptp_common_params__event
            cls._TYPE_SUPPORT = module.type_support_msg__srv__set_ptp_common_params__event
            cls._DESTROY_ROS_MESSAGE = module.destroy_ros_message_msg__srv__set_ptp_common_params__event

            from service_msgs.msg import ServiceEventInfo
            if ServiceEventInfo.__class__._TYPE_SUPPORT is None:
                ServiceEventInfo.__class__.__import_type_support__()

    @classmethod
    def __prepare__(cls, name, bases, **kwargs):
        # list constant names here so that they appear in the help text of
        # the message class under "Data and other attributes defined here:"
        # as well as populate each message instance
        return {
        }


class SetPTPCommonParams_Event(metaclass=Metaclass_SetPTPCommonParams_Event):
    """Message class 'SetPTPCommonParams_Event'."""

    __slots__ = [
        '_info',
        '_request',
        '_response',
        '_check_fields',
    ]

    _fields_and_field_types = {
        'info': 'service_msgs/ServiceEventInfo',
        'request': 'sequence<dobot_msgs/SetPTPCommonParams_Request, 1>',
        'response': 'sequence<dobot_msgs/SetPTPCommonParams_Response, 1>',
    }

    # This attribute is used to store an rosidl_parser.definition variable
    # related to the data type of each of the components the message.
    SLOT_TYPES = (
        rosidl_parser.definition.NamespacedType(['service_msgs', 'msg'], 'ServiceEventInfo'),  # noqa: E501
        rosidl_parser.definition.BoundedSequence(rosidl_parser.definition.NamespacedType(['dobot_msgs', 'srv'], 'SetPTPCommonParams_Request'), 1),  # noqa: E501
        rosidl_parser.definition.BoundedSequence(rosidl_parser.definition.NamespacedType(['dobot_msgs', 'srv'], 'SetPTPCommonParams_Response'), 1),  # noqa: E501
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
        from service_msgs.msg import ServiceEventInfo
        self.info = kwargs.get('info', ServiceEventInfo())
        self.request = kwargs.get('request', [])
        self.response = kwargs.get('response', [])

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
        if self.info != other.info:
            return False
        if self.request != other.request:
            return False
        if self.response != other.response:
            return False
        return True

    @classmethod
    def get_fields_and_field_types(cls):
        from copy import copy
        return copy(cls._fields_and_field_types)

    @builtins.property
    def info(self):
        """Message field 'info'."""
        return self._info

    @info.setter
    def info(self, value):
        if self._check_fields:
            from service_msgs.msg import ServiceEventInfo
            assert \
                isinstance(value, ServiceEventInfo), \
                "The 'info' field must be a sub message of type 'ServiceEventInfo'"
        self._info = value

    @builtins.property
    def request(self):
        """Message field 'request'."""
        return self._request

    @request.setter
    def request(self, value):
        if self._check_fields:
            from dobot_msgs.srv import SetPTPCommonParams_Request
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
                 len(value) <= 1 and
                 all(isinstance(v, SetPTPCommonParams_Request) for v in value) and
                 True), \
                "The 'request' field must be a set or sequence with length <= 1 and each value of type 'SetPTPCommonParams_Request'"
        self._request = value

    @builtins.property
    def response(self):
        """Message field 'response'."""
        return self._response

    @response.setter
    def response(self, value):
        if self._check_fields:
            from dobot_msgs.srv import SetPTPCommonParams_Response
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
                 len(value) <= 1 and
                 all(isinstance(v, SetPTPCommonParams_Response) for v in value) and
                 True), \
                "The 'response' field must be a set or sequence with length <= 1 and each value of type 'SetPTPCommonParams_Response'"
        self._response = value


class Metaclass_SetPTPCommonParams(type):
    """Metaclass of service 'SetPTPCommonParams'."""

    _TYPE_SUPPORT = None

    @classmethod
    def __import_type_support__(cls):
        try:
            from rosidl_generator_py import import_type_support
            module = import_type_support('dobot_msgs')
        except ImportError:
            import logging
            import traceback
            logger = logging.getLogger(
                'dobot_msgs.srv.SetPTPCommonParams')
            logger.debug(
                'Failed to import needed modules for type support:\n' +
                traceback.format_exc())
        else:
            cls._TYPE_SUPPORT = module.type_support_srv__srv__set_ptp_common_params

            from dobot_msgs.srv import _set_ptp_common_params
            if _set_ptp_common_params.Metaclass_SetPTPCommonParams_Request._TYPE_SUPPORT is None:
                _set_ptp_common_params.Metaclass_SetPTPCommonParams_Request.__import_type_support__()
            if _set_ptp_common_params.Metaclass_SetPTPCommonParams_Response._TYPE_SUPPORT is None:
                _set_ptp_common_params.Metaclass_SetPTPCommonParams_Response.__import_type_support__()
            if _set_ptp_common_params.Metaclass_SetPTPCommonParams_Event._TYPE_SUPPORT is None:
                _set_ptp_common_params.Metaclass_SetPTPCommonParams_Event.__import_type_support__()


class SetPTPCommonParams(metaclass=Metaclass_SetPTPCommonParams):
    from dobot_msgs.srv._set_ptp_common_params import SetPTPCommonParams_Request as Request
    from dobot_msgs.srv._set_ptp_common_params import SetPTPCommonParams_Response as Response
    from dobot_msgs.srv._set_ptp_common_params import SetPTPCommonParams_Event as Event

    def __init__(self):
        raise NotImplementedError('Service classes can not be instantiated')
