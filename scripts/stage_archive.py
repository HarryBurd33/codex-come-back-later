"""Conservative ASAR reader/writer preserving unmodified packed content."""
import copy,hashlib,io,json,os,re,stat,struct
from pathlib import Path
from recovery import canonical,require,digest
BLOCK=4*1024*1024
INTEGRITY_KEY='Resources/app.asar'


def component(value):
    require(value not in ('', '.', '..') and not any(c in value for c in '/\\\0'),
            f'Invalid archive path component: {value!r}')


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, f'Duplicate JSON key: {key}')
        result[key] = value
    return result


def regular(path):
    require(stat.S_ISREG(canonical(path).lstat().st_mode), f'Expected regular file: {path}')
    return path


def pickle_header(tree):
    raw = json.dumps(tree, ensure_ascii=False, separators=(',', ':')).encode()
    padding = (-len(raw)) % 4
    payload = 4 + len(raw) + padding
    return struct.pack('<4I', 4, 4 + payload, payload, len(raw)) + raw + bytes(padding)


def archive_index(path):
    """Parse the on-disk Pickle header and validate the entire file index."""
    with regular(path).open('rb') as stream:
        file_size = os.fstat(stream.fileno()).st_size
        prefix = stream.read(16)
        require(len(prefix) == 16, 'Truncated ASAR prefix')
        marker, outer, inner, length = struct.unpack('<4I', prefix)
        padding = (-length) % 4
        require(marker == 4 and outer == inner + 4 and inner == 4 + length + padding
                and 0 < length <= 32 * 1024 * 1024 and 8 + outer <= file_size,
                'Invalid ASAR prefix')
        raw = stream.read(length)
        require(len(raw) == length and stream.read(padding) == bytes(padding), 'Invalid ASAR header padding')
    tree = json.loads(raw, object_pairs_hook=unique_object)
    files, directories = {}, set()

    def walk(node, parent):
        require(isinstance(node, dict) and set(node) == {'files'} and isinstance(node['files'], dict),
                f'Unsupported directory metadata at {parent}')
        directories.add(parent)
        for key, child in node['files'].items():
            component(key)
            relative = f'{parent}/{key}' if parent else key
            require(isinstance(child, dict), f'Invalid archive node: {relative}')
            if 'files' in child:
                walk(child, relative)
                continue
            unpacked = child.get('unpacked') is True
            required = {'size', 'integrity', 'unpacked' if unpacked else 'offset'}
            require(required <= set(child) <= required | {'executable'} and
                    type(child.get('executable', False)) is bool and
                    type(child['size']) is int and child['size'] >= 0,
                    f'Unsupported ASAR file node: {relative}')
            integrity = child['integrity']
            require(isinstance(integrity, dict) and set(integrity) == {'algorithm', 'hash', 'blockSize', 'blocks'}
                    and integrity['algorithm'] == 'SHA256' and integrity['blockSize'] == BLOCK
                    and isinstance(integrity['blocks'], list)
                    and len(integrity['blocks']) == max(1, (child['size'] + BLOCK - 1) // BLOCK)
                    and all(isinstance(h, str) and re.fullmatch('[a-f0-9]{64}', h)
                            for h in [integrity['hash'], *integrity['blocks']]),
                    f'Invalid integrity metadata: {relative}')
            if not unpacked:
                offset = child['offset']
                require(isinstance(offset, str) and re.fullmatch(r'0|[1-9][0-9]{0,15}', offset)
                        and int(offset) + child['size'] <= file_size - (8 + outer),
                        f'Invalid packed extent: {relative}')
            files[relative] = child

    walk(tree, '')
    # Exact extents can be shared by multiple paths in the original archive.
    extents = sorted({(int(n['offset']), n['size']) for n in files.values() if 'offset' in n and n['size']})
    end = 0
    dense = True
    for offset, size in extents:
        require(offset >= end, 'Partially overlapping ASAR extents')
        dense &= offset == end
        end = offset + size
    return tree, files, directories, 8 + outer, digest(raw), dense and end == file_size - (8 + outer)


def measure(stream, size, output=None):
    whole = hashlib.sha256()
    blocks = []
    remaining = size
    while remaining:
        block = stream.read(min(remaining, BLOCK))
        require(len(block) == min(remaining, BLOCK), 'Truncated archive data')
        whole.update(block)
        blocks.append(digest(block))
        if output is not None:
            output.write(block)
        remaining -= len(block)
    return {'algorithm': 'SHA256', 'hash': whole.hexdigest(), 'blockSize': BLOCK,
            'blocks': blocks or [digest(b'')]}


def integrity_record(header):
    return {'algorithm': 'SHA256', 'hash': header}


def write_archive(original, tree, nodes, base, overlay, output):
    tree = copy.deepcopy(tree)
    for relative in sorted(overlay.keys() - nodes.keys()):
        *parents, leaf = relative.split('/')
        directory = tree
        for parent in parents:
            directory = directory['files'].setdefault(parent, {'files': {}})
            require('files' in directory, f'Overlay parent conflicts with a file: {relative}')
        directory['files'][leaf] = {}
    operations = []
    aliases = {}
    cursor = 0

    def assign(directory, prefix=''):
        nonlocal cursor
        for key, node in directory['files'].items():
            relative = f'{prefix}{key}'
            if 'files' in node:
                assign(node, relative + '/')
                continue
            if node.get('unpacked'):
                continue
            if relative in overlay:
                data = overlay[relative]
                node.update(offset=str(cursor), size=len(data), integrity=measure(io.BytesIO(data), len(data)))
                operations.append((None, data))
                cursor += len(data)
            else:
                extent = (int(node['offset']), node['size'])
                if extent not in aliases:
                    aliases[extent] = cursor
                    operations.append(extent)
                    cursor += node['size']
                node['offset'] = str(aliases[extent])

    assign(tree)
    header_bytes = pickle_header(tree)
    with original.open('rb') as source, output.open('xb') as target:
        target.write(header_bytes)
        for offset, payload in operations:
            if offset is None:
                target.write(payload)
                continue
            source.seek(base + offset)
            remaining = payload
            while remaining:
                part = source.read(min(remaining, BLOCK))
                require(part, 'Source archive changed while copying')
                target.write(part)
                remaining -= len(part)
        target.flush()
        os.fsync(target.fileno())
    length = struct.unpack_from('<I', header_bytes, 12)[0]
    return digest(header_bytes[16:16 + length])
