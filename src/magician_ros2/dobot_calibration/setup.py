from setuptools import setup

setup(
    name='dobot_calibration',
    version='0.1.0',
    packages=['dobot_calibration'],
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/dobot_calibration']),
        ('share/dobot_calibration', ['package.xml', 'README.md']),
        ('share/dobot_calibration/config', [
            'config/calibration.yaml', 'config/mount_model.yaml',
            'config/carrier_mount.example.yaml',
        ]),
        ('share/dobot_calibration/launch', ['launch/markerless_calibration.launch.py']),
    ],
    install_requires=['setuptools', 'numpy', 'scipy', 'PyYAML'],
    zip_safe=True,
    maintainer='bbcontact',
    maintainer_email='bbcontact@users.noreply.github.com',
    description='Automatic markerless RGB-D calibration for the Dobot Magician.',
    license='MIT',
    entry_points={'console_scripts': [
        'markerless_calibration = dobot_calibration.node:main',
    ]},
)
