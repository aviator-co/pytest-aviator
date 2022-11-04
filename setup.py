from os.path import dirname, join

from setuptools import setup

CLASSIFIERS = [
    "Development Status :: 4 - Beta",
    "Intended Audience :: Developers",
    "Topic :: Software Development :: Testing",
    "Programming Language :: Python",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.5",
    "Programming Language :: Python :: 3.6",
    "Programming Language :: Python :: 3.7",
    "Programming Language :: Python :: 3.8",
]

with open("README.md", "r") as f:
    readme = f.read()


def main():
    setup(
        name="pytest-aviator",
        version="0.1.1",
        license="MIT",
        description="Aviator\'s Flakybot pytest plugin that automatically reruns flaky tests.",
        long_description=readme,
        long_description_content_type="text/markdown",
        author="aviator-co",
        author_email="engineering@aviator.co",
        url="https://github.com/aviator-co/pytest-aviator",
        entry_points={
            "pytest11": [
                "pytest-aviator = pytest_aviator.runner"
            ]
        },
        keywords="pytest plugin flaky tests rerun retry flakybot aviator",
        python_requires=">=3.6",
        classifiers=CLASSIFIERS,
        install_requires=[
            "pytest",
            "requests"
        ]
    )


if __name__ == "__main__":
    main()
