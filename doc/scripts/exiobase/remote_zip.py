"""Read selected original ZIP members with verified HTTP byte ranges and ZIP CRCs."""
import io,re,time,zipfile,threading
from collections import OrderedDict
import requests

class RequestPacer:
    def __init__(self):self.lock=threading.Lock();self.next=0;self.interval=.75
    def wait(self):
        with self.lock:
            now=time.monotonic();scheduled=max(now,self.next);self.next=scheduled+self.interval
        if scheduled>now:time.sleep(scheduled-now)
    def backoff(self,seconds):
        with self.lock:self.next=max(self.next,time.monotonic()+seconds)

PACER=RequestPacer()

class RemoteArchive(io.RawIOBase):
    def __init__(self,url,size,session=None):
        self.url=url;self.size=size;self.pos=0;self.session=session or requests.Session();self.cache=OrderedDict();self.downloaded=0
    def seekable(self):return True
    def readable(self):return True
    def tell(self):return self.pos
    def seek(self,offset,whence=0):
        self.pos=offset if whence==0 else self.pos+offset if whence==1 else self.size+offset
        if self.pos<0:raise ValueError('Negative archive seek')
        return self.pos
    def read(self,n=-1):
        if n<0:n=self.size-self.pos
        if not n or self.pos>=self.size:return b''
        end=min(self.size,self.pos+n)
        for start,data in self.cache.items():
            if start<=self.pos and end<=start+len(data):
                result=data[self.pos-start:end-start];self.pos=end;return result
        position=self.pos
        start=self.size-65536 if self.size>65536 and self.pos>=self.size-65536 else self.pos
        stop=min(self.size,max(end,start+65536))
        for attempt in range(6):
            try:
                PACER.wait()
                with self.session.get(self.url,headers={'Range':f'bytes={start}-{stop-1}','Accept-Encoding':'identity'},stream=True,timeout=(20,90)) as r:
                    if r.status_code==429:
                        delay=max(15,float(r.headers.get('Retry-After','15')))
                        PACER.backoff(delay);r.raise_for_status()
                    r.raise_for_status()
                    if r.status_code!=206:raise ValueError(f'Server ignored byte range ({r.status_code})')
                    if r.headers.get('Content-Range')!=f'bytes {start}-{stop-1}/{self.size}':raise ValueError('Wrong byte range returned')
                    data=r.content
                    if len(data)!=stop-start:raise ValueError('Truncated byte range')
                break
            except (requests.RequestException,ValueError):
                if attempt==5:raise
                time.sleep(min(30,2**attempt))
        self.downloaded+=len(data)
        if len(data)<32*1024**2:
            self.cache[start]=data
            while len(self.cache)>12 or sum(map(len,self.cache.values()))>64*1024**2:self.cache.popitem(last=False)
        result=data[position-start:end-start];self.pos=end;return result

    def prefetch(self,info):
        # A small safety margin covers local-header fields that differ from
        # central-directory metadata; the ZipFile reader still verifies CRCs.
        length=30+len(info.filename.encode('utf-8'))+len(info.extra)+info.compress_size+4096
        self.seek(info.header_offset);self.read(length)

def archive_url(record,filename):
    from urllib.parse import quote
    return f'https://zenodo.org/records/{record}/files/{quote(filename)}'
