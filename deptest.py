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
from optparse import OptionParser

# Check for correct number of arguments
usage = "usage: %prog configfile project_to_test"
parser = OptionParser(usage=usage)
options, args = parser.parse_args()
if len(args) != 2:
    print "Wrong number of arguments. See -h for help."
    sys.exit(1)


# Common params for every Popen call
stdparams = {
    'stdout' : subprocess.PIPE,
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

    if 'fixtures' in x:
        for f in x['fixtures']:
            print "Loading fixture", f, "for", d
            p = subprocess.Popen( [cmd, "manage.py", "loaddata", f],
                                  cwd=x['dir'],
                                  **stdparams)

    print "Starting server for", d, "on port", x['port']
    p = subprocess.Popen( [cmd, "manage.py", "runserver", str(x['port'])],
                          cwd=x['dir'],
                          **stdparams)
    running.append(p)

print "Running tests"
# Now we actually want some output
stdparams['stdout'] = sys.stdout
stdparams['stderr'] = sys.stdout
for t in main['tests']:
    p = subprocess.Popen( [cmd, "manage.py", "test", t],
                          cwd=main['dir'],
                          **stdparams)
# Wait for the tests to complete
p.wait()

# Now kill all running dependencies
for r in running:
    print "Killing", r.pid
    os.killpg(r.pid, signal.SIGKILL)

sys.exit()
