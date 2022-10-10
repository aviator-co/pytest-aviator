import os
import requests

BUILDKITE_JOB_PREFIX = "buildkite/"
CIRCLECI_JOB_PREFIX = "ci/circleci:"


class FlakybotRunner:
    runner = None
    _API_URL = 'https://api.flakybot.com/api/v1/flaky-tests'
    flaky_tests_identified = {}

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
        config.addinivalue_line('markers', 'flaky: marks flaky tests for Flakybot to automatically rerun')

    def get_flaky_tests(self):
        repo_name = None
        job_name = None

        # Get job and repo name
        if os.environ.get('CIRCLE_JOB'):
            # https://circleci.com/docs/2.0/env-vars/#built-in-environment-variables
            job_name = CIRCLECI_JOB_PREFIX + os.environ.get('CIRCLE_JOB', '')
            repo_name = '{username}/{repo_name}'.format(
                username=os.environ.get('CIRCLE_PROJECT_USERNAME', ''),
                repo_name=os.environ.get('CIRCLE_PROJECT_REPONAME', '')
            )
        if os.environ.get('BUILDKITE_PIPELINE_SLUG'):
            # Note: BUILDKITE_REPO is in the format "git@github.com:{repo_name}.git"
            job_name = BUILDKITE_JOB_PREFIX + os.environ.get('BUILDKITE_PIPELINE_SLUG', '')
            repo_name = os.environ.get('BUILDKITE_REPO').replace('git@github.com:', '').replace('.git', '')

        # Fetch flaky test info
        self._API_URL = os.environ.get('FLAKY_BOT_API_URL') or self._API_URL
        API_TOKEN = os.environ.get('FLAKY_BOT_API_TOKEN', '')
        headers = {
            'Authorization': 'Bearer ' + API_TOKEN,
            'Content-Type': 'application/json'
        }
        params = {'repo_name': repo_name, 'job_name': job_name}
        response = requests.get(self._API_URL, headers=headers, params=params).json()
        flaky_tests = response.get('flaky_tests', [])

        for test in flaky_tests:
            if test.get('test_name', ''):
                self.flaky_tests_identified[test['test_name']] = test

        print("flaky tests: ", self.flaky_tests_identified)


PLUGIN = FlakybotRunner()
