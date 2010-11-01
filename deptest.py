#!/usr/bin/env python

"""
django-deptest
v0.1

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

# Check for correct number of arguments
usage = "usage: %prog configfile project_to_test [testprofile]"
parser = OptionParser(usage=usage)
parser.add_option('-d', '--dependency-stdout', action="store_true",
                  dest="dep_output", default=False,
                  help="Display output of dependencies on stdout")
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

# Name of python interpreter
cmd = 'python'

# For the tests we actually want some output
testparams = dict(stdparams)
testparams['stdout'] = sys.stdout
testparams['stderr'] = sys.stdout
results = {}
for tests in main['tests'][profile]:
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
            for r in x['reset']:
                print "Resetting app", r, "for", d
                p = subprocess.Popen( [cmd, "manage.py", "reset", r, "--noinput"],
                                      cwd=x['dir'],
                                      **stdparams)
                p.wait()

        if 'fixtures' in x:
            for f in x['fixtures']:
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
