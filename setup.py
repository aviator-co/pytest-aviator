from os.path import dirname, join

from setuptools import setup

CLASSIFIERS = [
    'Development Status :: 4 - Beta',
    'Intended Audience :: Developers',
    'Topic :: Software Development :: Testing',
    'Programming Language :: Python',
    'Programming Language :: Python :: 3',
    'Programming Language :: Python :: 3.5',
    'Programming Language :: Python :: 3.6',
    'Programming Language :: Python :: 3.7',
    'Programming Language :: Python :: 3.8',
]


def main():
    base_dir = dirname(__file__)
    setup(
        name='pytest-flakybot',
        version='0.1.1',
        description='Aviator\'s Flakybot pytest plugin that automatically reruns flaky tests.',
        long_description=open(join(base_dir, 'README.md')).read(),
        author='aviator-co',
        author_email='info@aviator.co',
        url='https://github.com/aviator-co/pytest-flakybot',
        entry_points={
            'pytest11': [
                'flakybot_pytest_runner = flakybot_pytest_runner.runner'
            ]
        },
        keywords='pytest plugin flaky tests rerun retry flakybot',
        python_requires='>=3.5',
        classifiers=CLASSIFIERS,
    )


if __name__ == '__main__':
    main()
