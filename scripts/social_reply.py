"""Local control entry. JSON stdin, JSON stdout; no network or model API calls."""
import argparse
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
import time
from pathlib import Path

sys.dont_write_bytecode=True
from sr.integrity import Store, StorageBinding, backup_bundle, Error, Conflict, canonical, file_sha, private_path, safe_extract, validate_schema, expected_version
from sr.memory import Memory
from sr.knowledge import Knowledge
from sr.runtime import Runtime, degraded_context

def restore(source, destination, expected_sha256=None):
    source=private_path(source);root=private_path(destination)
    if root.exists(): raise Error('restore requires a new private directory')
    if not source.is_file(): raise Error('backup unavailable')
    root.parent.mkdir(parents=True,exist_ok=True)
    staging=Path(tempfile.mkdtemp(prefix='.sr-restore-',dir=root.parent))
    try:
        target=staging/'social-reply.sqlite3'
        shutil.copyfile(source,target);os.chmod(target,0o600)
        digest=file_sha(target)
        if expected_sha256 is not None and digest!=expected_sha256:
            raise Error('copied snapshot checksum mismatch; no restoration performed')
        with sqlite3.connect(target.as_uri()+'?mode=ro',uri=True) as db:
            validate_schema(db,full=True)
        root.mkdir(mode=0o700)
        try:os.link(target,root/'social-reply.sqlite3')
        except Exception:
            try:root.rmdir()
            except OSError:pass
            raise
    finally:
        if staging.exists():shutil.rmtree(staging)
    return {'restored':True,'source_sha256':digest}

def recover_bundle(manifest, destination, confirmed=False):
    if confirmed is not True:raise Error('explicit private recovery confirmation required')
    path=private_path(manifest)
    if not path.is_file() or path.stat().st_size>8192:raise Error('recovery manifest unavailable')
    value=json.loads(path.read_text(encoding='utf-8'))
    if (not isinstance(value,dict) or value.get('format')!=1 or value.get('schema')!=2
            or value.get('snapshot')!='snapshot.sqlite3' or type(value.get('bytes')) is not int
            or not isinstance(value.get('sha256'),str)):
        raise Error('unsupported recovery manifest')
    source=private_path(path.parent/value['snapshot'])
    if not source.is_file() or source.stat().st_size!=value['bytes'] or file_sha(source)!=value['sha256']:
        raise Error('snapshot checksum mismatch; no restoration performed')
    result=restore(source,destination,expected_sha256=value['sha256'])
    result.update({'manifest_verified':True,'binding_changed':False})
    return result

def migrate(store, request):
    records=request.get('records',[])
    if not isinstance(records,list) or len(records)>256: raise Error('bounded migration batch required')
    # Prepared mapping is data, never executable instructions. Dry-run is the default.
    if request.get('apply') is not True:
        return {'dry_run':True,'records':len(records),'source_files_modified':False}
    memory=Memory(store);result=[]
    for item in records:
        identifier=item.get('person_id')
        if identifier and not store.db.execute('SELECT 1 FROM people WHERE id=?',(identifier,)).fetchone():
            memory.person(identifier,item.get('aliases',[]))
        source=memory.source(identifier,'legacy',item['content'],event_group=item.get('event_group'))
        claims=[]
        for value in item.get('claims',[]):
            # Legacy summaries retain uncertainty; never turn migration into fresh factual verification.
            claims.append(memory.claim(identifier,value,[source['source_id']],'unknown','unknown','stable_fact',
                                       store.revision('person:'+identifier),status='pending',preserve_existing=True))
        result.append({'source_id':source['source_id'],'duplicate':source['duplicate'],'claims':claims})
    return {'applied':True,'records':result,'source_files_modified':False,
            'transaction_boundary':'each evidence/claim operation is atomic; retry deduplicates; original mapping remains the recovery record'}

def dispatch(store, command, request):
    m=Memory(store);k=Knowledge(store)
    if command=='init':return k.initialize()
    if command=='context':return Runtime(store).context(**request)
    if command=='user-status':return Runtime(store).status(**request)
    if command=='storage-backup':return backup_bundle(store,**request)
    if command=='person-add':return m.person(**request)
    if command=='aliases-set':return m.update_aliases(**request)
    if command=='person-resolve':return m.resolve(**request)
    if command=='profile-get':return m.profile(**request)
    if command=='claim-upsert':return m.claim(**request)
    if command=='source-add':return m.source(**request)
    if command=='source-get':
        rows=store.query('SELECT * FROM sources WHERE id=? AND person_id IS ?',(request['source_id'],request.get('identifier')))
        if not rows:raise Error('source not found in authorized scope')
        return rows[0]
    if command=='memory-list':
        limit=request.get('limit',50);offset=request.get('offset',0)
        if type(limit) is not int or not 1<=limit<=100 or type(offset) is not int or offset<0:raise Error('invalid page')
        return store.query('SELECT id,kind,digest,event_group,created_at FROM sources WHERE person_id IS ? ORDER BY id LIMIT ? OFFSET ?',
                           (request.get('identifier'),limit,offset))
    if command=='source-delete':return m.delete_source(**request)
    if command=='person-delete':return m.delete_person(**request)
    if command=='config-get':
        scope=request.get('scope','global')
        row=store.query('SELECT (SELECT data FROM config WHERE scope=?) AS data, COALESCE((SELECT value FROM revisions WHERE scope=?),0) AS revision',(scope,'config:'+scope))[0]
        return {'config':json.loads(row['data']) if row['data'] else {},'revision':row['revision']}
    if command=='config-set':return store.configure(**request)
    if command=='config-reset':
        scope=request['scope']
        expected_version(request['expected'])
        with store.write('config:'+scope,request['expected']) as db:db.execute('DELETE FROM config WHERE scope=?',(scope,))
        return {'reset':True,'revision':store.revision('config:'+scope)}
    if command=='export':return store.export(**request)
    if command=='core-propose':return k.propose_core(**request)
    if command=='core-adopt':return k.commit_core(**request)
    if command=='core-rollback':return k.rollback_core(**request)
    if command=='extension-propose':return k.propose_extension(**request)
    if command=='extension-transition':return k.transition(**request)
    if command=='extension-rollback':return k.rollback_extension(**request)
    if command=='extension-delete':return k.clear_extensions(**request)
    if command=='extension-list':return store.query('SELECT id,scope,version,data FROM extensions WHERE scope=? ORDER BY id',(request.get('scope','global'),))
    if command=='core-get':
        version=request.get('version',k.version())
        return {'version':version,'rules':[json.loads(r['data']) for r in store.query('SELECT data FROM core_rules WHERE version=? ORDER BY id',(version,))]}
    if command=='migrate':return migrate(store,request)
    if command=='health':
        return {'integrity':store.db.execute('PRAGMA integrity_check').fetchone()[0],
                'foreign_keys':not bool(store.db.execute('PRAGMA foreign_key_check').fetchall()),'schema':2,'core_version':k.version()}
    raise Error('unknown command')

def main():
    for stream in (sys.stdin,sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__,epilog='JSON stdin: context requires identifier; topic is daily, invite, boundary, conflict, uncertainty, review or general; custom must be a JSON object. See README.md for other command fields.')
    parser.add_argument('--data',help='explicit authorized private directory outside the skill')
    parser.add_argument('--binding',help='optional private locator file; defaults to the user state directory')
    parser.add_argument('command',help='init, context, user-status, storage-bind/status/backup/recover, profile-get, person-add, aliases-set, source-add, claim-upsert, config-get/set/reset, core-get/propose/adopt/rollback, extension-propose/transition/rollback/delete/list, export, restore, migrate, health, extract or check-reply')
    args=parser.parse_args()
    store=None
    try:
        raw='' if sys.stdin.isatty() else sys.stdin.read(4*1024*1024+1)
        if len(raw)>4*1024*1024:raise Error('request too large')
        request=json.loads(raw) if raw.strip() else {}
        if not isinstance(request,dict):raise Error('request must be a JSON object')
        if args.command=='extract':result=safe_extract(**request)
        elif args.command=='restore':result=restore(**request)
        elif args.command=='storage-recover':result=recover_bundle(**request)
        elif args.command=='storage-bind':result=StorageBinding(args.binding).bind(**request)
        elif args.command=='storage-status':result=StorageBinding(args.binding).status()
        elif args.command=='check-reply':result={'violations':Runtime.check_reply(**request)}
        else:
            opened=time.perf_counter_ns()
            try:
                directory=args.data if args.data else StorageBinding(args.binding).directory()
                if args.command=='init' and not args.data:raise Error('new storage initialization requires an explicit authorized directory')
                store=Store(directory,create=args.command=='init')
            except Error:
                if args.command=='context':print(canonical({'status':'degraded','result':degraded_context()}));return 0
                raise
            store.reads=0;store.bytes_loaded=0
            prepared=time.perf_counter_ns()
            result=dispatch(store,args.command,request)
            if args.command=='context':
                result['diagnostics']={'sql_reads':store.reads,'row_json_bytes':store.bytes_loaded,'logical_data_files':1,'helper_invocations':1,
                                       'data_open_ms':(prepared-opened)/1e6,'context_prepare_ms':(time.perf_counter_ns()-prepared)/1e6}
        print(canonical({'status':'succeeded','result':result}))
        return 0
    except Conflict as exc:
        print(canonical({'status':'failed','error':'version_conflict','message':str(exc)}));return 2
    except Error as exc:
        print(canonical({'status':'failed','error':'operation_failed','message':str(exc)}));return 1
    except (OSError,ValueError,TypeError,KeyError,sqlite3.DatabaseError,zipfile.BadZipFile):
        print(canonical({'status':'failed','error':'invalid_input_or_storage','message':'operation failed; no success is asserted; inspect the request or restore a verified private export'}));return 1
    finally:
        if store:store.close()

if __name__=='__main__':raise SystemExit(main())
