"""Portable policy and archive guards with owned fixtures; signing is a mocked boundary."""
from datetime import datetime,timezone,timedelta
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_marker as build
import marker as policy
import recovery as r
import stage_archive as a
import bundle_transaction as tx


class PortablePolicyTest(unittest.TestCase):
    def setUp(self):
        self.root=Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.directory=self.root/'candidate';self.directory.mkdir()
        self.source=self.directory/'Codex Marker.app';self.source.mkdir();(self.source/'payload').write_text('fixture')
        self.original=self.root/'Original.app';self.original.mkdir();(self.original/'keep').write_text('unchanged')
        self.original_entries=r.tree(self.original)
        self.target=self.root/'Applications/Codex Marker.app';self.target.parent.mkdir()
        record={'schema':1,'label':'candidate','status':'signed-verified','bundle':str(self.source),
                'original_app':str(self.original),'identifier':'local.example.marker','team':'TEST123456',
                'bundle_fingerprint':tx.contents(self.source)}
        r.write_json(self.directory/'before-sign.json',r.tree(self.source))
        record['before_sign_sha256']=r.file_digest(self.directory/'before-sign.json')
        r.write_json(self.directory/'manifest.json',record)
        self.enterContext(patch.object(build,'paths',return_value=(self.directory,self.source)))
        self.enterContext(patch.object(policy,'PLANS',self.root/'plans'))
        self.enterContext(patch.object(policy,'native_signature'))
        self.enterContext(patch.object(build,'source'))
        self.enterContext(patch.object(tx,'require_quiet'))
        self.record=record

    def tearDown(self):self.assertEqual(r.tree(self.original),self.original_entries)

    def prepare(self):
        policy.accept('candidate',True);return policy.plan('pilot','candidate',self.target)

    def test_acceptance_install_and_recoverable_disable(self):
        self.prepare();self.assertFalse(policy.install('pilot')['original_replaced'])
        shutil.rmtree(self.source)
        with patch.object(build,'source',side_effect=AssertionError('Updated original must not block removal')):
            self.assertEqual(policy.disable('pilot')['status'],'retired')
        self.assertFalse(self.target.exists())
        self.assertTrue((self.target.parent/'.codex-marker-pilot/removed.app').exists())

    def test_missing_or_changed_human_acceptance_cannot_install(self):
        with self.assertRaises(ValueError):policy.accept('candidate',False)
        self.assertFalse((self.directory/'acceptance.json').exists())
        self.prepare();(self.directory/'acceptance.json').write_text('{}')
        with self.assertRaisesRegex(ValueError,'Acceptance record changed'):policy.install('pilot')
        self.assertFalse((self.target.parent/'.codex-marker-pilot').exists())

    def test_changed_tools_or_original_version_cannot_mutate_target(self):
        self.prepare()
        with patch.object(policy,'tool_pins',return_value={'changed':'code'}):
            with self.assertRaises(ValueError):policy.install('pilot')
        with patch.object(build,'source',side_effect=ValueError('Unsupported version')):
            with self.assertRaisesRegex(ValueError,'Unsupported version'):policy.install('pilot')
        self.assertFalse((self.target.parent/'.codex-marker-pilot').exists())

    def test_original_source_and_nested_targets_are_refused(self):
        for target in (self.original,self.source,self.original/'Nested.app',self.source/'Nested.app'):
            with self.assertRaises(ValueError):policy.safe_target(target,self.original,self.source)

    def test_stale_future_and_mismatched_acceptance_are_rejected(self):
        self.prepare();evidence=r.read_json(self.directory/'acceptance.json')
        for changes in ({'operator':'simulated'},{'label':'other'},{'passed':[]},
                        {'signed_fingerprint':'other'},{'development_limits_acknowledged':False},
                        {'observed_at':(datetime.now(timezone.utc)-timedelta(days=8)).isoformat()},
                        {'observed_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()}):
            with self.assertRaises(ValueError):policy.require_acceptance({**evidence,**changes},self.record)

    def test_only_root_macl_can_differ_in_post_launch_audit(self):
        entries=r.tree(self.source);expected=self.record['bundle_fingerprint']
        entries['.']['xattrs']['com.apple.macl']='observed-after-launch'
        with patch.object(r,'tree',return_value=entries):
            self.assertEqual(policy.audit(self.source,self.record,None),r.fingerprint(entries))
            entries['payload']['sha256']='changed'
            with self.assertRaises(ValueError):policy.audit(self.source,self.record,None)


class ArchiveReadbackTest(unittest.TestCase):
    def test_alias_empty_added_file_and_corrupt_archive(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder).resolve();original=root/'source.asar';output=root/'result.asar'
            data=b'original'
            node={'offset':'0','size':len(data),'integrity':a.measure(io.BytesIO(data),len(data))}
            files={'one':node,'alias':dict(node),'empty':{'offset':str(len(data)),'size':0,
                                                        'integrity':a.measure(io.BytesIO(b''),0)}}
            original.write_bytes(a.pickle_header({'files':files})+data)
            tree,nodes,_,base,_,_=a.archive_index(original)
            changes={'one':b'new','added/deep':b'marker'}
            a.write_archive(original,tree,nodes,base,changes,output)
            build.verify_archive(original,output,changes)
            corrupted=bytearray(output.read_bytes());corrupted[-1]^=1;output.write_bytes(corrupted)
            with self.assertRaises(ValueError):build.verify_archive(original,output,changes)


if __name__=='__main__':unittest.main()
