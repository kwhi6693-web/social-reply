"""Knowledge Engine: immutable core versions, independently controlled branches."""
import json
import re
import uuid
from .integrity import Error, Conflict, PUBLIC_ROOT, canonical, now, text, expected_version as require_version

TOPICS={'daily','invite','boundary','conflict','uncertainty','review','general'}
STATES={'proposed','reviewed','active','rejected','revised','revoked'}

class Knowledge:
    def __init__(self, store):
        self.s=store

    def initialize(self):
        if self.s.db.execute('SELECT 1 FROM core_active').fetchone():
            return {'initialized':False,'core_version':self.version()}
        rules=json.loads((PUBLIC_ROOT/'assets/theory-core.json').read_text(encoding='utf-8'))['rules']
        with self.s.write('core') as db:
            db.execute('INSERT INTO core_versions VALUES(1,?,?)',('bundled foundation',now()))
            for rule in rules:
                self.validate_rule(rule,bundled=True)
                db.execute('INSERT INTO core_rules VALUES(?,?,?,?)',(1,rule['id'],rule['topic'],canonical(rule)))
            db.execute('INSERT INTO core_active VALUES(1,1)')
        return {'initialized':True,'core_version':1}

    def version(self):
        row=self.s.db.execute('SELECT version FROM core_active WHERE singleton=1').fetchone()
        if not row: raise Error('core not initialized')
        return row[0]

    def validate_refs(self, refs, scope='global'):
        if not isinstance(refs,list) or not 1<=len(refs)<=8:
            raise Error('bounded source references required')
        for ref in refs:
            if re.fullmatch(r'builtin:V(?:0[1-9]|[12][0-9]|3[0-2])',str(ref)):
                continue
            row=self.s.db.execute('SELECT person_id,sent FROM sources WHERE id=?',(ref,)).fetchone()
            owner=None if scope=='global' else scope
            if not row or row[0]!=owner or not row[1]:
                raise Error('missing or cross-scope theory source')

    def validate_rule(self, rule, bundled=False):
        required={'id','topic','content','conditions','limits','source_refs'}
        if not isinstance(rule,dict) or set(rule)!=required or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,39}',str(rule.get('id',''))):
            raise Error('invalid core rule structure')
        if rule['topic'] not in TOPICS: raise Error('invalid theory topic')
        for k in ['content','conditions','limits']: text(rule[k],1200)
        self.validate_refs(rule['source_refs'])

    def propose_core(self, rules, reason, replace_ids=None):
        if not isinstance(rules,list) or not 1<=len(rules)<=64:
            raise Error('review small theory batches')
        for rule in rules: self.validate_rule(rule)
        if len({r['id'] for r in rules})!=len(rules): raise Error('duplicate proposed rule IDs')
        replacements=replace_ids or []
        if not isinstance(replacements,list) or len(replacements)>64: raise Error('invalid replacements')
        proposal='T'+uuid.uuid4().hex
        data={'rules':rules,'reason':text(reason,1000),'replace_ids':replacements,'base_version':self.version()}
        with self.s.write('knowledge') as db:
            for rule in rules:self.validate_rule(rule)
            data['base_version']=self.version()
            db.execute('INSERT INTO theory_proposals VALUES(?,?,?)',(proposal,canonical(data),'proposed'))
        return {'proposal_id':proposal,'state':'proposed','core_unchanged':True}

    def commit_core(self, proposal, expected_version, confirmed=False):
        require_version(expected_version)
        if confirmed is not True: raise Error('explicit theory adoption confirmation required')
        with self.s.write('core') as db:
            if self.version()!=expected_version: raise Conflict('core changed; review again')
            row=db.execute('SELECT data,state FROM theory_proposals WHERE id=?',(proposal,)).fetchone()
            if not row or row[1]!='proposed': raise Error('proposal unavailable')
            data=json.loads(row[0])
            if data['base_version']!=expected_version: raise Conflict('proposal based on older core')
            existing={r['id']:json.loads(r['data']) for r in self.s.query('SELECT id,data FROM core_rules WHERE version=?',(expected_version,))}
            if set(data['replace_ids'])-existing.keys(): raise Error('replacement does not exist')
            for identifier in data['replace_ids']: del existing[identifier]
            duplicate_count=0
            for rule in data['rules']:
                self.validate_rule(rule)
                duplicate=next((r for r in existing.values() if r['content'].strip()==rule['content'].strip()),None)
                if duplicate:
                    if any(duplicate[key]!=rule[key] for key in ['topic','conditions','limits']):
                        raise Error('matching principle has different scope; review and explicitly replace')
                    refs=list(dict.fromkeys(duplicate['source_refs']+rule['source_refs']))
                    if len(refs)>8:raise Error('consolidate source references before merge')
                    duplicate['source_refs']=refs
                    duplicate_count+=1;continue
                if rule['id'] in existing: raise Error('rule ID conflict; explicitly replace it')
                existing[rule['id']]=rule
            version=db.execute('SELECT COALESCE(max(version),0)+1 FROM core_versions').fetchone()[0]
            db.execute('INSERT INTO core_versions VALUES(?,?,?)',(version,data['reason'],now()))
            db.executemany('INSERT INTO core_rules VALUES(?,?,?,?)',[(version,r['id'],r['topic'],canonical(r)) for r in existing.values()])
            db.execute('UPDATE core_active SET version=?',(version,))
            db.execute("UPDATE theory_proposals SET state='reviewed' WHERE id=?",(proposal,))
        return {'core_version':version,'duplicates_merged':duplicate_count,'previous_version':expected_version}

    def rollback_core(self, version, expected_version):
        require_version(expected_version)
        require_version(version)
        with self.s.write('core') as db:
            if self.version()!=expected_version: raise Conflict('core version changed')
            if not db.execute('SELECT 1 FROM core_versions WHERE version=?',(version,)).fetchone(): raise Error('version unavailable')
            db.execute('UPDATE core_active SET version=?',(version,))
        return {'core_version':version}

    def propose_extension(self, scope, content, kind, source_refs, conditions, counterevidence='尚未充分验证'):
        if scope!='global' and not self.s.db.execute('SELECT 1 FROM people WHERE id=?',(scope,)).fetchone():
            raise Error('unknown extension person')
        if kind not in {'fact','statement','inference','preference','unknown'}: raise Error('invalid extension evidence type')
        self.validate_refs(source_refs,scope)
        identifier='E'+uuid.uuid4().hex
        data={'content':text(content,1000),'kind':kind,'source_refs':source_refs,'conditions':text(conditions,500),
              'counterevidence':text(counterevidence,500),'state':'proposed','updated_at':now()}
        with self.s.write('extension:'+scope) as db:
            if scope!='global' and not db.execute('SELECT 1 FROM people WHERE id=?',(scope,)).fetchone():raise Error('person removed')
            self.validate_refs(source_refs,scope)
            db.execute('INSERT INTO extensions(id,scope,version,data) VALUES(?,?,1,?)',(identifier,scope,canonical(data)))
            db.execute('INSERT INTO extension_history VALUES(?,1,?,?)',(identifier,scope,canonical(data)))
        return {'branch_id':identifier,'version':1,'state':'proposed'}

    def transition(self, identifier, state, expected_version, confirmed=False, content=None):
        require_version(expected_version)
        row=self.s.db.execute('SELECT scope,version,data FROM extensions WHERE id=?',(identifier,)).fetchone()
        if not row: raise Error('branch unavailable')
        scope=row[0]
        allowed={'proposed':{'reviewed','rejected','revoked'},'reviewed':{'active','rejected','revoked'},
                 'active':{'revised','revoked'},'revised':{'reviewed','rejected','revoked'},'rejected':{'revoked'},'revoked':set()}
        with self.s.write('extension:'+scope) as db:
            current=db.execute('SELECT version,data FROM extensions WHERE id=?',(identifier,)).fetchone()
            if not current:raise Error('branch removed')
            if current[0]!=expected_version: raise Conflict('branch changed')
            data=json.loads(current[1])
            if state not in allowed[data['state']]: raise Error('invalid branch state transition')
            if state=='active':
                if confirmed is not True:raise Error('branch activation requires confirmation')
                if db.execute("SELECT count(*) FROM extensions WHERE scope=? AND state='active'",(scope,)).fetchone()[0]>=16:
                    raise Error('active branch limit reached; consolidate first')
            self.validate_refs(data['source_refs'],scope)
            if content is not None:
                if state!='revised': raise Error('content changes require revised state')
                data['content']=text(content,1000)
            data.update(state=state,updated_at=now())
            version=expected_version+1
            db.execute('UPDATE extensions SET version=?,data=?,state=? WHERE id=?',(version,canonical(data),state,identifier))
            db.execute('INSERT INTO extension_history VALUES(?,?,?,?)',(identifier,version,scope,canonical(data)))
        return {'branch_id':identifier,'version':version,'state':state}

    def rollback_extension(self, identifier, version, expected_version, confirmed=False):
        require_version(expected_version);require_version(version)
        if confirmed is not True: raise Error('branch rollback needs explicit confirmation')
        row=self.s.db.execute('SELECT scope,version FROM extensions WHERE id=?',(identifier,)).fetchone()
        if not row: raise Error('branch unavailable')
        scope=row[0]
        with self.s.write('extension:'+scope) as db:
            current=db.execute('SELECT version FROM extensions WHERE id=?',(identifier,)).fetchone()
            if not current:raise Error('branch removed')
            if current[0]!=expected_version: raise Conflict('branch changed')
            old=db.execute('SELECT data FROM extension_history WHERE id=? AND version=?',(identifier,version)).fetchone()
            if not old: raise Error('branch version unavailable')
            data=json.loads(old[0]);self.validate_refs(data['source_refs'],scope)
            new=expected_version+1
            if data['state']=='active' and db.execute("SELECT count(*) FROM extensions WHERE scope=? AND state='active' AND id!=?",(scope,identifier)).fetchone()[0]>=16:
                raise Error('active branch limit reached')
            db.execute('UPDATE extensions SET version=?,data=?,state=? WHERE id=?',(new,canonical(data),data['state'],identifier))
            db.execute('INSERT INTO extension_history VALUES(?,?,?,?)',(identifier,new,scope,canonical(data)))
        return {'branch_id':identifier,'version':new,'restored_version':version}

    def clear_extensions(self, scope):
        with self.s.write('extension:'+scope) as db:
            if scope!='global' and not db.execute('SELECT 1 FROM people WHERE id=?',(scope,)).fetchone():raise Error('person unavailable')
            count=db.execute('SELECT count(*) FROM extensions WHERE scope=?',(scope,)).fetchone()[0]
            db.execute('DELETE FROM extension_history WHERE scope=?',(scope,));db.execute('DELETE FROM extensions WHERE scope=?',(scope,))
            row=db.execute('SELECT data FROM config WHERE scope=?',(scope,)).fetchone()
            cfg=json.loads(row[0]) if row else {};cfg.update(extension_enabled=False,extension_generate=False)
            db.execute('INSERT OR REPLACE INTO config VALUES(?,?)',(scope,canonical(cfg)))
            db.execute('INSERT INTO revisions VALUES(?,1) ON CONFLICT(scope) DO UPDATE SET value=value+1',('config:'+scope,))
        return {'branches_deleted':count,'extensions_enabled':False}

    def purge_source(self, db, source_id):
        # Privacy deletion supersedes historical restoration; no retired snapshot may resurrect the evidence.
        db.execute('DELETE FROM cache')
        db.execute("INSERT INTO revisions VALUES('core',1) ON CONFLICT(scope) DO UPDATE SET value=value+1")
        for row in db.execute('SELECT version,id,data FROM core_rules').fetchall():
            data=json.loads(row[2])
            if source_id not in data['source_refs']: continue
            data['source_refs']=[r for r in data['source_refs'] if r!=source_id]
            if data['source_refs']: db.execute('UPDATE core_rules SET data=? WHERE version=? AND id=?',(canonical(data),row[0],row[1]))
            else: db.execute('DELETE FROM core_rules WHERE version=? AND id=?',(row[0],row[1]))
        for row in db.execute('SELECT id,scope,data FROM extensions').fetchall():
            if source_id in json.loads(row[2])['source_refs']:
                db.execute('DELETE FROM extension_history WHERE id=?',(row[0],));db.execute('DELETE FROM extensions WHERE id=?',(row[0],))
        for row in db.execute('SELECT id,version,data FROM extension_history').fetchall():
            if source_id in json.loads(row[2])['source_refs']:
                db.execute('DELETE FROM extension_history WHERE id=? AND version=?',(row[0],row[1]))
        for row in db.execute('SELECT id,data FROM theory_proposals').fetchall():
            if any(source_id in r['source_refs'] for r in json.loads(row[1])['rules']):
                db.execute('DELETE FROM theory_proposals WHERE id=?',(row[0],))
