import hashlib
import time


def authtoken(secret, username, password):
    t = time.localtime()
    grist = secret + username + '*' + hashlib.sha1(hashlib.sha1(password).digest()).hexdigest().upper()
    grist += str(t.tm_hour)
    grist += str(t.tm_mday)
    grist += str(t.tm_mon - 1)
    grist += str(t.tm_year - 1900)

    return hashlib.md5(grist).hexdigest()
