"""Disposable filesystem tests; never executes or installs Codex."""
import fcntl,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import alongside_transaction as t
import bundle_transaction as tx
import recovery as r

class AlongsideTransactionTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.source,self.target,self.directory = [self.root/p for p in ('source.app','Installed.app','transaction')]
        self.source.mkdir();(self.source/'payload').write_text('signed fixture')
        self.expected = tx.contents(self.source)
        self.original = self.root/'Original.app';self.original.mkdir();(self.original/'keep').write_text('unchanged')
        self.original_entries = r.tree(self.original)

    def validate(self,path,expected):
        r.require(tx.contents(path) == expected,'Fixture changed')

    def install(self,binding='test',quiet=lambda:None):
        return t.install(self.target,self.directory,self.source,self.expected,binding,self.validate,quiet)

    def retire(self,audit=None):
        def default(path):
            self.validate(path,self.expected);return self.expected
        return t.retire(self.target,self.directory,self.source,self.expected,'test',audit or default,
                        self.validate,lambda:None)

    def tearDown(self):
        self.assertEqual(r.tree(self.original),self.original_entries)

    def test_install_and_retire_idempotently_preserve_original_and_new_app(self):
        self.assertEqual(self.install()['status'],'installed')
        with patch.object(t,'move_absent',side_effect=AssertionError('duplicate install')):self.install()
        self.assertEqual(self.retire()['status'],'retired')
        self.assertEqual(tx.contents(self.directory/'removed.app'),self.expected)
        with patch.object(t,'move_absent',side_effect=AssertionError('duplicate retire')):self.retire()
        with self.assertRaisesRegex(ValueError,'cannot be replayed'):self.install()

    def test_installer_and_retirement_resume_after_actual_rename(self):
        move=t.move_absent
        def interrupted(a,b):move(a,b);raise InterruptedError('after rename')
        with patch.object(t,'move_absent',interrupted),self.assertRaises(InterruptedError):self.install()
        self.install()
        with patch.object(t,'move_absent',interrupted),self.assertRaises(InterruptedError):self.retire()
        self.retire();self.assertFalse(self.target.exists())

    def test_foreign_target_is_never_overwritten_even_if_created_at_rename(self):
        move=t.move_absent
        def interloper(a,b):b.mkdir();(b/'keep').write_text('foreign');move(a,b)
        with patch.object(t,'move_absent',interloper),self.assertRaises(FileExistsError):self.install()
        self.assertEqual((self.target/'keep').read_text(),'foreign')
        before=r.tree(self.root)
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(r.tree(self.root),before)

    def test_empty_existing_target_also_refuses_without_transaction(self):
        self.target.mkdir()
        with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.directory.exists())

    def test_partial_copy_and_unrecognized_artifacts_are_preserved(self):
        def partial(source,target,entries):target.mkdir();raise OSError('partial copy')
        with patch.object(r,'copy_bundle',partial),self.assertRaises(OSError):self.install()
        before=r.tree(self.root)
        with self.assertRaisesRegex(ValueError,'Partial stage'):self.install()
        self.assertEqual(r.tree(self.root),before)
        (self.directory/'foreign').write_text('keep')
        with self.assertRaisesRegex(ValueError,'Unknown transaction artifacts'):self.install()

    def test_running_app_and_changed_source_prevent_any_mutation(self):
        def active():raise ValueError('Running')
        with self.assertRaisesRegex(ValueError,'Running'):self.install(quiet=active)
        self.assertFalse(self.directory.exists())
        (self.source/'payload').write_text('changed')
        with self.assertRaises(ValueError):self.install()
        self.assertFalse(self.directory.exists())

    def test_changed_binding_and_invalid_phase_preserve_installed_app(self):
        self.install()
        with self.assertRaisesRegex(ValueError,'intent changed'):self.install(binding='different')
        p=self.directory/'journal.json';value=r.read_json(p);value['phase']='staging';r.write_json(p,value)
        with self.assertRaises(ValueError):self.install()
        self.assertEqual(tx.contents(self.target),self.expected)

    def test_changed_app_cannot_be_removed_and_retirement_can_bind_audited_metadata(self):
        self.install();(self.target/'payload').write_text('unexpected')
        with self.assertRaises(ValueError):self.retire()
        self.assertFalse((self.directory/'retire.json').exists())
        (self.target/'payload').write_text('signed fixture')
        # The audit policy is separate: only an explicitly accepted full fingerprint
        # is frozen, then any later drift is refused during interrupted retirement.
        self.target.chmod(0o700);actual=tx.contents(self.target)
        def interrupted(a,b):raise InterruptedError('before rename')
        with patch.object(t,'move_absent',interrupted),self.assertRaises(InterruptedError):
            self.retire(audit=lambda p:actual)
        (self.target/'payload').write_text('later drift')
        with self.assertRaises(ValueError):self.retire(audit=lambda p:tx.contents(p))
        self.assertEqual(r.read_json(self.directory/'retire.json')['fingerprint'],actual)

    def test_lock_and_symlink_are_not_followed(self):
        self.directory.mkdir(mode=0o700)
        with (self.directory/'lock').open('w') as lock:
            (self.directory/'lock').chmod(0o600)
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.install()
        (self.directory/'lock').unlink();(self.directory/'lock').symlink_to(self.original/'keep')
        with self.assertRaises(ValueError):self.install()
