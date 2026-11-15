"""Read packaged application source without launching or modifying it."""
import json
import struct
from pathlib import Path


class Asar:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open('rb') as stream:
            sizes = struct.unpack('<4I', stream.read(16))
            self.header_bytes = stream.read(sizes[3])
            self.header = json.loads(self.header_bytes)
            self.base = 8 + sizes[1]

    def entries(self, node=None, prefix=''):
        for name, value in (node or self.header).get('files', {}).items():
            path = prefix + '/' + name
            if 'files' in value:
                yield from self.entries(value, path)
            else:
                yield path, value

    def read(self, name):
        node = self.header
        for part in name.strip('/').split('/'):
            node = node['files'][part]
        if node.get('unpacked') or 'link' in node:
            raise ValueError('Only packed regular files are supported')
        with self.path.open('rb') as stream:
            stream.seek(self.base + int(node['offset']))
            data = stream.read(node['size'])
        if len(data) != node['size']:
            raise ValueError('Truncated ASAR entry')
        return data
