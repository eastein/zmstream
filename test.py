import threading
import time
import sys
import zmstream

output_prefix = sys.argv[1]
input_capture = sys.argv[2]

auth = None
try :
	auth = (sys.argv[3], sys.argv[4])
except IndexError :
	pass

boundary = None
try :
	boundary = sys.argv[5]
except IndexError :
	pass

ext = 'jpg'

zms = zmstream.ZMThrottle(1, input_capture, auth=auth, boundary=boundary)
zms.start()

i = 0

try :
	for ts, frame in zms.generate() :
		i += 1
		filename = '%s.%06d.%s' % (output_prefix, i, ext)

		print 'writing %s, ts delta is %0.3f' % (filename, time.time() - ts)
		fhw = open(filename, 'w')
		try :
			fhw.write(frame)
		finally :
			fhw.close()

		time.sleep(1)
finally :
	zms.stop()
	zms.join()
