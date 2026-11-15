"""Whole-bundle inventory/copy primitives. Never reads application profile data."""
import fcntl,hashlib,json,os,re,shutil,stat,subprocess,tempfile
from contextlib import contextmanager
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'build/locks'
ARCHIVE='Contents/Resources/app.asar'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical(path):
    require(path.is_absolute() and path.resolve() == path, f'Unsafe path: {path}')
    return path


def name(value):
    require(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', value), 'Invalid recovery name')
    return value


def output(*args):
    return subprocess.check_output(args, stderr=subprocess.PIPE)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def file_digest(path):
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), 'rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def tree(root):
    canonical(root)
    require(root.is_dir(), f'Missing bundle: {root}')
    entries = {}

    def visit(path):
        info = path.lstat()
        mode = info.st_mode
        attrs = output('/usr/bin/xattr', '-s', str(path)).decode().splitlines()
        acl = output('/bin/ls', '-ledq', str(path)).decode().splitlines()[1:]
        node = dict(mode=mode, uid=info.st_uid, gid=info.st_gid, flags=info.st_flags,
                    acl=acl, xattrs={key: digest(output('/usr/bin/xattr', '-spx', key, str(path)))
                                     for key in sorted(attrs)})
        entries[str(path.relative_to(root))] = node
        if stat.S_ISLNK(mode):
            target = os.readlink(path)
            require(not Path(target).is_absolute() and path.resolve().is_relative_to(root),
                    f'Link escapes bundle: {path}')
            node['link'] = target
        elif stat.S_ISREG(mode):
            require(info.st_nlink == 1, f'Unsupported hard-linked file: {path}')
            node.update(size=info.st_size, sha256=file_digest(path))
        elif stat.S_ISDIR(mode):
            for child in sorted(path.iterdir()):
                visit(child)
        else:
            raise ValueError(f'Unsupported file type: {path}')
        after = path.lstat()
        require((info.st_ino, info.st_ctime_ns) == (after.st_ino, after.st_ctime_ns),
                f'Changed during inventory: {path}')

    visit(root)
    return entries


def fingerprint(entries):
    return digest(json.dumps(entries, sort_keys=True).encode())


def write_json(path, value):
    canonical(path)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.journal-',
                                     delete=False) as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(stream.name, path)
    sync_directory(path.parent)


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def read_json(path):
    return json.loads(canonical(path).read_text())


def storage(entries, destination):
    needed = sum(entry.get('size', 0) for entry in entries.values())
    require(shutil.disk_usage(destination).free >= needed, 'Insufficient free space')


def copy_bundle(source, destination, entries):
    canonical(destination)
    require(not destination.exists(), f'Destination already exists: {destination}')
    storage(entries, destination.parent)
    output('/usr/bin/ditto', '--rsrc', '--extattr', '--acl', '--qtn',
           str(source), str(destination))
    require(tree(destination) == entries and tree(source) == entries,
            'Metadata/content mismatch or source changed during copy')


@contextmanager
def locked():
    canonical(WORK).mkdir(parents=True, exist_ok=True, mode=0o700)
    path = WORK / 'lock'
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        os.close(fd)
