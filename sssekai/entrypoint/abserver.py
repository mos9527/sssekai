import os, logging
from shutil import copyfileobj
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from sssekai import __version__
from sssekai.abcache.fs import AbCacheFilesystem
from rich import filesize

logger = logging.getLogger("abserver")
fs: AbCacheFilesystem = None


class AbServerHTTPRequestHandler(BaseHTTPRequestHandler):
    ENCODING = "utf-8"

    def format_listing(self, path):
        r = []
        title = f"Directory listing for {path}"
        r = (
            f"<!DOCTYPE HTML>"
            f'<html lang="en">'
            f"<head>"
            f'<meta charset="utf-8">'
            f"<style>"
            f"body {{ font-family: monospace; }}"
            f"body {{ background-color: black; color: white; }}"
            f"a {{ color: lightblue; }}"
            f"</style>"
            f"<title>{title}</title>"
            f"</head>"
            f"<body><h1>{title}</h1>"
            f"<hr><ul>"
            f'<li><a href="..">..</a></li>'
        )
        for entry in sorted(
            fs.listdir(path), key=lambda x: (x["type"], x["name"], x["size"])
        ):
            # Directory then Files, then sorted lexically, then size
            name = entry["name"]
            
            nodename = name.split("/")[-1]
            linkname = name
            displayname = nodename
            if fs.isdir(name):
                linkname += "/"
            else:
                fsize = filesize.decimal(entry["size"])
                displayname += f" ({fsize})"
            r += '<li><a href="%s">%s</a></li>' % (linkname, displayname)
        r += "</ul><hr>"
        r += "<i>sssekai v%s, %s</i>" % (__version__, fs.cache)
        r += "</body></html>"
        encoded = r.encode(self.ENCODING, "surrogateescape")
        return encoded

    def handle_path(self, path):
        pass

    def do_GET(self):
        path = self.path.rstrip("/")
        if not fs.exists(path):
            self.send_error(404, "File not found")
            return
        else:
            if fs.isfile(path):
                self.send_response(200)
                self.send_header("Content-type", "application/octet-stream")
                self.send_header("Content-Length", fs.stat(path)["size"])
                self.end_headers()
                with fs.open(path, "rb") as f:
                    copyfileobj(f, self.wfile)
            else:
                listing = self.format_listing(path)
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.send_header("Content-Length", len(listing))
                self.end_headers()
                self.wfile.write(listing)


def main_abserver(args):
    global fs
    import fsspec
    db_path = os.path.expanduser(os.path.normpath(args.db))
    fs = fsspec.filesystem("abcache", fo=db_path)
    if args.fuse:
        import fsspec.fuse
        fsspec.fuse.run(fs, "", args.fuse)
    else:
        with ThreadingHTTPServer(
            (args.host, args.port), AbServerHTTPRequestHandler
        ) as httpd:
            try:
                host, port = httpd.socket.getsockname()[:2]
                url_host = f"[{host}]" if ":" in host else host
                logger.info(
                    f"Serving HTTP on {host} port {port} "
                    f"> http://127.0.0.1:{port}/"
                    f"> http://{url_host}:{port}/"
                    f""
                    f"Press Ctrl-C to stop."
                )
                httpd.serve_forever()
            except Exception as e:
                logger.info("Exiting. %s" % e)
