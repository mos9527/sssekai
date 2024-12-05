import os, logging, datetime, time, sys
from shutil import copyfileobj
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from sssekai import __version__
from sssekai.abcache.fs import AbCacheFilesystem
from rich import filesize

logger = logging.getLogger("abserve")
fs: AbCacheFilesystem = None


class AbServeHTTPRequestHandler(BaseHTTPRequestHandler):
    ENCODING = "utf-8"

    def format_listing(self, path):
        t0 = time.time()
        r = []
        path = path or "/"
        title = f"Directory listing for {path}"
        r = (
            f"<!DOCTYPE HTML>"
            f'<html lang="en">'
            f"<head>"
            f'<meta charset="utf-8">'
            f"<style>"
            f"body {{ font-family: monospace; }}"
            f"body {{ background-color: black; color: white; }}"
            f"a,i {{ color: lightblue; }}"
            f"</style>"
            f"<title>{title}</title>"
            f"</head>"
            f"<body><h1>{title}</h1>"
            f"<i>children: {len(fs.ls(path))},</i>"
            f"<i>total number of files: {fs.info(path)['file_count']},</i>"
            f"<i>total size: {filesize.decimal(fs.info(path)['total_size'])}</i><br>"
            f'<hr><ul><li><a href="..">..</a></li>'
        )
        for entry in sorted(
            fs.listdir(path), key=lambda x: (x["type"], x["name"], x["size"])
        ):
            # Directory then Files, then sorted lexically, then size
            name = entry["name"]

            nodename = name.split("/")[-1]
            linkname = name
            displayname = nodename
            extra_tags = " ".join([f'{k}="{v}"' for k, v in entry.items()])
            if fs.isdir(name):
                linkname += "/"
            else:
                displayname += f" ({filesize.decimal(entry['size'])})"
            r += f'<li><a {extra_tags} href="{linkname}">{displayname}</a></li>'
        r += "</ul><hr>"
        r += f"<i>sssekai v{__version__} running on Python {sys.version}</i><br>"
        r += f"<i>{fs.cache}</i><br>"
        r += "<i>page rendered in %.3fms, server time: %s</i>" % (
            (time.time() - t0) * 1000,
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
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
                # XXX: Size reported by bundles' metadata is not accurate.
                # If a wrong size is reported, the browser will reject the download.
                # TODO: Figure out why the size is wrong.
                # self.send_header("Content-Length", fs.stat(path)["size"])
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


def main_abserve(args):
    global fs
    import fsspec

    db_path = os.path.expanduser(os.path.normpath(args.db))
    fs = fsspec.filesystem("abcache", fo=db_path)
    if args.fuse:
        import fsspec.fuse

        fsspec.fuse.run(fs, "", args.fuse)
    else:
        with ThreadingHTTPServer(
            (args.host, args.port), AbServeHTTPRequestHandler
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
