import sys
import os
from subprocess import Popen, PIPE
from ConfigParser import NoSectionError

from scrapyd.spiderqueue import SqliteSpiderQueue
from scrapy.utils.python import stringify_dict, unicode_to_str
from scrapyd.config import Config

def get_spider_queues(config):
    """Return a dict of Spider Quees keyed by project name"""
    # We need to check whether the --rundir arg exists.
    # https://github.com/scrapy/scrapyd/issues/70
    workingdir = os.getcwd()
    rundir = get_rundir()
    changed_to_rundir = False
    if rundir and rundir != workingdir:
        # Later on the code cds to rundir. But at the moment, we are not
        # in rundir, so the code to load dbs will run from the wrong
        # directory. This means that any existing eggs/projects in rundir
        # won't be read at startup! So we cd to rundir.
        os.chdir(rundir)
        changed_to_rundir = True

    dbsdir = config.get('dbs_dir', 'dbs')
    if not os.path.exists(dbsdir):
        os.makedirs(dbsdir)
    d = {}
    for project in get_project_list(config):
        dbpath = os.path.join(dbsdir, '%s.db' % project)
        d[project] = SqliteSpiderQueue(dbpath)

    if changed_to_rundir:
        # While it would be desirable to stay in rundir, the rest of the
        # code might rely on not having changed dir to rundir yet.
        # So to be safe, we restore the original (faulty) workingdir
        os.chdir(workingdir)

    return d

def get_project_list(config):
    """Get list of projects by inspecting the eggs dir and the ones defined in
    the scrapyd.conf [settings] section
    """
    eggs_dir = config.get('eggs_dir', 'eggs')
    if os.path.exists(eggs_dir):
        projects = os.listdir(eggs_dir)
    else:
        projects = []
    try:
        projects += [x[0] for x in config.cp.items('settings')]
    except NoSectionError:
        pass
    return projects

def get_crawl_args(message):
    """Return the command-line arguments to use for the scrapy crawl process
    that will be started for this message
    """
    msg = message.copy()
    args = [unicode_to_str(msg['_spider'])]
    del msg['_project'], msg['_spider']
    settings = msg.pop('settings', {})
    for k, v in stringify_dict(msg, keys_only=False).items():
        args += ['-a']
        args += ['%s=%s' % (k, v)]
    for k, v in stringify_dict(settings, keys_only=False).items():
        args += ['-s']
        args += ['%s=%s' % (k, v)]
    return args

def get_spider_list(project, runner=None, pythonpath=None):
    """Return the spider list from the given project, using the given runner"""
    if runner is None:
        runner = Config().get('runner')
    env = os.environ.copy()
    env['SCRAPY_PROJECT'] = project
    if pythonpath:
        env['PYTHONPATH'] = pythonpath
    pargs = [sys.executable, '-m', runner, 'list']
    proc = Popen(pargs, stdout=PIPE, stderr=PIPE, env=env)
    out, err = proc.communicate()
    if proc.returncode:
        msg = err or out or 'unknown error'
        raise RuntimeError(msg.splitlines()[-1])
    return out.splitlines()


def get_rundir():
    """Try to get a value for the --rundir command line argument.
    """
    max_value_for_i = len(sys.argv) - 1
    for i, arg in enumerate(sys.argv):
        if arg == "--rundir" and i < max_value_for_i:
            return sys.argv[i + 1]

    return None
