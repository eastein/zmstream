#!/usr/bin/env python

import threading
import time
import sys
import zmstream

try :
	mode = getattr(zmstream.Mode, sys.argv[1].upper())
	output_prefix = sys.argv[2]
	input_capture = sys.argv[3]

	auth = None
	try :
		auth = (sys.argv[4], sys.argv[5])
	except IndexError :
		pass
except :
	print 'usage: test.py mjpeg|ffmpeg <output_prefix> <input_source> [user password] [boundary]'
	sys.exit(1)

boundary = None
try :
	boundary = sys.argv[6]
except IndexError :
	pass

ext = 'jpg'

zms = zmstream.ZMThrottle(1, input_capture, auth=auth, boundary=boundary, mode=mode)
zms.start()

i = 0

try :
	for ts, frame in zms.generate() :
		i += 1
		filename = '%s.%06d.%s' % (output_prefix, i, ext)

		print 'writing %s, ts delta is %0.3f' % (filename, time.time() - ts)

		frame.save(filename)

		time.sleep(1)
finally :
	zms.stop()
	zms.join()
