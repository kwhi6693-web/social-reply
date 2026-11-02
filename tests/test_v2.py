import json
import sys
import tempfile
import unittest
import contextlib
import sqlite3
import zipfile
import stat
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from sr.integrity import Store, Error, Conflict, safe_extract, canonical, sha
from sr.memory import Memory
from sr.knowledge import Knowledge
from sr.runtime import Runtime
from social_reply import migrate, restore, dispatch

class Acceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name)/'private', create=True)
        self.memory = Memory(self.store)
        self.memory.person('SELF', [])
        self.memory.person('PERSON_A', ['A'])
        self.memory.person('PERSON_B', ['B'])
        self.knowledge = Knowledge(self.store)
        self.knowledge.initialize()

    def tearDown(self):
        self.store.close()
        self.temp.cleanup()

    def source(self, person='PERSON_A', content='明确说喜欢散步', **kw):
        return self.memory.source(person, 'chat', content, **kw)['source_id']

    def claim(self, source, person='PERSON_A', content='喜欢散步', **kw):
        return self.memory.claim(person, content, [source], 'statement', 'high', 'preference', self.store.revision('person:'+person), **kw)

    def test_unique_evidence_deletion(self):
        source = self.source()
        self.claim(source)
        self.memory.delete_source(source)
        self.assertEqual(self.memory.profile('PERSON_A')['claims'], [])

    def test_unrelated_deletion_preserves_fact(self):
        self.claim(self.source())
        self.memory.delete_source(self.source(content='早上好'))
        self.assertEqual(len(self.memory.profile('PERSON_A')['claims']), 1)

    def test_cross_person_evidence_rejected(self):
        source = self.source('PERSON_B')
        with self.assertRaises(Error): self.claim(source)

    def test_repeated_source_does_not_grow(self):
        self.assertEqual(self.source(), self.source())

    def test_version_conflict_is_not_overwrite(self):
        source = self.source()
        old = self.store.revision('person:PERSON_A')
        self.claim(source)
        with self.assertRaises(Conflict):
            self.memory.claim('PERSON_A','另一事实',[source],'statement','high','preference',old)

    def test_draft_is_not_evidence(self):
        source = self.source(sent=False)
        with self.assertRaises(Error): self.claim(source)

    def test_extension_default_off(self):
        result = Runtime(self.store).context('PERSON_A', 'daily')
        self.assertEqual(result['extensions'], [])
        self.assertEqual(result['path'], 'FAST')

    def test_unknown_person_uses_standard(self):
        self.assertEqual(Runtime(self.store).context('UNKNOWN','daily')['path'],'STANDARD')

    def test_export_is_valid_private_copy(self):
        self.claim(self.source())
        target = Path(self.temp.name)/'export.sqlite3'
        self.store.export(target)
        self.assertGreater(target.stat().st_size,0)

    def test_raw_record_is_separate_from_compact_profile(self):
        source=self.source(content='原始记录。'*1000)
        self.claim(source)
        result=Runtime(self.store).context('PERSON_A')
        self.assertNotIn('原始记录。',json.dumps(result,ensure_ascii=False))
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM sources').fetchone()[0],1)

    def test_independent_evidence_preserves_fact(self):
        a=self.source(content='一次明确陈述');b=self.source(content='另一次明确确认')
        self.memory.claim('PERSON_A','喜欢散步',[a,b],'statement','high','preference',self.store.revision('person:PERSON_A'))
        self.memory.delete_source(a)
        self.assertEqual(self.memory.profile('PERSON_A')['claims'][0]['source_refs'],[b])

    def test_same_event_not_stable_pattern(self):
        a=self.source(content='截图一',event_group='same');b=self.source(content='截图二',event_group='same')
        with self.assertRaises(Error):self.memory.claim('PERSON_A','模式',[a,b],'inference','medium','stable_pattern',self.store.revision('person:PERSON_A'))

    def test_ordinary_event_not_promoted(self):
        source=self.source()
        with self.assertRaises(Error):self.memory.claim('PERSON_A','早上好',[source],'statement','high','ordinary',self.store.revision('person:PERSON_A'))

    def test_compact_profile_limit(self):
        source=self.source()
        for n in range(48):self.claim(source,content='有价值结论'+str(n))
        with self.assertRaises(Error):self.claim(source,content='不应继续追加')
        self.assertEqual(len(self.memory.profile('PERSON_A')['claims']),48)

    def test_failure_rolls_back_claim_and_refs(self):
        a=self.source();first=self.claim(a)
        self.claim(a,content='另一条现有结论')
        rev=self.store.revision('person:PERSON_A')
        with self.assertRaises(sqlite3.IntegrityError):
            self.memory.claim('PERSON_A','另一条现有结论',[a],'statement','high','correction',rev,claim_id=first['claim_id'])
        self.assertEqual(self.store.revision('person:PERSON_A'),rev)
        self.assertEqual(len(self.memory.profile('PERSON_A')['claims']),2)

    def test_person_delete_clears_all_and_prevents_rebuild(self):
        self.claim(self.source());Runtime(self.store).context('PERSON_A')
        self.store.configure('PERSON_A',{'tone':'自然'},0)
        self.memory.delete_person('PERSON_A',self.store.revision('person:PERSON_A'))
        for table in ['claims','sources','cache']:
            self.assertEqual(self.store.db.execute('SELECT count(*) FROM '+table+' WHERE person_id=?',('PERSON_A',)).fetchone()[0],0)
        with self.assertRaises(Error):self.memory.person('PERSON_A',[])
        self.memory.person('PERSON_A',[],allow_recreate=True)

    def test_export_restore_and_corruption(self):
        self.claim(self.source())
        export=Path(self.temp.name)/'backup.sqlite3';self.store.export(export)
        restored=Path(self.temp.name)/'restored';restore(export,restored)
        copy=Store(restored)
        self.assertEqual(len(Memory(copy).profile('PERSON_A')['claims']),1);copy.close()
        invalid=Path(self.temp.name)/'invalid';invalid.write_bytes(b'corrupt')
        with self.assertRaises(sqlite3.DatabaseError):restore(invalid,Path(self.temp.name)/'bad')

    def test_fake_schema_cannot_restore(self):
        p=Path(self.temp.name)/'fake.sqlite3'
        with sqlite3.connect(p) as db:db.execute('PRAGMA user_version=2')
        with self.assertRaises(Error):restore(p,Path(self.temp.name)/'bad')

    def test_unknown_schema_not_restamped(self):
        p=Path(self.temp.name)/'future';p.mkdir()
        with sqlite3.connect(p/'social-reply.sqlite3') as db:db.execute('PRAGMA user_version=99')
        with self.assertRaises(Error):Store(p,create=True)
        with sqlite3.connect(p/'social-reply.sqlite3') as db:self.assertEqual(db.execute('PRAGMA user_version').fetchone()[0],99)

    def test_null_versions_cannot_bypass_protection(self):
        with self.assertRaises(Error):self.store.configure('global',{'tone':'自然'},None)
        with self.assertRaises(Error):self.memory.delete_person('PERSON_A',None)
        with self.assertRaises(Error):dispatch(self.store,'config-reset',{'scope':'global','expected':None})

    def test_string_false_cannot_recreate_deleted_person(self):
        self.memory.delete_person('PERSON_A',self.store.revision('person:PERSON_A'))
        with self.assertRaises(Error):self.memory.person('PERSON_A',[],allow_recreate='false')
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM tombstones WHERE id='PERSON_A'").fetchone()[0],1)

    def test_migration_retry_preserves_later_verification(self):
        req={'apply':True,'records':[{'person_id':'PERSON_A','content':'历史摘要','claims':['偏好']}]}
        first=migrate(self.store,req)['records'][0]
        self.memory.claim('PERSON_A','偏好',[first['source_id']],'statement','high','preference',self.store.revision('person:PERSON_A'))
        migrate(self.store,req)
        self.assertEqual(self.memory.profile('PERSON_A')['claims'][0]['status'],'active')

    def branch(self,scope='PERSON_A',refs=None):
        b=self.knowledge.propose_extension(scope,'短句表达','preference',refs or ['builtin:V01'],'日常')['branch_id']
        self.knowledge.transition(b,'reviewed',1)
        self.knowledge.transition(b,'active',2,confirmed=True)
        return b

    def test_extension_activation_needs_confirmation(self):
        b=self.knowledge.propose_extension('PERSON_A','短句','preference',['builtin:V01'],'日常')['branch_id']
        self.knowledge.transition(b,'reviewed',1)
        with self.assertRaises(Error):self.knowledge.transition(b,'active',2)

    def test_extension_does_not_change_core(self):
        version=self.knowledge.version();self.branch()
        self.assertEqual(version,self.knowledge.version())

    def test_extension_off_revoke_and_cross_person(self):
        b=self.branch();self.store.configure('PERSON_A',{'extension_enabled':True},0)
        self.assertEqual(len(Runtime(self.store).context('PERSON_A')['extensions']),1)
        self.assertEqual(Runtime(self.store).context('PERSON_B')['extensions'],[])
        self.knowledge.transition(b,'revoked',3)
        self.assertEqual(Runtime(self.store).context('PERSON_A')['extensions'],[])

    def test_inactive_candidates_do_not_hide_active(self):
        ids=[self.knowledge.propose_extension('PERSON_A','候选'+str(i),'preference',['builtin:V01'],'日常')['branch_id'] for i in range(33)]
        chosen=max(ids);self.knowledge.transition(chosen,'reviewed',1);self.knowledge.transition(chosen,'active',2,confirmed=True)
        self.store.configure('PERSON_A',{'extension_enabled':True},0)
        self.assertEqual(Runtime(self.store).context('PERSON_A')['extensions'][0]['id'],chosen)

    def test_extension_rollback_independent(self):
        b=self.branch();self.knowledge.transition(b,'revoked',3)
        self.knowledge.rollback_extension(b,3,4,confirmed=True)
        self.assertEqual(self.knowledge.version(),1)

    def test_person_source_cannot_feed_global_theory(self):
        s=self.source()
        with self.assertRaises(Error):self.knowledge.propose_extension('global','不应传播','inference',[s],'未知')

    def test_deleted_source_clears_branch_history(self):
        s=self.source();b=self.branch(refs=[s]);self.memory.delete_source(s)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM extensions').fetchone()[0],0)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM extension_history').fetchone()[0],0)

    def test_core_import_is_versioned_and_rollbackable(self):
        s=self.memory.source(None,'document','新理论资料')['source_id']
        rule={'id':'NEW_A','topic':'daily','content':'具体回应已确认的分享','conditions':'日常','limits':'不推断未知','source_refs':[s]}
        p=self.knowledge.propose_core([rule],'用户审核采用')['proposal_id']
        self.assertEqual(self.knowledge.version(),1)
        self.knowledge.commit_core(p,1,confirmed=True)
        self.assertEqual(self.knowledge.version(),2)
        self.knowledge.rollback_core(1,2);self.assertEqual(self.knowledge.version(),1)
        self.memory.delete_source(s)
        self.knowledge.rollback_core(2,1)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM core_rules WHERE id='NEW_A'").fetchone()[0],0)

    def test_cache_survives_unrelated_person_change(self):
        runtime=Runtime(self.store);runtime.context('PERSON_A')
        self.source('PERSON_B',content='无关资料')
        self.assertTrue(runtime.context('PERSON_A')['cache_hit'])

    def test_current_instruction_overrides_old_goal(self):
        self.store.configure('PERSON_A',{'relationship_goal':'继续了解'},0)
        result=Runtime(self.store).context('PERSON_A',custom={'relationship_goal':'普通联系'})
        self.assertEqual(result['config']['relationship_goal'],'普通联系')
        self.assertEqual(Runtime(self.store).context('PERSON_A')['config']['relationship_goal'],'继续了解')

    def test_person_version_change_invalidates_cache(self):
        runtime=Runtime(self.store);runtime.context('PERSON_A');self.claim(self.source())
        self.assertFalse(runtime.context('PERSON_A')['cache_hit'])

    def test_deep_path_and_no_forced_profile_reads(self):
        self.assertEqual(Runtime(self.store).context('PERSON_A',mode='learn')['path'],'DEEP')

    def test_latest_context_is_atomic_against_deletion(self):
        self.claim(self.source());other=Store(self.store.root);other.db.execute('PRAGMA busy_timeout=1')
        original=self.store.query;attempted=[]
        def interleave(sql,args=()):
            if sql=='SELECT 1 FROM people WHERE id=?' and not attempted:
                attempted.append(True)
                with self.assertRaises(sqlite3.OperationalError):Memory(other).delete_person('PERSON_A',other.revision('person:PERSON_A'))
            return original(sql,args)
        self.store.query=interleave
        Runtime(self.store).context('PERSON_A')
        Memory(other).delete_person('PERSON_A',other.revision('person:PERSON_A'))
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM cache WHERE person_id='PERSON_A'").fetchone()[0],0);other.close()

    def test_deleted_person_cannot_leave_orphan_branch(self):
        source=self.source();other=Store(self.store.root);original=self.store.write
        @contextlib.contextmanager
        def interleave(scope,expected=None):
            if scope=='extension:PERSON_A':Memory(other).delete_person('PERSON_A',other.revision('person:PERSON_A'))
            with original(scope,expected) as db:yield db
        self.store.write=interleave
        with self.assertRaises(Error):self.knowledge.propose_extension('PERSON_A','私有候选','statement',[source],'日常')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM extensions').fetchone()[0],0);other.close()

    def test_safe_extract_rejects_traversal_and_symlink(self):
        for name,mode in [('../escape',0),('link',stat.S_IFLNK<<16),('CON.txt',0),('folder\\bad',0)]:
            p=Path(self.temp.name)/'bad.zip';info=zipfile.ZipInfo(name);info.external_attr=mode
            with zipfile.ZipFile(p,'w') as z:z.writestr(info,'synthetic')
            with self.assertRaises(Error):safe_extract(p,Path(self.temp.name)/'rejected')
            self.assertFalse((Path(self.temp.name)/'rejected').exists())

    def test_safe_extract_rejects_bomb_and_collision(self):
        p=Path(self.temp.name)/'bomb.zip'
        with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:z.writestr('large.txt','A'*100000)
        with self.assertRaises(Error):safe_extract(p,Path(self.temp.name)/'rejected',max_ratio=10)
        with zipfile.ZipFile(p,'w') as z:z.writestr('A.txt','a');z.writestr('a.txt','b')
        with self.assertRaises(Error):safe_extract(p,Path(self.temp.name)/'rejected')

    def test_anonymized_summary_consolidates_multiple_orphans(self):
        source=self.source();self.claim(source,content='私密细节一');self.claim(source,content='私密细节二')
        self.memory.delete_source(source,retain_anonymized='用户批准的摘要')
        claims=self.memory.profile('PERSON_A')['claims']
        self.assertEqual(len(claims),1);self.assertEqual(claims[0]['content'],'用户批准的摘要')
        self.assertEqual(claims[0]['status'],'pending')

    def test_schema_cascade_tampering_is_rejected(self):
        export=Path(self.temp.name)/'tampered.sqlite3';self.store.export(export)
        with sqlite3.connect(export) as db:
            db.execute('PRAGMA writable_schema=ON')
            sql=db.execute("SELECT sql FROM sqlite_master WHERE name='sources'").fetchone()[0]
            db.execute("UPDATE sqlite_master SET sql=? WHERE name='sources'",(sql.replace('ON DELETE CASCADE','ON DELETE SET NULL'),))
            db.execute('PRAGMA writable_schema=OFF')
        with self.assertRaises(Error):restore(export,Path(self.temp.name)/'bad-restore')

    def test_core_proposal_cannot_resurrect_deleted_source(self):
        source=self.memory.source(None,'document','待审核理论')['source_id']
        other=Store(self.store.root);original=self.store.write
        @contextlib.contextmanager
        def interleave(scope,expected=None):
            if scope=='knowledge':Memory(other).delete_source(source)
            with original(scope,expected) as db:yield db
        self.store.write=interleave
        rule={'id':'CANDIDATE','topic':'daily','content':'候选','conditions':'日常','limits':'未知','source_refs':[source]}
        with self.assertRaises(Error):self.knowledge.propose_core([rule],'审核')
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM theory_proposals').fetchone()[0],0);other.close()

    def test_new_global_source_keeps_old_fast_cache(self):
        runtime=Runtime(self.store);runtime.context('PERSON_A')
        self.memory.source(None,'video-note','新增尚未审核的视频说明')
        self.assertTrue(runtime.context('PERSON_A')['cache_hit'])

    def test_core_duplicate_preserves_new_provenance(self):
        rule=json.loads(self.store.db.execute("SELECT data FROM core_rules WHERE version=1 AND id='V01'").fetchone()[0])
        source=self.memory.source(None,'document','相同原则的新资料')['source_id']
        rule['id']='DUPLICATE';rule['source_refs']=[source]
        proposal=self.knowledge.propose_core([rule],'合并重复')['proposal_id']
        result=self.knowledge.commit_core(proposal,1,confirmed=True)
        merged=json.loads(self.store.db.execute("SELECT data FROM core_rules WHERE version=2 AND id='V01'").fetchone()[0])
        self.assertIn(source,merged['source_refs']);self.assertEqual(result['duplicates_merged'],1)

    def test_unavailable_storage_is_honest_degradation(self):
        command=Path(__file__).resolve().parents[1]/'scripts/social_reply.py'
        result=subprocess.run([sys.executable,'-B',str(command),'--data',str(Path(self.temp.name)/'unavailable'),'context'],input='{}',capture_output=True,encoding='utf-8')
        value=json.loads(result.stdout)
        self.assertEqual(value['status'],'degraded');self.assertFalse(value['result']['profile_loaded'])

    def test_relevant_theory_overflow_is_explicit_not_silent(self):
        rules=[{'id':'NEW_BOUNDARY_'+str(i),'topic':'boundary','content':'独立边界规则'+str(i),
                'conditions':'相关场景','limits':'不覆盖真实事实','source_refs':['builtin:V01']} for i in range(12)]
        proposal=self.knowledge.propose_core(rules,'明确采用这些规则')['proposal_id']
        self.knowledge.commit_core(proposal,1,confirmed=True)
        result=Runtime(self.store).context('PERSON_A','boundary')
        self.assertEqual(result['path'],'STANDARD');self.assertTrue(result['needs_theory_consolidation'])
        self.assertFalse(result['theory_applied'])
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM core_rules WHERE version=2 AND topic='boundary'").fetchone()[0],20)
        self.assertEqual(self.store.db.execute('SELECT count(*) FROM cache').fetchone()[0],0)

    def test_unrelated_theory_growth_keeps_fast_path(self):
        rules=[{'id':'OTHER_REVIEW_'+str(i),'topic':'review','content':'复盘专项规则'+str(i),
                'conditions':'复盘','limits':'示例','source_refs':['builtin:V32']} for i in range(40)]
        proposal=self.knowledge.propose_core(rules,'复盘专项')['proposal_id'];self.knowledge.commit_core(proposal,1,confirmed=True)
        result=Runtime(self.store).context('PERSON_A','daily')
        self.assertEqual(result['path'],'FAST');self.assertNotIn('needs_theory_consolidation',result)

    def test_context_parameter_errors_are_actionable(self):
        command=Path(__file__).resolve().parents[1]/'scripts/social_reply.py'
        for request,expected_message in [({'identifier':'PERSON_A','topic':'a pasted chat'},'daily'),
                                         ({'identifier':'PERSON_A','custom':'a style sentence'},'JSON object')]:
            result=subprocess.run([sys.executable,'-B',str(command),'--data',str(self.store.root),'context'],input=json.dumps(request),capture_output=True,encoding='utf-8')
            value=json.loads(result.stdout)
            self.assertEqual(value['status'],'failed');self.assertIn(expected_message,value['message'])

    def test_legacy_runtime_cache_is_not_reused_after_upgrade(self):
        Runtime(self.store).context('PERSON_A')
        scopes=['person:SELF','person:PERSON_A','config:global','config:SELF','config:PERSON_A','extension:global','extension:PERSON_A','core']
        rows=self.store.query('SELECT scope,value FROM revisions WHERE scope IN ('+','.join('?' for _ in scopes)+') ORDER BY scope',scopes)
        legacy=sha(canonical([rows,self.knowledge.version()]))
        self.store.db.execute('UPDATE cache SET fingerprint=? WHERE person_id=?',(legacy,'PERSON_A'))
        result=Runtime(self.store).context('PERSON_A')
        self.assertFalse(result['cache_hit']);self.assertEqual(result['path'],'FAST')

    def test_alias_change_retains_person_and_detects_ambiguity(self):
        self.memory.update_aliases('PERSON_A',['共同昵称'],self.store.revision('person:PERSON_A'))
        self.memory.update_aliases('PERSON_B',['共同昵称'],self.store.revision('person:PERSON_B'))
        self.assertFalse(self.memory.resolve('共同昵称')['resolved'])

    def test_configured_analysis_mode_and_invalid_custom(self):
        self.store.configure('global',{'output_mode':'analysis'},0)
        self.assertEqual(Runtime(self.store).context('PERSON_A')['path'],'STANDARD')
        with self.assertRaises(Error):Runtime(self.store).context('PERSON_A',custom={'max_chars':'wrong'})

    def test_revoked_claim_not_loaded_for_reply(self):
        s=self.source();first=self.claim(s)
        self.memory.claim('PERSON_A','喜欢散步',[s],'statement','high','preference',self.store.revision('person:PERSON_A'),claim_id=first['claim_id'],status='revoked')
        self.assertEqual(Runtime(self.store).context('PERSON_A')['profile']['claims'],[])

    def test_malformed_zip_preserves_json_protocol(self):
        bad=Path(self.temp.name)/'bad.zip';bad.write_bytes(b'not a zip')
        command=Path(__file__).resolve().parents[1]/'scripts/social_reply.py'
        result=subprocess.run([sys.executable,'-B',str(command),'extract'],input=json.dumps({'archive':str(bad),'destination':str(Path(self.temp.name)/'badout')}),text=True,capture_output=True)
        self.assertEqual(json.loads(result.stdout)['status'],'failed');self.assertNotIn('Traceback',result.stderr)

if __name__ == '__main__': unittest.main()
