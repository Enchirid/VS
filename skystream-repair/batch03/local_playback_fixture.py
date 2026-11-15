#!/usr/bin/env python3
"""Batch03: deterministic local authorized media transport regression.

No third-party media sites. The generated test pattern is original and silent.
This validates HTTP auth headers, HLS playlist/segment delivery, independent
subtitle retrieval and decoding via ffprobe. It does not drive Flutter's VLC GUI.
"""
import http.server
import pathlib
import socketserver
import subprocess
import tempfile
import threading
import json
import urllib.request

def run(cmd):
    r=subprocess.run(cmd,check=True,text=True,capture_output=True,timeout=120)
    return r.stdout

def main():
    with tempfile.TemporaryDirectory() as t:
        root=pathlib.Path(t)
        run(["ffmpeg","-hide_banner","-loglevel","error","-y",
             "-f","lavfi","-i","testsrc2=size=320x180:rate=15",
             "-f","lavfi","-i","sine=frequency=440:sample_rate=48000",
             "-t","4","-c:v","mpeg2video","-b:v","500k","-c:a","mp2","-b:a","96k",
             "-f","hls","-hls_time","1","-hls_list_size","0",
             str(root/"master.m3u8")])
        (root/"subtitles.srt").write_text("1\n00:00:00,000 --> 00:00:02,000\nOriginal sample caption\n",encoding="utf-8")
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self,*args,**kw):
                super().__init__(*args,directory=str(root),**kw)
            def do_GET(self):
                if self.headers.get("X-Playback-QA")!="Batch03-Authorized":
                    self.send_error(403)
                    return
                return super().do_GET()
            def log_message(self,*args):pass
        class Server(socketserver.ThreadingMixIn,http.server.HTTPServer):
            daemon_threads=True
            allow_reuse_address=True
        server=Server(("127.0.0.1",0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            base=f"http://127.0.0.1:{server.server_port}"
            forbidden=urllib.request.Request(base+"/master.m3u8")
            try:
                urllib.request.urlopen(forbidden,timeout=8)
                raise AssertionError("Protected fixture accepted missing playback header")
            except urllib.error.HTTPError as error:
                assert error.code==403
            headers={"X-Playback-QA":"Batch03-Authorized","Referer":"https://fixture.invalid/authorized"}
            playlist=urllib.request.urlopen(urllib.request.Request(base+"/master.m3u8",headers=headers),timeout=8).read().decode()
            segments=[x.strip() for x in playlist.splitlines() if x.strip() and not x.startswith("#")]
            assert segments and all((root/x).is_file() for x in segments)
            for segment in segments:
                assert urllib.request.urlopen(urllib.request.Request(base+"/"+segment,headers=headers),timeout=8).status==200
            subtitle=urllib.request.urlopen(urllib.request.Request(base+"/subtitles.srt",headers=headers),timeout=8).read().decode()
            assert "Original sample caption" in subtitle
            probe=json.loads(run(["ffprobe","-v","quiet","-print_format","json","-show_streams",
                                  "-headers","X-Playback-QA: Batch03-Authorized\r\n",
                                  base+"/master.m3u8"]))
            types={s.get("codec_type") for s in probe["streams"]}
            assert {"video","audio"}.issubset(types),types
            print(json.dumps({"test":"authorized local playback transport","result":"PASS",
                              "httpHeaderRequired":True,"hlsSegments":len(segments),
                              "audioDecodedByFFprobe":True,"videoDecodedByFFprobe":True,
                              "subtitleFetch":True,"guiVlcPlaybackTested":False}))
        finally:
            server.shutdown()
            server.server_close()

if __name__=="__main__":
    import urllib.error
    main()
