# Aviator's Pytest Plugin
## About

Aviator's pytest plugin will automatically rerun flaky tests to keep your builds green. By analyzing the test data we have in Flakybot, we determine how many times we should rerun a specific flaky test and the threshold for passing. 

In the example output below, `test_sample_random` must pass at least 1 time, with a maximum of 5 runs. It fails on the first run but passes on the second run, so `test_sample_random` successfully passes on this CI run.
```
============================= test session starts ==============================
platform linux -- Python 3.6.2, pytest-7.0.1, pluggy-1.0.0 -- /home/circleci/repo/venv/bin/python
cachedir: .pytest_cache
rootdir: /home/circleci/repo
plugins: flakybot-0.1.1
collecting ... collected 6 items                                                              

src/test_sample.py::TestSample::test_sample_dict PASSED                  [ 16%]
src/test_sample.py::TestSample::test_sample_list PASSED                  [ 33%]
src/test_sample.py::TestSample::test_sample_number PASSED                [ 50%]
src/test_sample.py::TestSample::test_sample_random PASSED                [ 66%]
src/test_sample.py::TestSample::test_sample_text PASSED                  [ 83%]
src/test_sample.py::TestSample::test_sample_tuple PASSED                 [100%]

------- generated xml file: /home/circleci/repo/test_results/output.xml --------
===FlakyBot Test Report===

test_sample_random
    FAILED: (4 runs remaining out of 5).
	<class 'AssertionError'>: 2 != 1
	[<TracebackEntry /home/circleci/repo/src/test_sample.py:35>]
	
test_sample_random passed 1 out of the required 1 times.

===End FlakyBot Test Report===
============================== 6 passed in 0.08s ===============================
```

Here's another example run, where `test_sample_random` must pass at least 2 times, with a maximum of 3 runs. It passes on the first run but fails on the next two runs, so `test_sample_random` fails on this CI run.

```
============================= test session starts ==============================
platform linux -- Python 3.6.2, pytest-7.0.1, pluggy-1.0.0 -- /home/circleci/repo/venv/bin/python
cachedir: .pytest_cache
rootdir: /home/circleci/repo
plugins: flakybot-0.1.1
collecting ... collected 6 items                                                              

src/test_sample.py::TestSample::test_sample_dict PASSED                  [ 16%]
src/test_sample.py::TestSample::test_sample_list PASSED                  [ 33%]
src/test_sample.py::TestSample::test_sample_number PASSED                [ 50%]
src/test_sample.py::TestSample::test_sample_random FAILED                [ 66%]
src/test_sample.py::TestSample::test_sample_text PASSED                  [ 83%]
src/test_sample.py::TestSample::test_sample_tuple PASSED                 [100%]

=================================== FAILURES ===================================
________________________ TestSample.test_sample_random _________________________
 
self = <src.test_sample.TestSample testMethod=test_sample_random>
 
    def test_sample_random(self):
        a = random.randint(0, 2)
        # a = 1
>       self.assertEqual(a, 1)
E       AssertionError: 0 != 1
 
src/test_sample.py:44: AssertionError
- generated xml file: /opt/homebrew/var/buildkite-agent/builds/Doras-MacBook-Pro-local-1/aviator-demo/sample-test/test_results/output.xml -===FlakyBot Test Report===
===FlakyBot Test Report===

test_sample_random passed 1 out of the required 2 times.
Running test again until it passes 2 times.
 
test_sample_random
	FAILED: (1 runs remaining out of 3).
	<class 'AssertionError'>: 2 != 1
	[<TracebackEntry /opt/homebrew/var/buildkite-agent/builds/Doras-MacBook-Pro-local-1/aviator-demo/sample-test/src/test_sample.py:44>]
 
test_sample_random: FAILED
	It passed 1 out of the required 2 times.

===End FlakyBot Test Report===
============================== 6 passed in 0.08s ===============================
```

## Install

Install the plugin before running tests with pytest.

```
pip install -e git+https://git@github.com/aviator-co/pytest-aviator.git#egg=pytest-aviator
```

## Store Test Artifacts

In order to correctly process and rerun the tests, we need the test results. You'll need to use pytest's [`junitxml`](https://docs.pytest.org/en/7.1.x/_modules/_pytest/junitxml.html) flag to report results in JUnit-XML format..

```
pytest src/ -vv --junitxml="test_results/result.xml"
```

### Buildkite

If the test results are stored in `test_results/result.xml`, you can upload the artifacts using the buildkite agent.

```
buildkite-agent artifact upload test_results/output.xml
```
See the [Buildkite docs](https://buildkite.com/docs/pipelines/artifacts) for other ways to upload build artifacts.

### CircleCI

Make sure to include the `store_artifacts` step in your config.yml.
```
- store_artifacts:
      path: ./test_results/output.xml
      destination: output.xml
```
See the [CircleCI docs](https://circleci.com/docs/artifacts) for more information.

## Aviator API Token
Make sure to set your account's Aviator API token as an environment variable `AVIATOR_API_URL`. You can find the token at https://app.aviator.co/account/api.

[CircleCI](https://circleci.com/docs/env-vars) - set the variable under the Project Settings page.

[Buildkite](https://buildkite.com/docs/pipelines/secrets) - manage your API token using a storage service or environment hooks.
