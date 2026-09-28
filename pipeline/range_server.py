"""Static file server with HTTP Range support, so local <video> can seek and loop like on a real host."""
import os, re, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer


class RangeHandler(SimpleHTTPRequestHandler):
    def send_head(self):
        rng = self.headers.get('Range')
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r'bytes=(\d*)-(\d*)', rng)
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else max(size - int(m.group(2)), 0)
        end = int(m.group(2)) if m.group(1) and m.group(2) else size - 1
        end = min(end, size - 1)
        f = open(path, 'rb')
        f.seek(start)
        self.send_response(206)
        self.send_header('Content-Type', self.guess_type(path))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        self.send_header('Content-Length', str(end - start + 1))
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, src, dst):
        n = getattr(self, '_remaining', None)
        if n is None:
            return super().copyfile(src, dst)
        while n > 0:
            buf = src.read(min(65536, n))
            if not buf:
                break
            dst.write(buf)
            n -= len(buf)

    def end_headers(self):
        self.send_header('Accept-Ranges', 'bytes')
        super().end_headers()


os.chdir(sys.argv[2] if len(sys.argv) > 2 else '.')
ThreadingHTTPServer(('127.0.0.1', int(sys.argv[1]) if len(sys.argv) > 1 else 8765), RangeHandler).serve_forever()
