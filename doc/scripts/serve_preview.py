"""Serve a built documentation preview on loopback, with gzip and revalidation."""
from __future__ import annotations

import argparse
from email.utils import parsedate_to_datetime
from functools import lru_cache, partial
import gzip
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
from pathlib import Path


@lru_cache(maxsize=64)
def _compressed(path, mtime_ns, size):
    return gzip.compress(Path(path).read_bytes(), compresslevel=6, mtime=0)


def _accepts_gzip(header):
    for item in header.lower().split(','):
        parts = item.strip().split(';')
        if parts[0] != 'gzip':
            continue
        try:
            return all(float(p.strip()[2:]) > 0 for p in parts[1:] if p.strip().startswith('q='))
        except ValueError:
            return False
    return False


class PreviewHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Vary', 'Accept-Encoding')
        super().end_headers()

    def send_head(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file() or path.suffix.lower() not in {'.html', '.json', '.js', '.css', '.svg', '.txt'}:
            return super().send_head()
        if not _accepts_gzip(self.headers.get('Accept-Encoding', '')):
            return super().send_head()
        stat = path.stat()
        if stat.st_size < 1024:
            return super().send_head()
        etag = f'"{stat.st_mtime_ns:x}-{stat.st_size:x}-gzip"'
        unchanged = self.headers.get('If-None-Match') == etag
        since = self.headers.get('If-Modified-Since')
        if since and not self.headers.get('If-None-Match'):
            try:
                unchanged = int(stat.st_mtime) <= parsedate_to_datetime(since).timestamp()
            except (ValueError, TypeError, OverflowError):
                pass
        if unchanged:
            self.send_response(304)
            self.send_header('ETag', etag)
            self.end_headers()
            return None
        content = _compressed(str(path), stat.st_mtime_ns, stat.st_size)
        self.send_response(200)
        self.send_header('Content-Type', self.guess_type(str(path)))
        self.send_header('Content-Encoding', 'gzip')
        self.send_header('Content-Length', str(len(content)))
        self.send_header('Last-Modified', self.date_time_string(stat.st_mtime))
        self.send_header('ETag', etag)
        self.end_headers()
        return io.BytesIO(content)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error('Build directory does not exist')
    # Deliberately local: any remote preview uses the existing private proxy.
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(PreviewHandler, directory=str(args.directory.resolve())))
    print(f'Serving {args.directory} at http://127.0.0.1:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
