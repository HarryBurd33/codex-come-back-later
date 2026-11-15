"""Read executable paths and transaction bundle metadata; never controls native apps."""
import ctypes,errno,os,subprocess
from pathlib import Path
import recovery as r


def process_paths():
    """Inspect executable paths only. Do not read arguments or signal any process."""
    lib = ctypes.CDLL('/usr/lib/libproc.dylib', use_errno=True)
    lib.proc_listallpids.argtypes = [ctypes.c_void_p, ctypes.c_int]
    lib.proc_listallpids.restype = ctypes.c_int
    lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
    lib.proc_pidpath.restype = ctypes.c_int
    count = lib.proc_listallpids(None, 0)
    r.require(count > 0, 'Cannot enumerate running processes')
    capacity = count + 1024
    pids = (ctypes.c_int * capacity)()
    count = lib.proc_listallpids(pids, ctypes.sizeof(pids))
    r.require(0 < count < capacity, 'Process inventory failed or overflowed')
    paths, unknown = [], []
    for pid in pids[:count]:
        if pid <= 0:
            continue
        buffer = ctypes.create_string_buffer(4096)
        ctypes.set_errno(0)
        length = lib.proc_pidpath(pid, buffer, len(buffer))
        if length > 0:
            paths.append((pid, Path(os.fsdecode(buffer.value))))
        elif ctypes.get_errno() not in (errno.ESRCH, errno.ENOENT):
            unknown.append(pid)
    return paths, unknown


def require_quiet(roots):
    paths, unknown = process_paths()
    r.require(not unknown, f'Cannot determine executable paths for {len(unknown)} processes')
    active = [pid for pid, path in paths if
              any(path == root or root in path.parents for root in roots)
              or 'sparkle' in str(path).lower()]
    r.require(not active, f'App or updater is running (process IDs: {active})')
    require_no_updater_jobs()


def require_no_updater_jobs():
    # These two launchd labels are present in pinned build 27194's updater.
    # A job can run an ordinary shell/ditto executable outside the app bundle.
    for label in ('com.openai.chat-sparkle-updater', 'com.openai.chat-sparkle-progress'):
        result = subprocess.run(['/bin/launchctl', 'print', f'gui/{os.getuid()}/{label}'],
                                capture_output=True, text=True, timeout=10)
        r.require(result.returncode != 0, f'Updater launchd job is loaded: {label}')
        r.require(result.returncode == 113 and f'Could not find service "{label}"' in result.stderr,
                  f'Cannot establish that updater launchd job is absent: {label}')


def contents(path):
    r.canonical(path)
    return r.fingerprint(r.tree(path)) if path.exists() else None
