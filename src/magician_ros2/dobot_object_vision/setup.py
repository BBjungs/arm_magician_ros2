from glob import glob
from setuptools import setup

setup(
    name='dobot_object_vision', version='0.1.0', packages=['dobot_object_vision'],
    data_files=[('share/ament_index/resource_index/packages', ['resource/dobot_object_vision']),
                ('share/dobot_object_vision', ['package.xml', 'README.md']),
                ('share/dobot_object_vision/config', glob('config/*.yaml')),
                ('share/dobot_object_vision/launch', glob('launch/*.launch.py'))],
    install_requires=['setuptools', 'numpy', 'scipy'], zip_safe=True,
    maintainer='bbcontact', maintainer_email='bbcontact@users.noreply.github.com',
    description='Contour and depth based circular suction target vision.', license='MIT',
    entry_points={'console_scripts': ['circle_targets = dobot_object_vision.node:main']},
)
