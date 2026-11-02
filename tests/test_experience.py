"""Behavior checks for storage continuity, scoped settings and dated context.

All data is synthetic; subprocess checks exercise the installed CLI and real SQLite.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from sr.integrity import Store
from sr.memory import Memory
from sr.knowledge import Knowledge
from sr.runtime import Runtime


class Experience(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = self.root / 'private'
        self.binding = self.root / 'state' / 'binding.json'
        self.store = Store(self.data, create=True)
        Knowledge(self.store).initialize()
        self.memory = Memory(self.store)
        self.memory.person('PERSON_A', ['甲'])
        self.memory.person('PERSON_B', ['乙'])

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def cli(self, command, request=None, data=False, binding=None):
        args = [sys.executable, '-B', str(ROOT / 'scripts' / 'social_reply.py'), '--binding', str(binding or self.binding)]
        if data:
            args += ['--data', str(self.data)]
        process = subprocess.run(args + [command], input=json.dumps(request or {}), text=True, capture_output=True)
        self.assertTrue(process.stdout.strip(), process.stderr)
        return process.returncode, json.loads(process.stdout)

    def bind(self):
        code, value = self.cli('storage-bind', {'directory': str(self.data), 'confirmed': True, 'expected': 0})
        self.assertEqual(code, 0, value)
        return value['result']

    def claim(self, content, reason='preference', status='active'):
        source = self.memory.source('PERSON_A', 'chat', content)['source_id']
        result = self.memory.claim('PERSON_A', content, [source], 'statement', 'high', reason,
                                   self.store.revision('person:PERSON_A'), status=status)
        # Synthetic event time is deliberately fixed for reproducible calendar tests.
        self.store.db.execute('UPDATE claims SET updated_at=? WHERE id=?', ('2026-11-02T08:00:00+00:00', result['claim_id']))
        return result['claim_id']

    def test_bound_context_works_in_new_process_without_data_argument(self):
        self.claim('喜欢散步')
        self.bind()
        code, value = self.cli('context', {'identifier': 'PERSON_A'})
        self.assertEqual(code, 0, value)
        self.assertEqual(value['result']['profile']['claims'][0]['content'], '喜欢散步')

    def test_new_person_without_known_alias_can_be_created(self):
        code, value = self.cli('person-add', {'identifier': 'PERSON_C'}, data=True)
        self.assertEqual(code, 0, value)
        self.assertEqual(self.memory.profile('PERSON_C')['aliases'], [])

    def test_binding_requires_explicit_confirmation(self):
        code, value = self.cli('storage-bind', {'directory': str(self.data), 'expected': 0})
        self.assertNotEqual(code, 0)
        self.assertFalse(self.binding.exists())

    def test_binding_rejects_stale_revision(self):
        self.bind()
        code, value = self.cli('storage-bind', {'directory': str(self.data), 'confirmed': True, 'expected': 0})
        self.assertEqual(code, 2, value)
        self.assertEqual(json.loads(self.binding.read_text())['revision'], 1)

    def test_missing_bound_storage_is_not_silently_recreated(self):
        self.bind()
        self.store.close()
        self.data.rename(self.root / 'retained')
        code, value = self.cli('context', {'identifier': 'PERSON_A'})
        self.assertEqual(value['status'], 'degraded', value)
        self.assertFalse(self.data.exists())
        self.store = Store(self.root / 'retained')

    def test_unbound_context_is_degraded_without_creating_files(self):
        code, value = self.cli('context', {'identifier': 'PERSON_A'})
        self.assertEqual(value['status'], 'degraded', value)
        self.assertFalse(self.binding.exists())

    def test_corrupt_binding_does_not_load_other_storage(self):
        self.binding.parent.mkdir()
        self.binding.write_text('{bad', encoding='utf-8')
        code, value = self.cli('context', {'identifier': 'PERSON_A'})
        self.assertEqual(value['status'], 'degraded', value)
        self.assertNotIn('profile', value['result'])

    def test_binding_lock_refuses_parallel_overwrite(self):
        self.binding.parent.mkdir()
        self.binding.with_name(self.binding.name + '.lock').write_text('busy')
        code, value = self.cli('storage-bind', {'directory': str(self.data), 'confirmed': True, 'expected': 0})
        self.assertNotEqual(code, 0)
        self.assertFalse(self.binding.exists())

    def test_binding_file_with_lock_suffix_does_not_collide_with_its_lock(self):
        path = self.binding.with_suffix('.lock')
        code, value = self.cli('storage-bind', {'directory': str(self.data), 'confirmed': True, 'expected': 0}, binding=path)
        self.assertEqual(code, 0, value)
        self.assertEqual(json.loads(path.read_text())['revision'], 1)
        self.assertFalse(path.with_name(path.name + '.lock').exists())

    def test_storage_status_reports_missing_database(self):
        self.bind()
        self.store.close()
        self.data.rename(self.root / 'retained')
        code, value = self.cli('storage-status')
        self.assertEqual(code, 0, value)
        self.assertFalse(value['result']['available'])
        self.assertTrue(value['result']['recovery_needed'])
        self.store = Store(self.root / 'retained')

    def bundle(self):
        self.claim('历史总结尚待核实', status='pending')
        self.store.configure('PERSON_A', {'tone': '简洁'}, 0)
        self.bind()
        destination = self.root / 'backup'
        code, value = self.cli('storage-backup', {'destination': str(destination)})
        self.assertEqual(code, 0, value)
        return destination

    def test_verified_recovery_preserves_claim_status_and_configuration(self):
        bundle = self.bundle()
        destination = self.root / 'recovered'
        code, value = self.cli('storage-recover', {'manifest': str(bundle / 'recovery.json'), 'destination': str(destination), 'confirmed': True})
        self.assertEqual(code, 0, value)
        restored = Store(destination)
        try:
            self.assertEqual(Memory(restored).profile('PERSON_A')['claims'][0]['status'], 'pending')
            self.assertEqual(restored.get_config('PERSON_A')['tone'], '简洁')
        finally:
            restored.close()
        self.assertEqual(json.loads(self.binding.read_text())['data_directory'], str(self.data))

    def test_tampered_backup_is_rejected_before_destination_creation(self):
        bundle = self.bundle()
        with (bundle / 'snapshot.sqlite3').open('ab') as stream:
            stream.write(b'changed')
        destination = self.root / 'recovered'
        code, value = self.cli('storage-recover', {'manifest': str(bundle / 'recovery.json'), 'destination': str(destination), 'confirmed': True})
        self.assertNotEqual(code, 0)
        self.assertFalse(destination.exists())

    def test_recovery_manifest_cannot_escape_bundle(self):
        bundle = self.bundle()
        manifest = bundle / 'recovery.json'
        content = json.loads(manifest.read_text())
        content['snapshot'] = '../outside.sqlite3'
        manifest.write_text(json.dumps(content))
        code, value = self.cli('storage-recover', {'manifest': str(manifest), 'destination': str(self.root / 'new'), 'confirmed': True})
        self.assertNotEqual(code, 0)
        self.assertFalse((self.root / 'new').exists())

    def test_backup_and_recovery_never_overwrite_existing_directory(self):
        bundle = self.bundle()
        before = (bundle / 'snapshot.sqlite3').read_bytes()
        self.assertNotEqual(self.cli('storage-backup', {'destination': str(bundle)})[0], 0)
        self.assertNotEqual(self.cli('storage-recover', {'manifest': str(bundle / 'recovery.json'), 'destination': str(self.data), 'confirmed': True})[0], 0)
        self.assertEqual((bundle / 'snapshot.sqlite3').read_bytes(), before)

    def test_backup_does_not_claim_verified_when_foreign_keys_are_broken(self):
        self.store.db.execute('PRAGMA foreign_keys=OFF')
        self.store.db.execute('INSERT INTO claim_sources VALUES(?,?)', ('missing-claim', 'missing-source'))
        self.store.db.execute('PRAGMA foreign_keys=ON')
        before = self.store.path.read_bytes()
        destination = self.root / 'invalid-backup'
        code, value = self.cli('storage-backup', {'destination': str(destination)}, data=True)
        self.assertNotEqual(code, 0, value)
        self.assertFalse(destination.exists())
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_settings_show_effective_values_and_origins_without_raw_chat(self):
        self.store.configure('global', {'tone': '温和', 'max_chars': 40}, 0)
        self.store.configure('PERSON_A', {'tone': '直接'}, 0)
        self.memory.source('PERSON_A', 'chat', '不应展示的完整原始聊天')
        code, value = self.cli('user-status', {'identifier': 'PERSON_A'}, data=True)
        self.assertEqual(code, 0, value)
        state = value['result']
        self.assertEqual(state['config']['tone'], '直接')
        self.assertEqual(state['origins']['tone'], 'PERSON_A')
        self.assertEqual(state['origins']['max_chars'], 'global')
        self.assertEqual(state['extensions']['apply'], False)
        self.assertNotIn('不应展示的完整原始聊天', json.dumps(state, ensure_ascii=False))

    def test_status_for_unknown_person_does_not_fallback_to_another_profile(self):
        code, value = self.cli('user-status', {'identifier': 'UNKNOWN'}, data=True)
        self.assertEqual(value['result']['needs_identity'], True, value)
        self.assertNotIn('profile', value['result'])

    def test_status_inspection_does_not_change_database(self):
        before = self.store.path.read_bytes()
        code, value = self.cli('user-status', {'identifier': 'PERSON_A'}, data=True)
        self.assertEqual(code, 0, value)
        self.assertEqual(self.store.path.read_bytes(), before)

    def test_relative_date_does_not_pretend_update_time_is_message_time(self):
        self.claim('今天不方便见面', reason='boundary')
        claim = Runtime(self.store).context('PERSON_A', as_of='2026-11-02')['profile']['claims'][0]
        self.assertTrue(claim['temporal']['needs_reconfirmation'])
        self.assertEqual(claim['temporal']['date_basis'], 'record_update_not_message_time')

    def test_dated_claim_is_rechecked_even_with_warm_cache(self):
        claim_id = self.claim('今天不想出门', reason='boundary')
        current = Runtime(self.store).context('PERSON_A', as_of='2026-11-02')
        self.assertEqual(current['profile']['claims'][0]['status'], 'active')
        later = Runtime(self.store).context('PERSON_A', as_of='2026-11-03')
        self.assertTrue(later['cache_hit'])
        self.assertTrue(later['profile']['claims'][0]['temporal']['needs_reconfirmation'])
        stored = self.store.db.execute('SELECT status,content FROM claims WHERE id=?', (claim_id,)).fetchone()
        self.assertEqual(tuple(stored), ('active', '今天不想出门'))
        self.assertTrue(later['profile']['claims'][0]['temporal']['boundary_requires_explicit_change'])

    def test_weekly_and_vague_time_have_different_review_semantics(self):
        self.claim('这周不约见面', reason='boundary')
        self.claim('最近喜欢安静一点')
        values = Runtime(self.store).context('PERSON_A', as_of='2026-11-09')['profile']['claims']
        claims = {c['content']: c for c in values}
        self.assertEqual(claims['这周不约见面']['temporal']['valid_through'], '2026-11-08')
        self.assertEqual(claims['最近喜欢安静一点']['temporal']['state'], 'context_check')
        self.assertNotIn('valid_through', claims['最近喜欢安静一点']['temporal'])

    def test_other_common_temporary_statements_require_review_without_invented_deadline(self):
        for content in ['明天可以见面', '下周有空', '周末不想出门', '本月先不约', '今年先忙工作', '这几天想独处']:
            self.claim(content)
        values = Runtime(self.store).context('PERSON_A', as_of='2027-12-02')['profile']['claims']
        self.assertEqual(len(values), 6)
        for claim in values:
            self.assertTrue(claim.get('temporal', {}).get('needs_reconfirmation'), claim['content'])
            self.assertNotIn('valid_through', claim['temporal'])

    def test_stable_facts_and_pending_claims_are_not_promoted_by_time_processing(self):
        self.claim('生日是十一月二日', status='pending')
        result = Runtime(self.store).context('PERSON_A', as_of='2026-11-10')
        self.assertNotIn('temporal', result['profile']['claims'][0])
        self.assertEqual(result['profile']['claims'][0]['status'], 'pending')

    def test_explicit_valid_through_is_reviewed_after_that_date(self):
        self.claim('有效至2026-11-04：先不安排出游', reason='boundary')
        result = Runtime(self.store).context('PERSON_A', as_of='2026-11-05')
        self.assertTrue(result['profile']['claims'][0]['temporal']['needs_reconfirmation'])

    def test_temporal_annotations_cannot_overflow_fast_context_budget(self):
        for i in range(48):
            self.claim('今天第'+str(i)+'条：'+'临时信息'*70)
        result = Runtime(self.store).context('PERSON_A', as_of='2026-11-02')
        self.assertEqual(result['path'], 'STANDARD')
        self.assertFalse(result['profile_loaded'])
        self.assertEqual(len(self.memory.profile('PERSON_A')['claims']), 48)


if __name__ == '__main__':
    unittest.main()
