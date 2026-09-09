import os
from glob import glob
from setuptools import setup

package_name = 'dobot_vision_rgbd'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='bbcontact',
    maintainer_email='bbcontact@example.com',
    description='Rule-based RGB-D object detector for Dobot Magician.',
    license='MIT',
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'object_fusion_node = dobot_vision_rgbd.object_fusion_node:main',
        'camera_health_node = dobot_vision_rgbd.camera_health_node:main',
    ]},
)
