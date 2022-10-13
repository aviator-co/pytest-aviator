import os
import requests

from flakybot_pytest_runner.attributes import FlakyTestAttributes, DEFAULT_MIN_PASSES, DEFAULT_MAX_RUNS

AVIATOR_MARKER = "aviator"
BUILDKITE_JOB_PREFIX = "buildkite/"
CIRCLECI_JOB_PREFIX = "ci/circleci:"


class FlakybotRunner:
    runner = None
    API_URL = "https://api.aviator.co/api/v1/flaky-tests"
    flaky_tests = {}
    min_passes = DEFAULT_MIN_PASSES
    max_runs = DEFAULT_MAX_RUNS

    def __init__(self):
        super().__init__()
        self.get_flaky_tests()

    def pytest_configure(self, config):
        """
        Perform initial configuration. Include custom markers to avoid warnings.
        https://docs.pytest.org/en/7.1.x/how-to/writing_plugins.html#registering-custom-markers

        :param config: the pytest config object
        :return: None
        """
        self.runner = config.pluginmanager.getplugin("runner")

        config.addinivalue_line("markers", f"{AVIATOR_MARKER}: marks flaky tests for Flakybot to automatically rerun")

    def get_flaky_tests(self):
        """
        Get flaky test information from the Aviator API.

        :return: None
        """
        repo_name = None
        job_name = None

        # Get job and repo name
        if os.environ.get("CIRCLE_JOB"):
            # https://circleci.com/docs/2.0/env-vars/#built-in-environment-variables
            job_name = CIRCLECI_JOB_PREFIX + os.environ.get("CIRCLE_JOB", "")
            repo_name = "{username}/{repo_name}".format(
                username=os.environ.get("CIRCLE_PROJECT_USERNAME", ""),
                repo_name=os.environ.get("CIRCLE_PROJECT_REPONAME", "")
            )
        if os.environ.get("BUILDKITE_PIPELINE_SLUG"):
            # Note: BUILDKITE_REPO is in the format "git@github.com:{repo_name}.git"
            job_name = BUILDKITE_JOB_PREFIX + os.environ.get("BUILDKITE_PIPELINE_SLUG", "")
            repo_name = os.environ.get("BUILDKITE_REPO").replace("git@github.com:", "").replace(".git", "")

        # Fetch flaky test info
        self.API_URL = os.environ.get("AVIATOR_API_URL") or self.API_URL
        API_TOKEN = os.environ.get("AVIATOR_API_TOKEN", "")
        headers = {
            "Authorization": "Bearer " + API_TOKEN,
            "Content-Type": "application/json"
        }
        params = {"repo_name": repo_name, "job_name": job_name}
        response = requests.get(self.API_URL, headers=headers, params=params).json()
        av_flaky_tests = response.get("flaky_tests", [])

        for test in av_flaky_tests:
            if test.get("test_name", ""):
                self.flaky_tests[test["test_name"]] = test

    def pytest_runtest_protocol(self, item, nextitem):
        class_name = self._get_class_name(item)

        if (
            self.flaky_tests and
            self.flaky_tests.get(item.name) and
            self.flaky_tests[item.name].get("class_name") in class_name
        ):
            min_passes = self.min_passes
            max_runs = self.max_runs
            if self.flaky_tests[item.name].get("min_passes"):
                min_passes = self.flaky_tests[item.name]["min_passes"]
            if self.flaky_tests[item.name].get("max_runs"):
                max_runs = self.flaky_tests[item.name]["max_runs"]
            self._mark_flaky(item, max_runs, min_passes)
            print("item dict: ", item.__dict__)

    def _get_class_name(self, test):
        """
        Gets the combined module and class name of the test.

        :param test: The test `Item` object.
        :return: The module and class name as a string.
            eg. "src.test.TestSample" for tests within a class
                or "src.test" for tests not in a class
        """
        test_instance = self._get_test_instance(test)
        class_name = test_instance.__name__
        if getattr(test_instance, "__module__", None):
            class_name = test_instance.__module__ + "." + test_instance.__name__
        return class_name

    @staticmethod
    def _get_test_name(test):
        """
        Gets the test name.

        :param test: The test `Item` object.
        :return: The test name as a string, eg. "test_sample"
        """
        callable_name = test.name
        if callable_name.endswith("]") and "[" in callable_name:
            unparametrized_name = callable_name[:callable_name.index("[")]
        else:
            unparametrized_name = callable_name
        return unparametrized_name

    @staticmethod
    def _get_test_instance(item):
        test_instance = getattr(item, "instance", None)
        if test_instance is None:
            if hasattr(item, "parent") and hasattr(item.parent, "obj"):
                test_instance = item.parent.obj
        return test_instance

    @staticmethod
    def _get_flaky_attributes(test_item):
        """
        Get all the flaky related attributes from the test.

        :param test_item: The test `Item` object from which to get the flaky related attributes.
        :return: Dictionary containing attributes.
        """
        return {
            attr: getattr(test_item, attr, None) for attr in FlakyTestAttributes().items()
        }

    @staticmethod
    def _set_flaky_attribute(test_item, attr, value):
        """
        Sets an attribute on a flaky test.

        :param test_item: The test `Item` object to set the attribute for.
        :param attr: The name of the attribute.
        :param value: The value to set the attribute to.
        """
        test_item.__dict__[attr] = value

    def _mark_flaky(self, test, max_runs=None, min_passes=None):
        """
        Mark a test as flaky by setting flaky attributes.

        :param test: The test `Item` object.
        :param max_runs: The value of the FlakyTestAttributes.MAX_RUNS attribute to use.
        :param min_passes: The value of the FlakyTestAttributes.MIN_PASSES attribute to use.
        """
        attr_dict = FlakyTestAttributes.default_flaky_attributes(max_runs, min_passes)
        for attr, value in attr_dict.items():
            self._set_flaky_attribute(test, attr, value)


PLUGIN = FlakybotRunner()
for _pytest_hook in dir(PLUGIN):
    if _pytest_hook.startswith("pytest_"):
        globals()[_pytest_hook] = getattr(PLUGIN, _pytest_hook)
