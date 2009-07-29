#!/usr/bin/env python
# -*- coding: utf-8 -*-


import xmlrpclib
from optparse import OptionParser
from urlparse import urlparse

from sys import argv, exit
from fuse import FUSE, Operations, LoggingMixIn
from errno import ENOENT
from stat import S_IFDIR, S_IFLNK, S_IFREG
from time import time
import httplib
import base64
import os
import re

def slash(path):
	"handles first slash"
	if path == '':
		return '/'
	if path[0] != '/':
		return '/' + path
	return path

class Stockage(object):
	directory = dict(
		st_mode=(S_IFDIR | 0555), 
		st_size=0, st_ctime=time(), st_mtime=time(), st_atime=time())
	def __init__(self):
		self.data = {'/': self.directory}
	def addFile(self, path):
		path = slash(path)
		elems = path.split('/')
		file = elems[-1]
		folders = elems[:-1]
		self.data[path] = dict(
			st_mode=(S_IFREG | 0444), 
			st_size=1, st_ctime=time(), st_mtime=time(), st_atime=time())#[FIXME]
		self.addFolder('/'.join(folders))
	def addFolder(self, path):
		path = slash(path)
		if path == '/':
			self.data['/'] = self.directory
			return 
		folders = path.split('/')
		for a in range(2, len(folders)+1):
			self.data['/'.join(folders[:a])] = self.directory
	def __contains__(self, key):
		return slash(key) in self.data
	def __getitem__(self, key):
		return self.data[slash(key)]
	def sonOf(self, path):
		path = slash(path)
		sons = []
		if path == '/':
			path = ['']
			size = 2
		else:
			path = path.split('/')
			size = len(path)+1
		for p in self.data.keys():
			if p == path or p == '/': continue
			elems = p.split('/')
			if len(elems) == size and elems[:-1] == path:
				sons.append(elems[-1])
		return sons

class PieceJointe(LoggingMixIn, Operations):
	"Fuse main object"
	access = None
	flush = None
	getxattr = None
	listxattr = None
	def __init__(self, trac, stockage=None):
		self.trac = trac
		if stockage != None:
			self.stockage = stockage
			return
		self.stockage = Stockage()
		for page in self.trac.xmlrpc.wiki.getAllPages():
			self.stockage.addFolder(page)
			self.trac.multicall.wiki.listAttachments(page)
		for pieces in self.trac.multicall():
			for piece in pieces:
				self.stockage.addFile(piece)
	def __del__(self):
		""
		pass
	def HEAD(self, path):
		"deprecated"
		return self.trac.fetch("/raw-attachment/wiki/%s" % path, "HEAD")
	def open(self, path, flags):
		return 1
	def getattr(self, path, fh=None):
		print "getattr:path:", path
		if path not in self.stockage:
			raise OSError(ENOENT, '')
		attr = self.stockage[path]
		if attr['st_size'] != 0:
			attr['st_size'] = int(self.trac.fetch("/raw-attachment/wiki%s" % path, 'HEAD').getheader('content-length', 0))
		return attr
	def readdir(self, path, fh):
		print "path:", path
		print "fh:", fh
		return ['.', '..'] + self.stockage.sonOf(path)
	def statfs(self, path):
		return dict(f_bsize=512, f_blocks=4096, f_bavail=2048)
	def utimens(self, path, times=None):
		now = time()
		atime, mtime = times if times else (now, now)
		self.files[path]['st_atime'] = atime
		self.files[path]['st_mtime'] = mtime
		return 0
	def read(self, path, size, offset, fh):
		return self.trac.fetch("/raw-attachment/wiki%s" % path).read(offset + size)[offset:offset + size]

class Trac(object):
	def __init__(self, host, user, password):
		self.user = user
		self.password = password
		url = urlparse(host)
		if url.port == None:
			if url.scheme == 'http':
				port = 80
			if url.scheme == 'https':
				port = 443
		else:
			port = url.port
		self.root = "%s://%s:%s@%s:%i%s" % (url.scheme, user, password, url.hostname, port, url.path)
		self.xmlrpc = xmlrpclib.ServerProxy(self.root + "/login/xmlrpc")
		self.multicall = xmlrpclib.MultiCall(self.xmlrpc)
		self.url = url
	def fetch(self, url, method="GET"):
		"http fetching, with authentification"
		base64string = base64.encodestring('%s:%s' % (self.user, self.password))[:-1]
		authheader =  "Basic %s" % base64string
		conn = httplib.HTTPSConnection(self.url.hostname)
		conn.request(method, unicode(self.url.path + url).encode('utf8'), None, {'Authorization': authheader})
		res = conn.getresponse()
		#print res.status, res.reason, url.encode('ascii', 'ignore')
		return res
	def title(self):
		"Trac title"
		return re.compile("<title.*?>\s+(.*?)\s+</title>", re.I).search(self.fetch('').read()).group(1)

class Transport(xmlrpclib.Transport):
	"xmlrpc with basic auth"
	def make_connection(self, host):
		self.host = host
		return httplib.HTTP()
	def __init__(self, login, password):
		self.authheader = "Basic %s" % base64.encodestring('%s:%s' % (login, password))[:-1]
	def send_request(self, connection, handler, request_body):
		connection.putheader(self.authheader)
		connection.putrequest("POST", 'http://%s%s' % (self.host, handler))

if __name__ == "__main__":
	parser = OptionParser()
	parser.add_option("-u", "--user", dest="user", default=None)
	parser.add_option("-p", "--password", dest="password", default=None)
	parser.add_option("-H", "--host", dest="host", default=None)
	parser.add_option("-t", "--test", dest="test", default=False, action="store_true")

	(options, args) = parser.parse_args()

	if options.user == None or options.password == None or options.host == None:
		print """--user, --password and --host must be set, 
try :
%s --help""" % argv[0]
		exit()
	trac = Trac(options.host, options.user, options.password)
	title = trac.title()
	print title
	
	if options.test:
		import unittest
		import cPickle as pickle
		import os.path
		PAGES = "pages.cache"
		if os.path.exists(PAGES):
			pages = pickle.load(file(PAGES, 'r'))
		else:
			pages = trac.wiki.getAllPages()
			pickle.dump(pages, file(PAGES, 'w'))
		PIECES = 'pieces.cache'
		if os.path.exists(PIECES):
			pieces = pickle.load(file(PIECES, 'r'))
		else:
			for page in pages:
				multicall.wiki.listAttachments(page)
			pieces = multicall()
			pickle.dump(pieces, file(PIECES, 'w'))
		class StockageTest(unittest.TestCase):
			def setUp(self):
				self.stockage = Stockage()
				for page in pages:
					self.stockage.addFolder(page)
				for p in pieces:
					for piece in p:
						self.stockage.addFile(piece)
				self.pieceJointe = PieceJointe(self.stockage)
			def testPage(self):
				#print self.stockage.data.keys()
				self.assert_('/' in self.stockage)
				self.assert_(not '' in self.stockage)
			def testSonOf(self):
				root = self.stockage.sonOf('/')
				self.assert_(not ('' in root))
				self.assert_(len(root) > 0)
				root = self.stockage.sonOf('/Drupal')
				self.assert_(len(root) > 0)
			def testHead(self):
				for p in pieces:
					for piece in p:
						print self.pieceJointe.HEAD(piece).getheaders()
		unittest.main()
	else:
		fuse = FUSE(PieceJointe(trac), argv[1], 
			foreground=False, volname=title,
			auto_cache=True, noappledouble=True,
			noapplexattr=True, volicon="Trac.icns" )
		#os.getcwd() + 
