"""Local build/sign/accept/install/disable workflow. Never launches or quits Codex."""
import argparse
import copy
from datetime import datetime,timezone
import json
from pathlib import Path
import subprocess
import sys

import build_marker as build
import native_signing as signing
import recovery as r
import bundle_transaction as tx
import alongside_transaction as transaction

PLANS = r.ROOT/'build/installations'
CHECKS = ['normal icon launch','existing chats visible','native marker and manual removal',
          'accepted direct and queued prompts clear','drafts and assistant response retain',
          'normal restart retains marker','light/dark and keyboard toggle']


def now():return datetime.now(timezone.utc).isoformat()
def hash_json(value):return r.digest(json.dumps(value,sort_keys=True).encode())


def tool_pins():
    return {str(p.relative_to(r.ROOT)):r.file_digest(p) for folder in ('scripts','signing','src','compatibility')
            for p in sorted((r.ROOT/folder).glob('*')) if p.is_file()}


def native_signature(bundle, record):
    requirement = ('identifier '+json.dumps(record['identifier'])+' and anchor apple generic and '
                   'certificate leaf[subject.OU] = '+json.dumps(record['team']))
    signing.run('/usr/bin/codesign','--verify','--deep','--strict','-R='+requirement,str(bundle))


def record_for(label):
    directory,bundle = build.paths(label);record = r.read_json(directory/'manifest.json')
    r.require(record.get('schema') == 1 and record.get('label') == label and record.get('bundle') == str(bundle)
              and record.get('status') == 'signed-verified','Build is not signed and verified')
    return directory,bundle,record


def comparison_fingerprint(entries, original_macl):
    # Compare in memory only. Never clear/reset system metadata to pass a check.
    compared = copy.deepcopy(entries)
    if original_macl is None:compared['.']['xattrs'].pop('com.apple.macl',None)
    else:compared['.']['xattrs']['com.apple.macl'] = original_macl
    return r.fingerprint(compared)


def audit(bundle, record, original_macl):
    entries = r.tree(bundle)
    r.require(comparison_fingerprint(entries,original_macl) == record['bundle_fingerprint'],
              'Signed app changed beyond the observed OS root MACL field; preserve for review')
    native_signature(bundle,record)
    return r.fingerprint(entries)


def before_macl(directory, record):
    r.require(r.file_digest(directory/'before-sign.json') == record['before_sign_sha256'],'Inventory changed')
    return r.read_json(directory/'before-sign.json')['.']['xattrs'].get('com.apple.macl')


def accept(label, confirmed):
    r.require(confirmed,'Perform the documented native checks first; then pass --native-checks-passed')
    directory,bundle,record = record_for(label)
    r.require(not (directory/'acceptance.json').exists(),'Acceptance already recorded; preserve existing record')
    actual = audit(bundle,record,before_macl(directory,record))
    receipt = {'operator':'human','observed_at':now(),'label':label,'passed':CHECKS,
               'signed_fingerprint':record['bundle_fingerprint'],'observed_fingerprint':actual,
               'development_limits_acknowledged':True}
    r.write_json(directory/'acceptance.json',receipt)
    return {'status':'human-acceptance-recorded','note':'This records your attestation; it is not an automated native UI test.'}


def require_acceptance(value, record):
    r.require(value.get('operator') == 'human' and value.get('label') == record['label']
              and value.get('signed_fingerprint') == record['bundle_fingerprint']
              and value.get('development_limits_acknowledged') is True
              and set(CHECKS) <= set(value.get('passed',[])),'Incomplete/mismatched native acceptance')
    stamp = datetime.fromisoformat(value['observed_at'])
    r.require(stamp.tzinfo and 0 <= (datetime.now(timezone.utc)-stamp).total_seconds() <= 7*86400,
              'Native acceptance is stale or future-dated')


def plan_directory(name):return r.canonical(PLANS/r.name(name))


def safe_target(target, original, source):
    r.canonical(target)
    r.require(target.suffix == '.app' and target.parent.is_dir(),'Target must be an .app in an existing directory')
    r.require(target != original and target != source and not any(
        a in b.parents for a,b in ((target,original),(original,target),(target,source),(source,target))),
        'Alongside target must be separate from the original and source apps')


def plan(name, label, target):
    directory = plan_directory(name)
    source_dir,source,record = record_for(label)
    safe_target(target,Path(record['original_app']),source)
    transaction_dir = target.parent/('.codex-marker-'+r.name(name))
    r.canonical(transaction_dir)
    r.require(not directory.exists() and not transaction_dir.exists() and not target.exists(),
              'Existing target/plan/transaction requires reconciliation')
    require_acceptance(r.read_json(source_dir/'acceptance.json'),record)
    build.source(Path(record['original_app']))
    macl = before_macl(source_dir,record);actual = audit(source,record,macl)
    value = {'schema':1,'name':name,'label':label,'target':str(target),'source':str(source),
             'transaction':str(transaction_dir),'fingerprint':actual,'original_macl':macl,
             'manifest_sha256':r.file_digest(source_dir/'manifest.json'),
             'acceptance_sha256':r.file_digest(source_dir/'acceptance.json'),'tools':tool_pins(),'created_at':now()}
    PLANS.mkdir(parents=True,mode=0o700,exist_ok=True);directory.mkdir(mode=0o700)
    r.write_json(directory/'plan.json',value)
    return {'status':'ready-for-install','target':str(target),'plan':str(directory/'plan.json'),'installed':False}


def load_plan(name):
    directory = plan_directory(name);value = r.read_json(directory/'plan.json')
    expected = {'schema','name','label','target','source','transaction','fingerprint','original_macl',
                'manifest_sha256','acceptance_sha256','tools','created_at'}
    r.require(set(value) == expected and value['schema'] == 1 and value['name'] == name,'Plan changed')
    source_dir,source,record = record_for(value['label'])
    target = Path(value['target']);safe_target(target,Path(record['original_app']),source)
    transaction_dir = target.parent/('.codex-marker-'+r.name(name))
    r.require(value['source'] == str(source) and value['transaction'] == str(transaction_dir) and
              value['tools'] == tool_pins() and r.file_digest(source_dir/'manifest.json') == value['manifest_sha256'],
              'Bound source, tools or manifest changed')
    return directory,value,source_dir,source,record,target,transaction_dir


def install(name):
    directory,value,source_dir,source,record,target,transaction_dir = load_plan(name)
    r.require(r.file_digest(source_dir/'acceptance.json') == value['acceptance_sha256'],'Acceptance record changed')
    require_acceptance(r.read_json(source_dir/'acceptance.json'),record)
    build.source(Path(record['original_app']))
    def validate(path,expected):
        r.require(tx.contents(path) == expected,'Actual full bundle fingerprint changed')
        native_signature(path,record)
    quiet = lambda:tx.require_quiet([source,target,transaction_dir])
    result = transaction.install(target,transaction_dir,source,value['fingerprint'],hash_json(value),validate,quiet)
    r.write_json(directory/'install-result.json',result)
    return {**result,'original_replaced':False,'installed_icon':'human-launch-check-required'}


def disable(name):
    directory,value,source_dir,source,record,target,transaction_dir = load_plan(name)
    # Removal remains possible after an original app update or candidate removal.
    def validate(path,expected):
        r.require(tx.contents(path) == expected,'Actual full bundle fingerprint changed')
        native_signature(path,record)
    quiet = lambda:tx.require_quiet([source,target,transaction_dir])
    result = transaction.retire(target,transaction_dir,source,value['fingerprint'],hash_json(value),
                                lambda p:audit(p,record,value['original_macl']),validate,quiet)
    r.write_json(directory/'disable-result.json',result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    sub.add_parser('identities')
    p = sub.add_parser('inspect');p.add_argument('--app',type=Path,required=True)
    p = sub.add_parser('prepare');p.add_argument('label');p.add_argument('--app',type=Path,required=True)
    p.add_argument('--codex-home',type=Path,default=Path.home()/'.codex');p.add_argument('--bundle-id',default=build.DEFAULT_ID)
    p = sub.add_parser('sign');p.add_argument('label');p.add_argument('--identity',required=True)
    p = sub.add_parser('accept');p.add_argument('label');p.add_argument('--native-checks-passed',action='store_true')
    p = sub.add_parser('plan');p.add_argument('name');p.add_argument('label')
    p.add_argument('--target',type=Path,default=Path('/Applications/Codex Marker.app'))
    for command in ('install','disable'):sub.add_parser(command).add_argument('name')
    args = parser.parse_args()
    with r.locked():
        if args.command == 'identities':result = {'eligible':signing.identities()}
        elif args.command == 'inspect':
            info = build.source(args.app);result = {'supported':True,'version':info['CFBundleShortVersionString'],'build':info['CFBundleVersion']}
        elif args.command == 'prepare':result = build.prepare(args.label,args.app,args.codex_home,args.bundle_id)
        elif args.command == 'sign':result = build.sign(args.label,args.identity)
        elif args.command == 'accept':result = accept(args.label,args.native_checks_passed)
        elif args.command == 'plan':result = plan(args.name,args.label,args.target)
        else:result = globals()[args.command](args.name)
    print(json.dumps(result,indent=2))


if __name__ == '__main__':
    try:main()
    except (OSError,ValueError,KeyError,subprocess.SubprocessError) as error:
        print(f'Marker workflow stopped: {error}',file=sys.stderr);sys.exit(1)
