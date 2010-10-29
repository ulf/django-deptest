django-deptest
==============

This Python script is used to apply Django's testing framework in the scenario that you have several interdependent projects.

Configuration
-------------

To configure you need a Yaml file which contains all your Django projects you want to test and their dependencies.

### Example

    projects:
      main: # Project identifier
        dir: /home/ulf/django/main         # Path where the files are located
        deps: [login, static]              # Projects which need to run in order for tests to complete
        tests:                             # Collection of test profiles. 'default' is needed
          default: [myapp, yourapp]        # Tests to run default
          extended: [myapp, yourapp, herapp, hisapp] 
      login:
        dir: /home/ulf/django/login
        port: 8080                         # Port where the project runs as dependency
        fixtures: [base]		   # Fixtures to load when running as dependency
        reset: [app1,app2]		   # Apps to reset before fixture loading
      static:
        dir: /home/ulf/django/static
        port: 8081

Usage
-----
To run the tests, you need to supply the config file and the project, which you want to run the tests for, as arguments.

    ./deptest.py config.yaml main

This will run the tests in profile `default` for the *main* project, as specified in the config file above. Before running the tests, the dependencies are started. In this case, the script runs the *login* project on port 8080 and the *static* project on port 8081. After apps are reset and fixtures loaded, the tests for *main* are run. After that, the dependencies get torn down. To run tests in profile `extended` use:

    ./deptest.py config.yaml main extended

### Note

Be aware that the dependencies are setup anew for every item in the `tests` variable, in the example `tests: [myapp, yourapp]` that means the following workflow:

1. Dependencies are set up
2. Test myapp is run
3. Dependencies are torn down
4. Dependencies are set up
5. Test yourapp is run
6. Dependencies are torn down

If you want to run multiple tests without setting everything up every time, use a list element: `tests: [myapp, [yourapp, herapp]]`. Here, between the tests of `yourapp` and `herapp2` there is no tearing down of dependencies.

Dependencies
------------

* yamlconfig
* PyYAML

Roadmap
-------

* Integrate as Django manage command
* Add more configuration options
* Add python config files
* Maybe integrate fabric to run dependencies remotely
