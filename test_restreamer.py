#!/usr/bin/env python

import threading
import time
import sys
import zmstream
import socket

try :
	mode = getattr(zmstream.Mode, sys.argv[2].upper())
	input_capture = sys.argv[3]
	output_addr = sys.argv[1]

	auth = None
	try :
		auth = (sys.argv[4], sys.argv[5])
	except IndexError :
		pass
except :
	print 'usage: test.py <output addr> mjpeg|ffmpeg <input_source> [user password]'
	sys.exit(1)

boundary = None

ext = 'jpg'

zms = zmstream.ZMThrottle(1, input_capture, auth=auth, boundary=boundary, mode=mode)
zms.start()

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(30.0)
host,port = output_addr.split(':')
sock.bind((host, int(port)))
sock.listen(1)

server = zmstream.Server(sock)

try :
	for ts, frame in zms.generate() :
		server.send(frame)
finally :
	zms.stop()
	zms.join()
