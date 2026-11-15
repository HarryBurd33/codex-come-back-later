"""Apple-issued personal signing; preserve native payloads and active integrity checks."""
import json,plistlib,re,subprocess
from pathlib import Path
import recovery as r
import macho_signature_payload as m
import native_asar_integrity as native_integrity
EXECUTABLE='Contents/MacOS/ChatGPT'
FRAMEWORKS=('Contents/Frameworks/Codex Framework.framework','Contents/Frameworks/Sparkle.framework')
OMIT={'com.apple.application-identifier','com.apple.developer.team-identifier',
      'com.apple.developer.aps-environment','com.apple.developer.associated-domains',
      'com.apple.developer.usernotifications.communication','keychain-access-groups',
      'com.apple.security.application-groups'}

def run(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=60)
    r.require(result.returncode == 0, f'{Path(args[0]).name} failed: {result.stderr.strip()}')
    return result.stdout, result.stderr


def identities():
    out, _ = run('/usr/bin/security', 'find-identity', '-v', '-p', 'codesigning')
    return [{'fingerprint': value.upper(), 'name': name} for value, name in
            re.findall(r'\d+\)\s+([A-Fa-f0-9]{40})\s+"([^"]+)"', out)
            if name.startswith(('Apple Development:', 'Mac Developer:', 'Developer ID Application:'))]

def selected(relative):
    return (relative == EXECUTABLE or any(relative.startswith(f + '/') for f in FRAMEWORKS)
            or (relative.endswith('.node') and '.dSYM/' not in relative and
                relative.startswith(('Contents/Resources/native/', 'Contents/Resources/app.asar.unpacked/'))))


def object_path(relative):
    if relative == EXECUTABLE:
        return '.'
    for parent in Path(relative).parents:
        if parent.suffix in ('.app', '.xpc'):
            return str(parent)
    for framework in FRAMEWORKS:
        if relative.startswith(framework + '/') and Path(relative).name == Path(framework).stem:
            return framework
    return relative


def details(path):
    _, text = run('/usr/bin/codesign', '--display', '--verbose=4', str(path))
    identifier = re.search(r'^Identifier=(.+)$', text, re.M)
    team = re.search(r'^TeamIdentifier=(.+)$', text, re.M)
    flags = re.search(r'flags=(0x[0-9a-fA-F]+)', text)
    r.require(identifier and team and flags and int(flags[1], 16) == 0x10000,
              'Unsupported code identity/runtime flags')
    out, _ = run('/usr/bin/codesign', '--display', '--entitlements', '-', '--xml', str(path))
    return identifier[1], team[1], plistlib.loads(out.encode()) if out.strip() else {}


def plan(source, root_identifier):
    r.require(re.fullmatch(r'[a-z][a-z0-9]*(?:\.[a-z0-9-]+){2,}',root_identifier)
              and not root_identifier.startswith('com.openai.'),'Use a separate local bundle identifier')
    records = []
    for path in sorted(source.rglob('*')):
        relative = str(path.relative_to(source))
        if path.is_symlink() or not path.is_file() or not selected(relative):
            continue
        with path.open('rb') as stream:
            magic = stream.read(4)
        if magic not in (b'\xcf\xfa\xed\xfe', b'\xca\xfe\xba\xbe'):
            continue
        identifier, team, entitlements = details(path)
        r.require(team == '2DC432GLL2', 'Source signing team changed')
        records.append(dict(binary=relative, object=object_path(relative),
                            identifier=root_identifier if relative == EXECUTABLE else identifier,
                            entitlements={k:v for k,v in entitlements.items() if k not in OMIT},
                            omitted={k:v for k,v in entitlements.items() if k in OMIT},
                            payloads=m.fingerprints(path)))
    r.require(len(records) == 37 and len({v['object'] for v in records}) == 37,
              'Unexpected native signing closure')
    return sorted(records, key=lambda v: (-len(Path(v['object']).parts), v['object'] == '.', v['object']))


def validate_signed_contents(directory, bundle, record):
    r.require(r.file_digest(directory/'before-sign.json') == record['before_sign_sha256'], 'Inventory changed')
    before = r.read_json(directory/'before-sign.json'); after = r.tree(bundle)
    r.require(before.keys() == after.keys(), 'Signing changed the bundle path set')
    info = plistlib.loads((bundle/'Contents/Info.plist').read_bytes())
    native_integrity.verify((bundle/record['native_integrity_update']['binary']).read_bytes(),
                            info['ElectronAsarIntegrity'])
    for item in record['signing_plan']:
        target = bundle / item['object']
        requirement = ('identifier '+json.dumps(item['identifier'])+' and anchor apple generic and '
                       'certificate leaf[subject.OU] = '+json.dumps(record['team']))
        run('/usr/bin/codesign','--verify','--strict','-R='+requirement,str(target))
        identifier, team, entitlements = details(target)
        r.require((identifier,team,entitlements) == (item['identifier'],record['team'],item['entitlements']),
                  'Development signature/entitlements differ')
        r.require(m.fingerprints(bundle/item['binary']) == item['payloads'], 'Native executable payload changed')
    # Only CodeResources belonging to actually signed bundle objects may change.
    resource_owners = {str(Path(item['object'])/'Contents/_CodeSignature/CodeResources') for item in record['signing_plan']}
    resource_owners |= {'Contents/_CodeSignature/CodeResources'}
    # Framework resource seals are in their version directory, not Contents.
    for framework in FRAMEWORKS:
        resource_owners |= {key for key in before if key.startswith(framework+'/Versions/') and
                           key.endswith('/_CodeSignature/CodeResources') and '/Helpers/' not in key and '/XPCServices/' not in key and '/Updater.app/' not in key}
    mutable = {item['binary'] for item in record['signing_plan']} | resource_owners
    for key, node in after.items():
        strip = lambda v:{k:x for k,x in v.items() if k not in {'size','sha256'}}
        r.require((strip(node) == strip(before[key]) if key in mutable else node == before[key]),
                  'Unexpected signing change: '+key)
    run('/usr/bin/codesign','--verify','--deep','--strict','-R=anchor apple generic',str(bundle))
    r.require(r.file_digest(bundle/r.ARCHIVE) == record['archive_sha256'] and
              r.file_digest(bundle/'Contents/Info.plist') == record['plist_sha256'], 'Archive/plist changed')
    return r.fingerprint(after)
