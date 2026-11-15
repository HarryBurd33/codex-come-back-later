"""Create-only app installation and recoverable removal. Never touches profile data."""
from contextlib import contextmanager
import ctypes
import fcntl
import os

import bundle_transaction as tx
import recovery as r


def move_absent(source, destination):
    # macOS SDK sys/stdio.h: RENAME_EXCL=0x00000004. The destination cannot
    # be overwritten, even if another process creates it after the last check.
    library = ctypes.CDLL('/usr/lib/libSystem.B.dylib', use_errno=True)
    rename = library.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    if rename(os.fsencode(source), os.fsencode(destination), 4):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))
    r.sync_directory(source.parent)
    r.sync_directory(destination.parent)


@contextmanager
def locked(target, directory, source, *, create=False):
    for path in (target, directory, source): r.canonical(path)
    r.require(directory.parent == target.parent and len({target,directory,source}) == 3,
              'Transaction must be a distinct sibling of target')
    r.require(not any(a in b.parents for a in (target,directory,source)
                      for b in (target,directory,source) if a != b), 'Transaction paths overlap')
    if not directory.exists():
        r.require(create and tx.contents(target) is None, 'Missing transaction or existing target')
        directory.mkdir(mode=0o700); r.sync_directory(directory.parent)
    info = directory.stat()
    r.require(directory.is_dir() and info.st_uid == os.getuid() and info.st_mode & 0o077 == 0
              and info.st_dev == target.parent.stat().st_dev, 'Unsafe transaction directory')
    r.require({p.name for p in directory.iterdir()} <=
              {'lock','journal.json','stage.app','retire.json','removed.app'}, 'Unknown transaction artifacts')
    descriptor = os.open(r.canonical(directory/'lock'), os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW, 0o600)
    try:
        value = os.fstat(descriptor)
        r.require(value.st_uid == os.getuid() and value.st_nlink == 1 and value.st_mode & 0o077 == 0,
                  'Unsafe transaction lock')
        fcntl.flock(descriptor, fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally: os.close(descriptor)


def intent(target, source, expected, binding):
    return dict(schema=1,target=str(target),source=str(source),fingerprint=expected,binding=binding)


def journal(directory, item):
    saved = r.read_json(directory/'journal.json')
    r.require(set(saved) == set(item)|{'phase'} and all(saved[k] == v for k,v in item.items())
              and saved['phase'] in {'staging','prepared','installed','retired'}, 'Transaction intent changed')
    return saved


def install(target, directory, source, expected, binding, validate, quiet):
    validate(source, expected); quiet()
    with locked(target,directory,source,create=True):
        stage, record = directory/'stage.app', directory/'journal.json'
        r.require(not (directory/'retire.json').exists() and not (directory/'removed.app').exists(),
                  'Retired installation cannot be replayed')
        item = intent(target,source,expected,binding)
        observed = (tx.contents(target),tx.contents(stage))
        if not record.exists():
            r.require(observed == (None,None), 'Unknown installation without journal')
            r.write_json(record,{**item,'phase':'staging'})
        phase = journal(directory,item)['phase']
        # Reconcile an interrupted rename only after the prepared journal was saved.
        if observed == (expected,None) and phase in {'prepared','installed'}:
            validate(target,expected); quiet()
            r.write_json(record,{**item,'phase':'installed'})
            return {'status':'installed','target':str(target),'fingerprint':expected}
        r.require(phase in {'staging','prepared'} and observed[0] is None,
                  'Existing target or inconsistent phase; preserve for reconciliation')
        if phase == 'staging':
            r.require(observed[1] in {None,expected}, 'Partial stage; preserve for reconciliation')
            if observed[1] is None:
                entries = r.tree(source)
                r.require(r.fingerprint(entries) == expected, 'Source changed before copy')
                r.copy_bundle(source,stage,entries)
            validate(stage,expected); quiet()
            r.require(tx.contents(target) is None,'Target appeared during copy')
            r.write_json(record,{**item,'phase':'prepared'})
        validate(stage,expected); quiet()
        r.require(tx.contents(target) is None,'Target appeared before install')
        quiet(); move_absent(stage,target)
        validate(target,expected); quiet()
        r.write_json(record,{**item,'phase':'installed'})
        return {'status':'installed','target':str(target),'fingerprint':expected}


def retire(target, directory, source, expected, binding, audit, validate, quiet):
    """Archive the exact observed installed bundle. Actual fingerprint may include OS MACL drift.

    audit returns a complete fingerprint only after the caller's signed-build comparison.
    validate checks that frozen full fingerprint plus signatures; it never normalizes data.
    """
    quiet()
    with locked(target,directory,source):
        item = intent(target,source,expected,binding)
        saved = journal(directory,item)
        record, removed = directory/'retire.json',directory/'removed.app'
        r.require(tx.contents(directory/'stage.app') is None,'Staged installation needs reconciliation')
        if not record.exists():
            r.require(saved['phase'] in {'prepared','installed'} and not removed.exists(),
                      'Unknown retirement state')
            actual = audit(target)
            r.write_json(record,{'binding':binding,'fingerprint':actual})
        retirement = r.read_json(record)
        r.require(set(retirement) == {'binding','fingerprint'} and retirement['binding'] == binding,
                  'Retirement intent changed')
        actual = retirement['fingerprint']
        observed = (tx.contents(target),tx.contents(removed))
        if observed == (actual,None):
            r.require(saved['phase'] in {'prepared','installed'},'Retirement phase inconsistent')
            validate(target,actual); quiet(); move_absent(target,removed)
        else:
            r.require(observed == (None,actual),'Installed or archived bundle changed; preserve both')
        validate(removed,actual); quiet()
        r.require(tx.contents(target) is None,'Target reappeared during retirement')
        r.write_json(directory/'journal.json',{**item,'phase':'retired'})
        return {'status':'retired','target':str(target),'preserved_bundle':str(removed),
                'fingerprint':actual,'profiles_removed':False}
