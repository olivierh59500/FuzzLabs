#!/usr/bin/env python
import os
import sys
import time
import glob
import inspect
import importlib
import threading
from classes.Utils import Utils
from classes.Config import Config
from classes.Logger import Logger
from classes.Scenario import Scenario
from classes.MutationsExhaustedException import MutationsExhaustedException

drivers = {}
for driver in glob.glob("drivers/*.py"):
    name = driver.split(".")[0].split("/")[1]
    if name[:2] == "__": continue
    drivers[name] = importlib.import_module("drivers." + name)

# -----------------------------------------------------------------------------
#
# -----------------------------------------------------------------------------

class Worker(threading.Thread):

    def __init__(self, logger, config, uuid, job):
        threading.Thread.__init__(self)
        self.logger    = logger
        self.config    = config
        self.id        = uuid
        self.job       = None
        self.driver    = None
        self.scenarios = []

        try:
            self.job = Utils.read_json(job)
        except Exception, ex:
            msg = self.logger.log("failed to initialize job", "error",
                            str(ex),
                            self.id,
                            self.job.get('id'))
            raise Exception(msg)

        target = self.job.get('target')
        if not target:
            msg = self.logger.log("failed to initialize job", "error",
                            "no target defined",
                            self.id,
                            self.job.get('id'))
            raise Exception(msg)

        driver = target.get('transport').get('media')
        try:
            inst = getattr(drivers[driver], driver)
            self.driver = inst(target)
        except Exception, ex:
            msg = self.logger.log("failed to initialize driver", "error",
                            str(ex),
                            self.id,
                            self.job.get('id'))
            raise Exception(msg)

        t_scenarios = self.job.get('scenarios')

        if not t_scenarios:
            msg = self.logger.log("failed to initialize job", "error",
                            "no scenarios defined",
                            self.id,
                            self.job.get('id'))
            raise Exception(msg)

        for scenario_id in range(0, len(t_scenarios)):
            try:
                self.scenarios.append(Scenario(self.config,
                                               scenario_id, 
                                               self.job))
            except Exception, ex:
                msg = self.logger.log("failed to initialize scenarios", "error",
                                str(ex),
                                self.id,
                                self.job.get('id'))
                raise Exception(msg)
            scenario_id += 1

    # -------------------------------------------------------------------------
    #
    # -------------------------------------------------------------------------

    def run(self):
        for scenario in self.scenarios:
            try:
                for iteration in scenario.run():
                    if iteration.get('state') == "connect":
                        self.driver.connect()
                        scenario.stateConnected()
                        continue
                    if iteration.get('state') == "disconnect":
                        self.driver.disconnect()
                        scenario.stateDisconnected()
                        continue
                    self.driver.send(iteration.get('data'))
                    data = self.driver.receive()
            except MutationsExhaustedException, mex:
                pass
            except Exception, ex:
                msg = self.logger.log("failed to execute scenarios", "error",
                                str(ex),
                                self.id,
                                self.job.get('id'),
                                scenario.get('name'))
                raise Exception(msg)

# -----------------------------------------------------------------------------
# This is just to:
#     a) be able to easily test the worker
#     b) be able to run a fuzzing job from the command line
# -----------------------------------------------------------------------------

ROOT = os.path.dirname(
            os.path.abspath(
                inspect.getfile(inspect.currentframe()
            )))
config = Config(ROOT, "/../config/config.json")
logger = Logger()

if len(sys.argv) != 2:
    print "Usage: %s <job descriptor>" % sys.argv[0]
    sys.exit(1)

w = Worker(
        logger,
        config,
        Utils.generate_name(), 
        sys.argv[1])
w.start()

