#!/usr/bin/env python
# coding=utf-8

import time, signal, sys, os, shutil
import threading
import argparse
import codecs, locale
from kitchen.text.converters import getwriter
import pkg_resources

from witica.site import Site
from witica.log import *
from witica.metadata import extractor
from witica.source import Source, MetaChanged, ItemChanged, ItemRemoved
from witica.targets import target, web, statichtml
from witica.check import IntegrityChecker
from witica.util import sstr, suni, throw
from witica import util

VERSION = pkg_resources.get_distribution("witica").version

currentsite = None

def shutdown():
	log("Shutting down...", Logtype.DEBUG)
	try:
		if currentsite:
			currentsite.shutdown()
	except Exception, e:
		log_exception("Shutdown failed.", Logtype.ERROR)
	finally:
		seconds_left = 30
		while seconds_left > 0 and threading.active_count() > 2: #main + logging thread
			time.sleep(1)
			seconds_left -= 1
		if threading.active_count() > 2: #main + logging thread
			print("Hanging threads:")
			for t in threading.enumerate():
				if not(t == threading.current_thread()) and t.isAlive():
					print("* " + t.name)
			print("Force quit.")
			Logger.stop()
			sys.exit(0) #TODO: does this really kill all threads?
		Logger.stop()
		pkg_resources.cleanup_resources(force=False)

def signal_handler(signal, frame):
	log("Shutdown requested by user.", Logtype.INFO)
	shutdown()

def log(msg, logtype = Logtype.NONE):
	Logger.log("witica", msg, logtype)

def log_exception(msg, logtype = Logtype.NONE, exc_info=None):
	Logger.log_exception("witica", msg, logtype, exc_info)

def create_source(args):
	if args.source:
		return Source.construct_from_file(args.source)
	else:
		return Source.construct_from_working_dir()

def init_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)

	target_id = "web"

	cwd = os.getcwd()
	if cwd.find(os.sep + "Dropbox" + os.sep) > -1:
		if os.listdir(cwd) == []: #if dir is empty
			try: #copy sample source
				for fn in os.listdir(pkg_resources.resource_filename("witica","client")):
					abs_fn = pkg_resources.resource_filename("witica","client") + os.sep + fn
					if os.path.isdir(abs_fn):
						shutil.copytree(abs_fn, cwd + os.sep + fn)
					else:
						shutil.copy2(abs_fn, cwd)
				log("Source successfully initialized. Please adjust meta/web.target configuration file.", Logtype.INFO)
			except Exception, e:
				log_exception("Init finished with errors.", Logtype.ERROR)
		else:
			log("Init is only possible when the current folder is empty.", Logtype.ERROR)
	else:
		log("Working directory is not a valid source. Must be a folder inside your Dropbox.", Logtype.ERROR)

def upgrade_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)

	source = None
	try:
		source = Source.construct_from_working_dir()
		currentsite = Site(source, target_ids = args.targets)
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	cwd = os.getcwd()
	if cwd.find(os.sep + "Dropbox" + os.sep) > -1 \
		and os.path.exists(os.path.join(cwd, "meta")) \
		and os.path.isdir(os.path.join(cwd, "meta")):

		target_ids = []
		if args.targets:
			target_ids = args.targets
		else:
			target_ids = [target.target_id for target in currentsite.targets]

		for target_id in target_ids:
			errors = False
			target = currentsite.get_target_by_id(target_id)
			if target != None and isinstance(target, web.WebTarget):
				log("Will now upgrade '" + target_id + "'. This will overwrite metafiles of the source and can break your website due to API changes (see release notes). It is recommended to make a backup of the target's metafiles before continuing.", Logtype.WARNING)
				filename = "js" + os.sep + "witica.js"
				if args.force or util.confirm("Overwrite " + filename + "?"):
					try:
						old_file = os.path.join(cwd, "meta", target_id, filename)
						new_file = os.path.join(pkg_resources.resource_filename("witica","client"), "meta", "web", filename)
						shutil.copy2(new_file, old_file)
						log("Upgraded file '" + filename + "'.", Logtype.DEBUG)
					except Exception, e:
						errors = True
						log_exception("Couldn't upgrade file '" + filename + "'.", Logtype.ERROR)
				else:
					errors = True
				if errors == False:
					log("Target '" + target_id + "' has been successfully upgraded.", Logtype.INFO)
				else:
					log("Target '" + target_id + "' has been upgraded partially or with erros. You should run upgrade again.", Logtype.WARNING)
			else:
				log("Target '" + target_id + "' is not a WebTarget. Currently only WebTargets can be upgraded.", Logtype.ERROR)
	else:
		log("Working directory is not a valid source. Must be a folder inside your Dropbox.", Logtype.ERROR)
		shutdown()
	currentsite.source.stoppedEvent(currentsite.source, None)

def update_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)
	try:
		source = create_source(args)
		currentsite = Site(source, target_ids = args.targets)
		currentsite.source.start_update(continuous = args.deamon)
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()

def rebuild_meta(source, path = ""):
	abspath = source.get_abs_meta_filename(path)
	if os.path.isdir(abspath):
		for fn in os.listdir(abspath):
			pth = os.path.join(abspath, fn).rpartition(source.get_abs_meta_filename(""))[2][1:]
			rebuild_meta(source, pth)
	else:
		source.changeEvent(source, MetaChanged(source, path))

def rebuild_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)
	try:
		source = create_source(args)
		currentsite = Site(source, target_ids = args.targets)
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	if len(args.item) == 0:
		rebuild_meta(currentsite.source)
		log("Site metadata enqued for rebuilding.", Logtype.INFO)

	items = get_matching_items(currentsite.source, args)

	for item in items:
		try:
			for path in item.files:
				currentsite.source.changeEvent(currentsite.source, ItemChanged(currentsite.source, item.item_id, path))	
		except Exception, e:
			log_exception("Item '" + item.item_id + "'' could not be enqued for rebuilding.", Logtype.ERROR)	
	log(str(len(items)) + " item" + ("s" if len(items) != 1 else "") + " enqued for rebuilding.", Logtype.INFO)

	currentsite.source.stoppedEvent(currentsite.source, None)

def check_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)

	try:
		source = create_source(args)
		currentsite = Site(source, target_ids = [])
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	items = get_matching_items(currentsite.source, args)

	numberfaults = 0
	ic = IntegrityChecker(currentsite.source)
	for item in items:
		for fault in ic.check(item):
			log(sstr(fault), Logtype.WARNING)
			numberfaults += 1
	log("Checked " + str(len(items)) + " items. " + str(numberfaults) + " integrity fault" + (" was" if numberfaults==1 else "s were") + " found.", Logtype.INFO)
	currentsite.source.stoppedEvent(currentsite.source, None)

def list_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)

	try:
		source = create_source(args)
		currentsite = Site(source, target_ids = [])
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	items = get_matching_items(currentsite.source, args)
	s = u"\n"
	count = 0
	for item in items:
		s += suni(item.item_id) + u"\n"
		count += 1
		if count == 100:
			log(s, Logtype.INFO)
			s = u"\n"
			count = 0
	if count > 0:
		log(s, Logtype.INFO)

	log("Source contains " + str(len(items)) + (" matching" if (len(args.item) > 0) else "") + " items.", Logtype.INFO)
	currentsite.source.stoppedEvent(currentsite.source, None)

def get_matching_items(source, args):
	items = []
	if len(args.item) > 0:
		#return matching items
		for idpattern in args.item:
			items.extend(currentsite.source.items.get_items(source.prefix + idpattern))
	elif len(args.item) == 0:
		items = [item for item in source.items if item.item_id.startswith(source.prefix)]
	return items

def main():
	#initialize witica

	signal.signal(signal.SIGINT, signal_handler) #abort on CTRL-C

	UTF8Writer = getwriter('utf8')
	sys.stdout = UTF8Writer(sys.stdout)

	extractor.register_default_extractors()

	target.register("WebTarget", web.WebTarget)
	target.register("StaticHtmlTarget", statichtml.StaticHtmlTarget)

	parser = argparse.ArgumentParser(description="Reads contents from a source, converts them and publishes to one or more targets.")
	parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + VERSION)

	subparsers = parser.add_subparsers(title='sub-commands', help='sub-commands')

	#init command parser
	parser_init = subparsers.add_parser('init', help='inits a source with an example web site (WARNING: modifies the current working dir)')
	parser_init.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
	parser_init.set_defaults(func=init_command)

	#upgrade command parser
	parser_upgrade = subparsers.add_parser('upgrade', help='upgrades targets in the source to the newest version of witica.js (WARNING: modifies the current working dir)')
	parser_upgrade.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
	parser_upgrade.add_argument('-f', '--force', action='store_true', help="don't ask before overwriting files")
	parser_upgrade.add_argument('-t', '--targets', nargs='+', help="list of ids of targets that should be upgraded")
	parser_upgrade.set_defaults(func=upgrade_command)

	#update command parser
	parser_update = subparsers.add_parser('update', help='fetch changes and update targets')
	parser_update.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
	parser_update.add_argument('-s', '--source', help="the source configuration file to use")
	parser_update.add_argument('-d', '--deamon', action='store_true', help="keep running in background and process incoming events")
	parser_update.add_argument('-t', '--targets', nargs='+', help="list of ids of targets that should be used for the conversion")
	parser_update.set_defaults(func=update_command)

	#rebuild command parser
	parser_rebuild = subparsers.add_parser('rebuild', help='update single items or indicies')
	parser_rebuild.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
	parser_rebuild.add_argument('-s', '--source', help="the source configuration file to use")
	parser_rebuild.add_argument('-t', '--targets', nargs='+', help="list of ids of targets that should be used for the conversion, default: all")
	parser_rebuild.add_argument('item', nargs='*', help="list of ids of items or indicies that should be updated")
	parser_rebuild.set_defaults(func=rebuild_command)

	#check command parser
	parser_check = subparsers.add_parser('check', help='checks the integrity of the source')
	parser_check.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
	parser_check.add_argument('-s', '--source', help="the source configuration file to use")
	parser_check.add_argument('item', nargs='*', help="list of ids of items or indicies that should be checked")
	parser_check.set_defaults(func=check_command)

	#items command parser
	parser_list = subparsers.add_parser('list', help='lists available item ids')
	parser_list.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
	parser_list.add_argument('-s', '--source', help="the source configuration file to use")
	parser_list.add_argument('item', nargs='*', help="list of ids of items or indicies that should be included")
	parser_list.set_defaults(func=list_command)

	args = parser.parse_args()
	args.func(args)

	#to receive sigint, continue program until all threads stopped
	while threading.active_count() > 1:
		try:
			# Join all threads to receive sigint
			[t.join(1) for t in threading.enumerate() if t.isAlive() and not(t == threading.current_thread() or t == Logger.get_thread())]
			
			#if only the main and logging threads are running stop program
			working = False
			for t in threading.enumerate():
				if t.isAlive() and not(t == threading.current_thread() or t == Logger.get_thread()):
					working = True

			if not working:
				shutdown()
				break

			#print("Running threads:")
			#for t in threading.enumerate():
			#	if not(t == threading.current_thread()) and t.isAlive():
			#		print("* " + t.name)
		except KeyboardInterrupt:
			signal_handler(signal.SIGINT, None)


if __name__ == '__main__':
	main()