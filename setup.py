from setuptools import setup, find_packages
from os import path
from io import open

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='fiware-prometheus-publisher',
    version='0.0.40',
    description='Ceilometer Publisher for the FIWARE infrastructure',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/gabrielegiammatteo/fiware-prometheus-publisher',

    author='Gabriele Giammatteo',
    author_email='gabriele.giammatteo@eng.it',

    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Topic :: System :: Monitoring',
        'License :: OSI Approved :: Apache Software License',
        'Programming Language :: Python :: 2.7',
    ],

    keywords='monitoring ceilometer FIWARE metrics',

    packages=['ceilometer_fiprom'],

    python_requires='<3',

    entry_points = {
        'ceilometer.publisher': [
            'fiprom = ceilometer_fiprom.fiprom_publisher:PrometheusPublisher'
        ],
        'ceilometer.metering.storage': [
            'fiprom = ceilometer_fiprom.fiprom_storage:PrometheusStorage'
        ]
    },

   install_requires=[]


)