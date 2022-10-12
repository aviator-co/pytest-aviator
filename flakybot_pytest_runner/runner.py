import os
import requests

from flakybot_pytest_runner.attributes import FlakyTestAttributes, DEFAULT_MIN_PASSES, DEFAULT_MAX_RUNS


AVIATOR_MARKER = "aviator"
BUILDKITE_JOB_PREFIX = "buildkite/"
CIRCLECI_JOB_PREFIX = "ci/circleci:"


class FlakybotRunner:
    runner = None
    _API_URL = "https://api.aviator.co/api/v1/flaky-tests"
    flaky_tests_identified = {}
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
        self._API_URL = os.environ.get("AVIATOR_API_URL") or self._API_URL
        API_TOKEN = os.environ.get("AVIATOR_API_TOKEN", "")
        headers = {
            "Authorization": "Bearer " + API_TOKEN,
            "Content-Type": "application/json"
        }
        params = {"repo_name": repo_name, "job_name": job_name}
        response = requests.get(self._API_URL, headers=headers, params=params).json()
        flaky_tests = response.get("flaky_tests", [])

        for test in flaky_tests:
            if test.get("test_name", ""):
                self.flaky_tests_identified[test["test_name"]] = test

        print("flaky tests: ", self.flaky_tests_identified)

    def pytest_runtest_protocol(self, item, nextitem):
        test_instance = self._get_test_instance(item)
        self._copy_flaky_attributes(item, test_instance)
        class_name = test_instance.__module__ + "." + test_instance.__name__

        print(f"test instance: {test_instance}")
        print(f"class name: {class_name}")
        print("test item: ", item.name)
        if (
            self.flaky_tests_identified and
            self.flaky_tests_identified.get(item.name) and
            self.flaky_tests_identified[item.name].get("class_name") in class_name
        ):
            min_passes = self.min_passes
            max_runs = self.max_runs
            if self.flaky_tests_identified[item.name].get("min_passes"):
                min_passes = self.flaky_tests_identified[item.name]["min_passes"]
            if self.flaky_tests_identified[item.name].get("max_runs"):
                max_runs = self.flaky_tests_identified[item.name]["max_runs"]
            self._mark_flaky(item, max_runs, min_passes)
            print("item dict: ", item.__dict__.items())

    @staticmethod
    def _get_test_instance(item):
        instance = item.instance
        if not instance:
            if item.parent and item.parent.obj:
                instance = item.parent.obj
        return instance

    @classmethod
    def _copy_flaky_attributes(cls, test, test_class):
        """
        Copy flaky attributes from the test to the attribute dict.

        :param test: The test that is being prepared to run
        """
        test_callable = cls._get_test_callable(test)
        if test_callable is None:
            return
        for attr, value in cls._get_flaky_attributes(test_class).items():
            if hasattr(test, attr):
                continue
            attr_on_callable = getattr(test_callable, attr, None)
            if attr_on_callable is not None:
                cls._set_flaky_attribute(test, attr, attr_on_callable)
            elif value is not None:
                cls._set_flaky_attribute(test, attr, value)

    @classmethod
    def _get_test_callable(cls, test):
        """
        Base class override.

        :param test: The test that has raised an error or succeeded
        :return: The test declaration, callable and name that is being run
        """
        callable_name = test.name
        if callable_name.endswith("]") and "[" in callable_name:
            unparametrized_name = callable_name[:callable_name.index("[")]
        else:
            unparametrized_name = callable_name
        test_instance = cls._get_test_instance(test)
        if hasattr(test_instance, callable_name):
            # Test is a method of a class
            def_and_callable = getattr(test_instance, callable_name)
            return def_and_callable
        if hasattr(test_instance, unparametrized_name):
            # Test is a parametrized method of a class
            def_and_callable = getattr(test_instance, unparametrized_name)
            return def_and_callable
        if hasattr(test, "module"):
            if hasattr(test.module, callable_name):
                # Test is a function in a module
                def_and_callable = getattr(test.module, callable_name)
                return def_and_callable
            if hasattr(test.module, unparametrized_name):
                # Test is a parametrized function in a module
                def_and_callable = getattr(test.module, unparametrized_name)
                return def_and_callable
        elif hasattr(test, "runtest"):
            # Test is a doctest or other non-Function Item
            return test.runtest
        return None

    @classmethod
    def _get_flaky_attributes(cls, test_item):
        """
        Get all the flaky related attributes from the test.

        :param test_item: The test callable from which to get the flaky related attributes.
        :return: Dictionary containing attributes.
        """
        return {
            attr: getattr(test_item, attr, None) for attr in FlakyTestAttributes()
        }

    @staticmethod
    def _set_flaky_attribute(test_item, flaky_attribute, value):
        """
        Sets an attribute on a flaky test. Uses magic __dict__ since setattr
        doesn't work for bound methods.

        :param test_item: The test callable on which to set the attribute.
        :param flaky_attribute: The name of the attribute.
        :param value: The value to set the attribute to.
        """
        test_item.__dict__[flaky_attribute] = value

    @classmethod
    def _mark_flaky(cls, test, max_runs=None, min_passes=None, rerun_filter=None):
        """
        Mark a test as flaky by setting flaky attributes.

        :param test: The given test.
        :param max_runs: The value of the FlakyTestAttributes.MAX_RUNS attribute to use.
        :param min_passes: The value of the FlakyTestAttributes.MIN_PASSES attribute to use.
        :param rerun_filter:
            Filter function to decide whether a test should be rerun if it fails.
            Function signature is as follows:
                (err, name, test, plugin) -> should_rerun
            - err (`tuple` of `class`, :class:`Exception`, `traceback`):
                Information about the test failure (from sys.exc_info())
            - name (`unicode`):
                The test name
            - test (:class:`nose.case.Test` or :class:`Function`):
                The test that has raised an error
            - plugin (:class:`FlakyPytestPlugin`):
                The flakybot plugin. Has a :prop:`stream` that can be written to in
                order to add to the Flaky Report.
        """
        attrib_dict = FlakyTestAttributes.default_flaky_attributes(max_runs, min_passes, rerun_filter)
        for attr, value in attrib_dict.items():
            cls._set_flaky_attribute(test, attr, value)


PLUGIN = FlakybotRunner()
for _pytest_hook in dir(PLUGIN):
    if _pytest_hook.startswith('pytest_'):
        globals()[_pytest_hook] = getattr(PLUGIN, _pytest_hook)
