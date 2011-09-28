import hashlib
import time

def authtoken(secret, username, pwhash) :
	t = time.localtime()
	grist = secret + username + pwhash
	grist += str(t.tm_hour)
	grist += str(t.tm_mday)
	grist += str(t.tm_mon - 1)
	grist += str(t.tm_year - 1900)

	return hashlib.md5(grist).hexdigest()
