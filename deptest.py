#!/usr/bin/env python

"""
django-deptest
v0.2

Testing wrapper for Django's unittests with interdependent projects

Author: Ulf Boegeholz <boegeholz@gmail.com>
Help: http://github.com/ulf/django-deptest
"""

from yamlconfig import YamlConfig
import sys, os
import subprocess
import signal
import time
import httplib
from optparse import OptionParser
import unittest
from unittest import TestLoader
from collections import defaultdict

def get_tests(x):
    ret = []
    for t in x.__dict__.get('_tests'):
        if isinstance(t, unittest.TestSuite):
            # Add every test in that Suite
            ret.extend(get_tests(t))
        else:
            # Add the test directly
            # Text replacement because .tests is omitted
            # in the django test command
            ret.append(t.id().replace('.tests.','.'))
    return ret

# Check for correct number of arguments
usage = "usage: %prog configfile project_to_test [testprofile]"
parser = OptionParser(usage=usage)
parser.add_option('-d', '--dependency-stdout', action="store_true",
                  dest="dep_output", default=False,
                  help="Display output of dependencies on stdout")
parser.add_option('-c', '--check-coverage', action="store_true",
                  dest="coverage", default=False,
                  help="Check coverage of your tests")
options, args = parser.parse_args()
if len(args) not in [2,3]:
    print "Wrong number of arguments. See -h for help."
    sys.exit(1)

# Set profile default value if none is specified
if len(args) == 2:
    profile = 'default'
else:
    profile = args[2]

# Common params for every Popen call
stdparams = {
    'stdout' : options.dep_output and sys.stdout or subprocess.PIPE,
    'stderr' : sys.stdout,
    'env' : os.environ,
    'close_fds' : True,
    'preexec_fn' : os.setsid
    }

# Initialize config var and main project
config = YamlConfig(args[0])
main = config['projects'][args[1]]

# To check coverage, determine all the modules we run tests for
# Than compare to the tests which are really run in the profiles
# one by one
if options.coverage:
    # Needed for test loading
    sys.path.append(main['dir'])
    # Use specified settings name or default
    os.environ['DJANGO_SETTINGS_MODULE'] = main.get('settings', 'settings')

    modules = []
    # Find top level modules for all test profiles
    for p in main['tests']:
        prefixes = map(lambda x: x[:x.find('.')] if x.find('.') > -1 else x, main['tests'][p])
        modules.extend(prefixes)
    # Eliminate duplicates
    modules = list(set(modules))
    t = TestLoader()

    all_tests = []
    # Get every test of every module
    for m in modules:
        __import__(m + '.tests')
        all_tests.extend(get_tests(t.loadTestsFromName(m + '.tests')))

    untested_all = list(all_tests)
    for p in main['tests']:
        untested = list(all_tests)
        # Remove every test of this profile from the untested list
        for t in main['tests'][p]:
            untested = filter(lambda x: x.find(t) != 0,untested)
            untested_all = filter(lambda x: x.find(t) != 0,untested_all)
        # Now the untested list contains only tests not regarded in this profile
        if len(untested) == 0:
            print '\033[92mProfile',p,'tests everything!\033[0m\n'
        else:
            print '\033[93mProfile',p,'misses',len(untested),'of',len(all_tests),'tests:\033[0m\n',untested,'\n'

    if len(untested_all) == 0:
        print '\033[92mEvery test appears in at least one profile\033[0m\n'
    else:
        print '\033[93mTests run in no profile:\033[0m\n', untested_all
    sys.exit()

# Name of python interpreter
cmd = 'python'

def descend(container, *keys):
    """
    Helper function to descend in a nested default dict until
    all keys are found, return False on keyfailure
    """
    for k in keys:
        if not container[k]:
            return False
        container = container[k]
    return container

# For the tests we actually want some output
testparams = dict(stdparams)
testparams['stdout'] = sys.stdout
testparams['stderr'] = sys.stdout
results = {}
for tests in main['tests'][profile]:
    override = defaultdict(lambda : False)
    if isinstance(tests, dict):
        for d in tests['deps']:
            override[d] = defaultdict(lambda : False)
            for i in tests['deps'][d]:
                override[d][i] = tests['deps'][d][i]
        tests = tests['tests']
    if not isinstance(tests, list):
        tests = [tests]

    print "\nRunning tests", tests

    # Save the running processes here
    running = []

    # Set up the dependencies
    for d in main['deps']:
        if not d in config['projects']:
            print "Project", d, "was not found. Please update config file"
            sys.exit(1)
        x = config['projects'][d]
        if 'reset' in x:
            for r in descend(override, d, 'reset') or x['reset']:
                print "Resetting app", r, "for", d
                p = subprocess.Popen( [cmd, "manage.py", "reset", r, "--noinput"],
                                      cwd=x['dir'],
                                      **stdparams)
                p.wait()

        if 'fixtures' in x:
            for f in descend(override, d, 'fixtures') or x['fixtures']:
                print "Loading fixture", f, "for", d
                p = subprocess.Popen( [cmd, "manage.py", "loaddata", f],
                                      cwd=x['dir'],
                                      **stdparams)
                p.wait()

        print "Starting server for", d, "on port", x['port']
        p = subprocess.Popen( [cmd, "manage.py", "runserver", str(x['port']), "--noreload"],
                              cwd=x['dir'],
                              **stdparams)
        # Wait for the server to be reachable
        while True:
            try:
                conn = httplib.HTTPConnection('localhost', x['port'])
                conn.request("HEAD", '/')
                conn.getresponse()
                break
            except:
                print "Server",d,"on port",x['port'],"not yet running! Retry in 2s."
            time.sleep(2)
        running.append((p, d))

    for t in tests:
        print "Tests", t
        p = subprocess.Popen( [cmd, "manage.py", "test", "-v0", t],
                              cwd=main['dir'],
                              **testparams)
        # Wait for the tests to complete
        p.wait()
        results[t] = p.returncode

    # Now kill all running dependencies
    for r,name in running:
        print "Killing", name
        os.killpg(r.pid, signal.SIGKILL)

print """

-------
Results
-------"""
failures = 0
for t, f in results.iteritems():
    print "Return code for test", t,': ',f
    if f == 1:
        failures = 1

sys.exit(failures)
