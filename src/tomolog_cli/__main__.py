import os
import sys
import time
import pathlib 
import argparse

from datetime import datetime

from tomolog_cli import log
from tomolog_cli import utils
from tomolog_cli import config
from tomolog_cli import TomoLog
from tomolog_cli import TomoLog32ID
from tomolog_cli import TomoLog2BM
from tomolog_cli import TomoLog7BM


def init(args):
    if not os.path.exists(str(args.config)):
        config.write(args.config)
    else:
        log.error("{0} already exists".format(args.config))


def run_gui(args):
    """Launch the Tomolog GUI"""
    log.warning('Starting Tomolog GUI')
    
    try:
        import subprocess
        import os
        
        script_dir = os.path.dirname(os.path.abspath(__file__))
        gui_path = os.path.join(script_dir, 'gui.py')
        
        # Run: python gui.py from the same folder
        subprocess.run(['python', gui_path])
        
    except FileNotFoundError:
        log.error("gui.py file not found in the same directory")
    except Exception as e:
        log.error(f"Error starting GUI: {e}")


def run_status(args):
    config.log_values(args)    


def run_log(args):

    log.warning('Publication start')
    log.warning('Slide formatting for beamline: %s', args.beamline)
    file_path = pathlib.Path(args.file_name)
    if file_path.is_file():
        log.info("publishing a single file: %s" % args.file_name)
        if args.beamline == '32-id':
            TomoLog32ID(args).run_log()
        elif args.beamline == '2-bm':
            TomoLog2BM(args).run_log()
        elif args.beamline == '7-bm':
            TomoLog7BM(args).run_log()
        else:
            TomoLog(args).run_log()
    elif file_path.is_dir():
        log.info("publishing a multiple files in: %s" % args.file_name)
        top = os.path.join(args.file_name, '')
        h5_file_list = list(filter(lambda x: x.endswith(('.h5', '.hdf', 'hdf5')), os.listdir(top)))
        h5_file_list_sorted = sorted(h5_file_list, key = lambda x: x.split('_')[-1])
        if (h5_file_list):
            # h5_file_list.sort()
            log.info("found: %s" % h5_file_list_sorted) 
            index=0
            for fname in h5_file_list_sorted:
                args.file_name = top + fname
                log.warning("  *** file %d/%d;  %s" % (index, len(h5_file_list_sorted), fname))
                index += 1
                if args.beamline == '32-id':
                    TomoLog32ID(args).run_log()
                elif args.beamline == '2-bm':
                    TomoLog2BM(args).run_log()
                elif args.beamline == '7-bm':
                    TomoLog7BM(args).run_log()
                else:
                    TomoLog(args).run_log()
                time.sleep(20)

        else:
            log.error("directory %s does not contain any file" % args.file_name)
    else:
        log.error("directory or File Name does not exist: %s" % args.file_name)

    # args.count = args.count + 1
    config.write(args.config, args, sections=config.PARAMS)
    log.warning('publication end')
    
def main():

    # make sure logs directory exists
    logs_home = os.path.join(str(pathlib.Path.home()), 'logs')

    # logs_home = args.logs_home
    if not os.path.exists(logs_home):
        os.makedirs(logs_home)

    lfname = os.path.join(logs_home, 'tomolog_' +
                          datetime.strftime(datetime.now(), "%Y-%m-%d_%H_%M_%S") + '.log')
    # log_level = 'DEBUG' if args.verbose else "INFO"
    log.setup_custom_logger(lfname)
    log.info("Started tomolog")
    log.info("Saving log at %s" % lfname)

    parser = argparse.ArgumentParser()
    parser.add_argument('--config', **config.SECTIONS['general']['config'])
    params = config.PARAMS

    cmd_parsers = [
        ('init',        init,            (),     "Create configuration file"),
        ('run',         run_log,         params, "Run data logging to google slides"),
        ('status',      run_status,      params, "Show the tomolog status"),
        ('gui',         run_gui,         params, "Start Tomolog GUI"),
    ]

    subparsers = parser.add_subparsers(title="Commands", metavar='')

    for cmd, func, sections, text in cmd_parsers:
        cmd_params = config.Params(sections=sections)
        cmd_parser = subparsers.add_parser(
            cmd, help=text, formatter_class=argparse.ArgumentDefaultsHelpFormatter)
        cmd_parser = cmd_params.add_arguments(cmd_parser)
        cmd_parser.set_defaults(_func=func)

    args = config.parse_known_args(parser, subparser=True)

    # make sure token directory exists
    try:
        token_home = args.token_home
        if not os.path.exists(token_home):
            os.makedirs(token_home)
    except AttributeError as e:
        # log.error(str(e))
        log.error('Missing command selection. For options run: tomolog -h ')
        sys.exit(1)

    try:
        args._func(args)
    except RuntimeError as e:
        log.error(str(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
