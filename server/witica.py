#!/usr/bin/env python
# coding=utf-8

import time, signal, sys
import threading
import argparse
import codecs, locale
from kitchen.text.converters import getwriter

from witicapy.site import Site
from witicapy import *
from witicapy.log import *
from witicapy.metadata import extractor
from witicapy.source import ItemChanged, ItemRemoved
from witicapy.targets import target, web, statichtml
from witicapy.check import IntegrityChecker
from witicapy.util import sstr, suni, throw

VERSION = "0.8.3"

currentsite = None

def shutdown():
	log("Shutting down...", Logtype.INFO)
	try:
		if currentsite:
			currentsite.shutdown()
	except Exception, e:
		log_exception("Shutdown failed.", Logtype.ERROR)
	finally:
		seconds_left = 20
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

def signal_handler(signal, frame):
	log("Shutdown requested by user.", Logtype.WARNING)
	shutdown()

def log(msg, logtype = Logtype.NONE):
	Logger.log("witica", msg, logtype)

def log_exception(msg, logtype = Logtype.NONE, exc_info=None):
	Logger.log_exception("witica", msg, logtype, exc_info)

def update_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)
	try:
		log(args.source)
		currentsite = Site(args.source, target_ids = args.targets)
		currentsite.source.start_update(continuous = args.deamon)
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()

def rebuild_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)
	try:
		currentsite = Site(args.source, target_ids = args.targets)
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	items = get_matching_items(currentsite.source, args)

	for item in items:
		try:
			for path in item.files:
				currentsite.source.changeEvent(currentsite.source, ItemChanged(currentsite.source, item.item_id, path))	
		except Exception, e:
			log_exception("Item '" + item.item_id + "'' could not be enqued for rebuilding.", Logtype.ERROR)	
	currentsite.source.stoppedEvent(currentsite.source, None)

def remove_command(args):
	#TODO: remove (deprecated)
	global currentsite
	Logger.start(verbose=args.verbose)
	try:
		currentsite = Site(args.source, target_ids = args.targets)
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	items = get_matching_items(currentsite.source, args)

	for item in items:
		try:
			for path in item.files:
				currentsite.source.changeEvent(currentsite.source, ItemRemoved(currentsite.source, item.item_id))	
		except Exception, e:
			log_exception("Item '" + item.item_id + "'' could not be enqued for removing.", Logtype.ERROR)	
	currentsite.source.stoppedEvent(currentsite.source, None)

def check_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)

	try:
		currentsite = Site(args.source, target_ids = [])
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	items = get_matching_items(currentsite.source, args)

	numberfaults = 0
	ic = IntegrityChecker(currentsite.source)
	for item in items:
		#log("Checking item " + item.item_id + "...")
		for fault in ic.check(item):
			log(sstr(fault), Logtype.WARNING)
			numberfaults += 1
	log("Checked " + str(len(items)) + " items. " + str(numberfaults) + " integrity fault" + (" was" if numberfaults==1 else "s were") + " found.", Logtype.WARNING)
	currentsite.source.stoppedEvent(currentsite.source, None)

def items_command(args):
	global currentsite
	Logger.start(verbose=args.verbose)

	try:
		currentsite = Site(args.source, target_ids = [])
	except Exception, e:
		log_exception("Site could not be initialized.", Logtype.ERROR)
		shutdown()
		return

	items = get_matching_items(currentsite.source, args)
	s = u"\n"
	count = 0
	for item in items:
		s += item.item_id + u"\n"
		count += 1
		if count == 100:
			log(s, Logtype.WARNING)
			s = u"\n"
			count = 0
	if count > 0:
		log(s, Logtype.WARNING)

	log("Source contains " + str(len(items)) + (" matching" if (len(args.item) > 0) else "") + " items.", Logtype.WARNING)
	currentsite.source.stoppedEvent(currentsite.source, None)

def get_matching_items(source, args):
	items = []
	if len(args.item) > 0:
		#return matching items
		for idpattern in args.item:
			items.extend(currentsite.source.items.get_items(idpattern))
	elif len(args.item) == 0:
		items = source.items
	return items

#initialize witica

signal.signal(signal.SIGINT, signal_handler) #abort on CTRL-C

UTF8Writer = getwriter('utf8')
sys.stdout = UTF8Writer(sys.stdout)

extractor.register("item", extractor.JSONExtractor)
extractor.register("json", extractor.JSONExtractor)
extractor.register("md", extractor.MDExtractor)
extractor.register("txt", extractor.MDExtractor)
extractor.register("jpg", extractor.ImageExtractor)
extractor.register("jpeg", extractor.ImageExtractor)

target.register("WebTarget", web.WebTarget)
target.register("StaticHtmlTarget", statichtml.StaticHtmlTarget)

parser = argparse.ArgumentParser(description="Reads contents from a source, converts them and publishes to one or more targets.")
parser.add_argument('-v', '--version', action='version', version='%(prog)s ' + VERSION)

subparsers = parser.add_subparsers(title='sub-commands', help='sub-commands')

#update command parser
parser_update = subparsers.add_parser('update', help='fetch changes and update targets')
parser_update.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
parser_update.add_argument('-s', '--source', required=True, help="the source configuration file to use")
parser_update.add_argument('-d', '--deamon', action='store_true', help="keep running in background and process incoming events")
parser_update.add_argument('-t', '--targets', nargs='+', help="list of ids of targets that should be used for the conversion")
parser_update.set_defaults(func=update_command)


parser_rebuild = subparsers.add_parser('rebuild', help='update single items or indicies')
parser_rebuild.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
parser_rebuild.add_argument('-s', '--source', required=True, help="the source configuration file to use")
parser_rebuild.add_argument('-t', '--targets', nargs='+', help="list of ids of targets that should be used for the conversion, default: all")
parser_rebuild.add_argument('item', nargs='*', help="list of ids of items or indicies that should be updated")
parser_rebuild.set_defaults(func=rebuild_command)

parser_remove = subparsers.add_parser('remove', help='remove single items or indicies (deprecated)')
parser_remove.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
parser_remove.add_argument('-s', '--source', required=True, help="the source configuration file to use")
parser_remove.add_argument('-t', '--targets', nargs='+', help="list of ids of targets that should be used for the conversion, default: all")
parser_remove.add_argument('item', nargs='*', help="list of ids of items or indicies that should be removed")
parser_remove.set_defaults(func=remove_command)

parser_check = subparsers.add_parser('check', help='checks the integrity of the source')
parser_check.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
parser_check.add_argument('-s', '--source', required=True, help="the source configuration file to use")
parser_check.add_argument('item', nargs='*', help="list of ids of items or indicies that should be checked")
parser_check.set_defaults(func=check_command)

parser_items = subparsers.add_parser('items', help='lists available item ids')
parser_items.add_argument('-V', '--verbose', action='store_true', help="show also info messages and debbuging info")
parser_items.add_argument('-s', '--source', required=True, help="the source configuration file to use")
parser_items.add_argument('item', nargs='*', help="list of ids of items or indicies that should be included")
parser_items.set_defaults(func=items_command)

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