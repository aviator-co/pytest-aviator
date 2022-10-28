import os
import requests

from flakybot_pytest_runner.attributes import FlakyTestAttributes, DEFAULT_MIN_PASSES, DEFAULT_MAX_RUNS
from _pytest import runner

API_URL = "https://api.aviator.co/api/v1/flaky-tests"
AVIATOR_MARKER = "aviator"
BUILDKITE_JOB_PREFIX = "buildkite/"
CIRCLECI_JOB_PREFIX = "ci/circleci:"


class FlakybotRunner:
    runner = None
    flaky_tests = {}
    min_passes = DEFAULT_MIN_PASSES
    max_runs = DEFAULT_MAX_RUNS
    call_infos = {}

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
        url = os.environ.get("AVIATOR_API_URL") or API_URL
        api_token = os.environ.get("AVIATOR_API_TOKEN", "")
        headers = {
            "Authorization": "Bearer " + api_token,
            "Content-Type": "application/json"
        }
        params = {"repo_name": repo_name, "job_name": job_name}
        response = requests.get(url, headers=headers, params=params).json()
        av_flaky_tests = response.get("flaky_tests", [])

        for test in av_flaky_tests:
            if test.get("test_name", ""):
                self.flaky_tests[test["test_name"]] = test

    def pytest_runtest_protocol(self, item, nextitem):
        class_name = self.get_class_name(item)

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
            self.mark_flaky(item, max_runs, min_passes)

        self.call_infos[item] = {}
        default_call_and_report = self.runner.call_and_report
        should_rerun = True
        try:
            self.runner.call_and_report = self.call_and_report
            while should_rerun:
                self.runner.pytest_runtest_protocol(item, nextitem)
                for when in ["setup", "call"]:
                    call_info = self.call_infos.get(item, {}).get(when, None)
                    exc_info = getattr(call_info, "excinfo", None)
                    if exc_info:
                        break

                if not call_info:
                    return False
                passed = not exc_info
                if passed:
                    should_rerun = self.add_success(item)
                else:
                    should_rerun = self.add_failure(item, exc_info)
                    if not should_rerun:
                        item.excinfo = exc_info
        finally:
            self.runner.call_and_report = default_call_and_report
            del self.call_infos[item]
        return True

    def call_and_report(self, item, when, log=True, **kwds):
        """
        Monkey patch this runner method to get the CallInfo objects.
            https://docs.pytest.org/en/7.1.x/_modules/_pytest/runner.html
            CallInfo: https://docs.pytest.org/en/7.1.x/reference/reference.html#callinfo
        """
        call = runner.call_runtest_hook(item, when, **kwds)
        self.call_infos[item][when] = call
        hook = item.ihook
        report = hook.pytest_runtest_makereport(item=item, call=call)

        if report.when in ("call", "setup"):
            if report.outcome == "passed":
                if self.check_handle_success(item):
                    log = False
            elif report.outcome == "failed":
                if self.check_handle_failure(item):
                    log = False
        if log:
            hook.pytest_runtest_logreport(report=report)
        if self.runner.check_interactive_exception(call, report):
            hook.pytest_exception_interact(node=item, call=call, report=report)
        return report

    def get_class_name(self, test):
        """
        Gets the combined module and class name of the test.

        :param test: The test `Item` object.
        :return: The module and class name as a string.
            eg. "src.test.TestSample" for tests within a class
                or "src.test" for tests not in a class
        """
        test_instance = self.get_test_instance(test)
        class_name = test_instance.__name__
        if getattr(test_instance, "__module__", None):
            class_name = test_instance.__module__ + "." + test_instance.__name__
        return class_name

    @staticmethod
    def get_test_name(test):
        """
        Gets the test name.

        :param test: The test `Item` object.
        :return: The test name as a string, eg. "test_sample"
        """
        callable_name = test.name
        if callable_name.endswith("]") and "[" in callable_name:
            return callable_name[:callable_name.index("[")]
        return callable_name

    @staticmethod
    def get_test_instance(item):
        test_instance = getattr(item, "instance", None)
        if test_instance is None:
            if hasattr(item, "parent") and hasattr(item.parent, "obj"):
                test_instance = item.parent.obj
        return test_instance

    @staticmethod
    def get_flaky_attribute(test_item, attr):
        return getattr(test_item, attr, None)

    @staticmethod
    def set_flaky_attribute(test_item, attr, value):
        """
        Sets an attribute on a flaky test.

        :param test_item: The test `Item` object to set the attribute for.
        :param attr: The name of the attribute.
        :param value: The value to set the attribute to.
        """
        test_item.__dict__[attr] = value

    def mark_flaky(self, test, max_runs=None, min_passes=None):
        """
        Mark a test as flaky by setting flaky attributes.

        :param test: The test `Item` object.
        :param max_runs: The value of the FlakyTestAttributes.MAX_RUNS attribute to use.
        :param min_passes: The value of the FlakyTestAttributes.MIN_PASSES attribute to use.
        """
        attr_dict = FlakyTestAttributes.default_flaky_attributes(max_runs, min_passes)
        for attr, value in attr_dict.items():
            self.set_flaky_attribute(test, attr, value)

    def check_handle_failure(self, test):
        """
        Check if the failed test should be rerun.
        Does not make any changes to the FlakyTestAttribute info stored on the test object.

        :param test: The test that failed.
        :return: True if the test should be rerun, otherwise False.
        """
        if not self.is_flaky_test(test):
            return False
        flaky_info = self.get_flaky_info_copy(test)
        flaky_info[FlakyTestAttributes.RUNS] += 1
        return self.should_rerun_test(flaky_info)

    def add_failure(self, test, exc_info):
        """
        Add a test failure. Record the failure in the form of FlakyTestAttributes (RUNS, FAILURES).

        :param test: The test that failed.
        :param exc_info: Error information.
        :return: True if the test has not reached MAX_RUNS and should be rerun, otherwise False.
        """
        if exc_info:
            error = (exc_info.type, exc_info.value, exc_info.traceback)
        else:
            error = (None, None, None)

        if self.is_flaky_test(test):
            all_errors = self.get_flaky_attribute(test, FlakyTestAttributes.FAILURES) or []
            all_errors.append(error)
            self.set_flaky_attribute(test, FlakyTestAttributes.FAILURES, all_errors)
            self.increment(test, FlakyTestAttributes.RUNS)
            should_handle = self.check_handle_failure(test)

            if should_handle:
                self.log_failure(test, error)
                return True
        return False

    def add_success(self, test):
        """
        Add a test success. Record the success in the form of FlakyTestAttributes (RUNS, PASSES).

        :param test: The test that passed.
        :return: True if the test has not reached MIN_PASSES and should be rerun, otherwise False.
        """
        if not self.is_flaky_test(test):
            return False
        self.increment(test, FlakyTestAttributes.RUNS)
        self.increment(test, FlakyTestAttributes.PASSES)
        return not self.did_test_pass(test)

    def check_handle_success(self, test):
        """
        Check if the successful test should be rerun.
        Does not make any changes to the FlakyTestAttribute info stored on the test object.

        :param test: The test that passed.
        :return: True if the test should be rerun, otherwise False.
        """
        if not self.is_flaky_test(test):
            return False
        flaky_info = self.get_flaky_info_copy(test)
        flaky_info[FlakyTestAttributes.RUNS] += 1
        flaky_info[FlakyTestAttributes.PASSES] += 1
        return not self.did_info_pass(flaky_info)

    def get_flaky_info_copy(self, test):
        return {
            attribute: self.get_flaky_attribute(test, attribute) for attribute in FlakyTestAttributes().items()
        }

    def increment(self, test, attribute):
        self.set_flaky_attribute(test, attribute, getattr(test, attribute, 0) + 1)

    def log_failure(self, test, error):
        max_runs = self.get_flaky_attribute(test, FlakyTestAttributes.MAX_RUNS)
        current_runs = self.get_flaky_attribute(test, FlakyTestAttributes.RUNS)
        runs_left = max_runs - current_runs
        # TODO: generate nicer report
        print(self.get_test_name(test), "\n")
        print(f"failed ({runs_left} runs remaining out of {max_runs}).", "\n")
        print(error[0], "\n")
        print(error[1], "\n")
        print(error[2])

    @staticmethod
    def should_rerun_test(flaky_info):
        has_runs_remaining = flaky_info[FlakyTestAttributes.RUNS] < flaky_info[FlakyTestAttributes.MAX_RUNS]
        needs_more_passes = flaky_info[FlakyTestAttributes.PASSES] < flaky_info[FlakyTestAttributes.MIN_PASSES]
        if has_runs_remaining and needs_more_passes:
            return True
        return False

    @staticmethod
    def did_info_pass(flaky_info):
        return flaky_info[FlakyTestAttributes.PASSES] >= flaky_info[FlakyTestAttributes.MIN_PASSES]

    @staticmethod
    def did_test_pass(test):
        return FlakybotRunner.get_flaky_attribute(test, FlakyTestAttributes.PASSES) \
               >= FlakybotRunner.get_flaky_attribute(test, FlakyTestAttributes.MIN_PASSES)

    @staticmethod
    def is_flaky_test(test):
        return FlakyTestAttributes.MIN_PASSES in test.__dict__


PLUGIN = FlakybotRunner()
for _pytest_hook in dir(PLUGIN):
    if _pytest_hook.startswith("pytest_"):
        globals()[_pytest_hook] = getattr(PLUGIN, _pytest_hook)
