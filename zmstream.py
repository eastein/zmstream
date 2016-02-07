import urlparse
import socket
import select
import time
import base64
import os
import os.path
import threading
import Queue
import zmhash
from PIL import ImageFile
import socket


class ZMSException(Exception):
    pass


class BadProtocol(ZMSException):
    pass


class RemoteError(ZMSException):
    pass


class Timeout(RemoteError):
    pass


class SocketError(RemoteError):
    pass


class Mode(object):
    MJPEG = 1
    FFMPEG = 2
    IMAGESDIR = 3

    st_min = 1
    st_max = 3

    @classmethod
    def check(cls, st):
        assert isinstance(st, int)
        assert (st >= Mode.st_min and st <= Mode.st_max)


class ZMStreamer(object):
    ST_FILE = 1
    ST_SOCKET = 2

    ZF_FRAME_HEADER = '%s\r\n'

    # TODO handle when the hash secret is given but no auth, that's broken
    def __init__(self, timeout, input_capture, failure_timeout=10, auth=None, zm_auth_hash_secret=None, boundary=None, mode=Mode.MJPEG):
        self.timeout = timeout
        self.input_capture = input_capture
        self.failure_timeout = failure_timeout
        self.ok = True
        self.auth = auth
        self.zm_auth_hash_secret = zm_auth_hash_secret
        if boundary:
            self.boundary = '--' + boundary
        else:
            self.boundary = None
        Mode.check(mode)
        self.mode = mode

    def __del__(self):
        if hasattr(self, 'fh'):
            try:
                self.fh.close()
            except:
                pass

    def rf(self, size):
        if self.stream_type == self.ST_FILE:
            r = self.fh.read(size)
        if self.stream_type == self.ST_SOCKET:
            r = self.fh.recv(size)
        return r

    def send_all(self, sock, s):
        now = 0
        need = len(s)
        while now < need:
            self.abortcheck()
            r, w, x = select.select([], [sock], [], self.timeout)
            if w:
                now += sock.send(s[now:])

    def discard_until(self, buf, including):
        buf, dat = self.read_until(buf, including)
        return buf

    def read_bytes(self, buf, n):
        while len(buf) < n:
            self.abortcheck()
            r, w, x = select.select([self.fh], [], [], self.timeout)
            if r:
                buf += self.rf(min(self.chunk, n - len(buf)))
        dat = buf[0:n]
        buf = buf[n:]
        return buf, dat

    def read_until(self, buf, including):
        while including not in buf:
            self.abortcheck()
            r, w, x = select.select([self.fh], [], [], self.timeout)
            if r:
                buf += self.rf(self.chunk)
        offset = buf.find(including)
        before_offset = offset + len(including)
        dat = buf[0:offset]
        buf = buf[before_offset:]
        return buf, dat

    def stop(self):
        self.ok = False

    def abortcheck(self):
        if not self.ok:
            raise StopIteration
        if hasattr(self, 'abort_ts'):
            if time.time() > self.abort_ts:
                raise Timeout

    def generate(self):
        if self.mode == Mode.MJPEG:
            for f in self.generate_mjpeg():
                yield f
        elif self.mode == Mode.FFMPEG:
            for f in self.generate_ffmpeg():
                yield f
        elif self.mode == Mode.IMAGESDIR:
            for f in self.generate_imagesdir():
                yield f
        else:
            assert False  # what are you even doing, user? Do not meddle with the affairs of dragons.

    def generate_imagesdir(self):
        existing_files = set(os.listdir(self.input_capture))
        while True:
            self.abortcheck()

            now_files = set(os.listdir(self.input_capture))

            # support JPG and PNG for now
            new_files = [fn for fn in list(
                now_files - existing_files) if (fn.lower().endswith('.jpg') or fn.lower().endswith('.jpeg') or fn.lower().endswith('.png'))]

            if new_files:
                # Assumes that files are sorted sequentially.... if not, too bad. Everything will be wrong.
                new_files.sort()
                for f in new_files:
                    p = ImageFile.Parser()
                    p.feed(open(os.path.join(self.input_capture, f)).read())
                    yield p.close()
            else:
                time.sleep(0.0066733400)  # approximate 29.97 fps with minimal jitter (5x as fast)

            # save 'now'
            existing_files = now_files

    def generate_ffmpeg(self):
        import pyffmpeg
        stream = pyffmpeg.VideoStream()
        stream.open(self.input_capture.encode('ascii', 'ignore'))
        frame = 0
        while True:
            self.abortcheck()
            yield stream.GetFrameNo(frame)
            frame += 1

    def generate_mjpeg(self):
        if self.input_capture.startswith('http'):
            o = urlparse.urlparse(self.input_capture)

            if o.scheme != 'http':
                raise BadProtocol("only http supported")

            host = o.netloc.split(':')[0]
            port = o.port
            if not port:
                port = 80
            else:
                port = int(port)

            path = o.path
            netloc = o.netloc
            query = o.query

            if query:
                path = '%s?%s' % (path, query)

            basic_auth = ''
            if self.auth:
                if self.zm_auth_hash_secret:
                    path += zmhash.authtoken(self.zm_auth_hash_secret, self.auth[0], self.auth[1])
                else:
                    basic_auth = '\r\nAuthorization: Basic %s' % base64.b64encode(
                        '%s:%s' % (self.auth[0], self.auth[1]))

            # for the curious: the reason I'm not using urllib2 here is that I can't use
            # select on the stream it creates.  I'd prefer to use it, but them's the breaks and this works.
            self.fh = socket.create_connection((host, port))
            request = 'GET %s HTTP/1.1\r\nHost: %s%s\r\n\r\n' % (path, netloc, basic_auth)

            self.send_all(self.fh, request)

            self.stream_type = self.ST_SOCKET
        else:
            self.fh = open(self.input_capture, 'r')
            self.stream_type = self.ST_FILE

        self.chunk = 1024

        try:
            self.abort_ts = time.time() + self.failure_timeout
            buf = ''

            # do we need to auto-detect?
            if self.boundary is None:
                buf = self.discard_until(buf, '\r\n\r\n')

                buf, self.boundary = self.read_until(buf, '\r\n')

                # boundary now has the boundary line in it. great! now put it back so we
                # can align (jumping into the cycle below)
                buf = self.boundary + '\r\n' + buf

            # first, read until there's a ZF_FRAME_HEADER
            while True:
                self.abort_ts = time.time() + self.failure_timeout

                # we haven't already aligned to a zoneminder frame. align now.
                buf = self.discard_until(buf, ZMStreamer.ZF_FRAME_HEADER % self.boundary)
                header = True
                headers = {}
                while header:
                    self.abortcheck()
                    buf, header = self.read_until(buf, '\r\n')
                    if header:
                        header = header.lower()
                        point_offset = header.find(':')
                        if point_offset > 0:
                            header_name = header[0:point_offset]
                            header_value = header[point_offset + 1:]
                            while header_value.startswith(' '):
                                header_value = header_value[1:]
                            headers[header_name] = header_value

                cl = None
                if 'content-length' in headers:
                    try:
                        cl = int(headers['content-length'])
                    except ValueError:
                        pass

                if cl is not None:
                    buf, body = self.read_bytes(buf, cl)
                else:
                    buf, body = self.read_until(buf, (ZMStreamer.ZF_FRAME_HEADER % self.boundary))

                p = ImageFile.Parser()
                p.feed(body)
                yield p.close()

                self.abortcheck()
        finally:
            self.fh.close()


class TimestampingThrottle(threading.Thread):
    SHUTDOWN = 1
    TIMEOUT = 2
    SOCKETERROR = 3

    def __init__(self, generator, generatorstop=None, failure_timeout=10):
        self.failure_timeout = failure_timeout
        self.ok = True
        self.died = False
        self.generator = generator
        self.generatorstop = generatorstop
        self.q = Queue.Queue()
        threading.Thread.__init__(self)

    def stop(self):
        self.ok = False
        self.generatorstop()

    def run(self):
        try:
            # TODO catch exceptions here and offer a hook to call when this is dying
            for frame in self.generator:
                if not self.ok:
                    self.q.put(TimestampingThrottle.SHUTDOWN)
                    break
                self.q.put((time.time(), frame))
        except Timeout:
            self.q.put(TimestampingThrottle.TIMEOUT)
        except socket.error, se:
            self.q.put(TimestampingThrottle.SOCKETERROR)

    def qcheck(self, v):
        if not self.ok or v == TimestampingThrottle.SHUTDOWN:
            raise StopIteration
        elif v == TimestampingThrottle.TIMEOUT:
            raise Timeout
        elif v == TimestampingThrottle.SOCKETERROR:
            raise SocketError

    def qg(self, real_timeout, parts):
        # wait up to real_timeout total, but cut it into parts so we can quit in the middle.
        pt = real_timeout / float(parts)
        for i in range(parts):
            try:
                return self.q.get(timeout=pt)
            except Queue.Empty:
                if not self.ok:
                    raise StopIteration
        raise Queue.Empty

    def get(self):
        if not self.ok:
            raise StopIteration

        try:
            v = self.qg(self.failure_timeout, 20)
            self.qcheck(v)
            while True:
                try:
                    v = self.q.get(block=False)
                    self.qcheck(v)
                except Queue.Empty:
                    return v
        except Queue.Empty:
            if self.ok:
                raise Timeout
            raise StopIteration

    def generate(self):
        while True:
            yield self.get()


class ZMThrottle(TimestampingThrottle):

    def __init__(self, *args, **kwargs):
        zms = ZMStreamer(*args, **kwargs)
        TimestampingThrottle.__init__(self, zms.generate(), zms.stop, failure_timeout=zms.failure_timeout)


class Server(threading.Thread):

    """
    Given a set of sockets that are bound already, accept connections on them and serve
    HTTP motion jpeg over them.

    Do frame drops, so if the remote client falls behind only
    queue QUEUE_FRAMEs frame for sending per stream.  Time out frame transmissions at FRAME_TIMEOUT_MULT
    times the time per frame, at which point the server will close the connection to the client.

    Time per frame should be a running average based on how much time elapsed between
    the completions of the inbound copies of the last FPS_TIMING_FRAMES frames. Until this
    has been established, fps will be assumed to be DEFAULT_FPS.

    Later features: handle more than one stream per server; right now, we don't have any dispatch. One server is
    for one stream.
    """

    FRAME_TIMEOUT_MULT = 30
    FPS_TIMING_FRAMES = 10
    DEFAULT_FPS = 10
    QUEUE_FRAMES = 1

    # TODO analyze ~/git/gololgo network selecting socket code - make sure to handle all the same errors that it does.

    class RetransmitterThread(threading.Thread):

        def __init__(self, src, dst, autorun=True):
            self.ok = True
            self.src = src
            self.dst = dst
            threading.Thread.__init__(self)
            if autorun:
                self.start()

        def stop(self):
            self.ok = False

        def run(self):
            while self.ok:
                for img in self.src.generate():
                    self.dst.send(img)

    class Conn(object):

        class State:
            # perspective is always the server's perspective, not the client.

            OPENED = 0    # connection is opened, but isn't ready to send frames to yet
            READY = 1     # connection is ready to send a new frame
            RECVING = 2   # connection is recving into the inbuf
            SENDING = 3   # connection is sending from the outbuf

        def __init__(self, server, sock, addr):
            self.server = server
            self.sock = sock
            self.addr = addr
            self.inbuf = str()
            self.outbuf = str()
            self.fq = Queue.Queue(maxsize=server.QUEUE_FRAMES)
            self.set_state(self.State.OPENED)

        def set_state(self, st):
            self.state = st
            self.state_time = time.time()

        def tick(self):
            pass
            # TODO implement; this function will be called on each connection object after every
            # IO phase of the thread, and should perform no blocking operations. It should also avoid
            # spending too much CPU time.

    def __init__(self, socket, autorun=True):
        self.fps = self.DEFAULT_FPS
        self.socket = socket
        self.conns = set()

        self.ok = True
        threading.Thread.__init__(self)
        if autorun:
            self.start()

    def sendfrom(self, src, autorun=True):
        return RetransmitterThread(src, self, autorun=autorun)

    def send(self, img):
        # TODO handle opencv, string (assumed to be jpeg data), PIL image. For now take jpeg string only.

        print time.ctime(), "SENDING A FRAME [fake]"  # FIXME either log or something else

    def stop(self):
        self.ok = False

    def run(self):
        while self.ok:
            try:
                sock, addr = self.socket.accept()

                self.conns.add(self.Conn(self, sock, addr))

            except socket.timeout:
                print time.ctime(), 'timeout on accept'  # FIXME either log or something else
