"""Profile & Memory: compact claims are separate from retained evidence."""
import json
import uuid
from .integrity import Error, canonical, now, person_id, sha, text, expected_version

MAX_CLAIMS = 48
TYPES = {'fact','statement','user_statement','inference','unknown'}
REASONS = {'stable_fact','preference','boundary','correction','stable_pattern'}

class Memory:
    def __init__(self, store):
        self.s = store

    def person(self, identifier, aliases=None, allow_recreate=False):
        identifier = person_id(identifier)
        aliases = [] if aliases is None else aliases
        if type(allow_recreate) is not bool:raise Error('recreation requires an explicit boolean')
        if not isinstance(aliases,list) or len(aliases)>16:
            raise Error('invalid aliases')
        aliases = list(dict.fromkeys(text(a,80) for a in aliases))
        with self.s.write('person:'+identifier) as db:
            if db.execute('SELECT 1 FROM tombstones WHERE id=?',(identifier,)).fetchone() and allow_recreate is not True:
                raise Error('deleted person cannot be rebuilt without explicit recreation')
            if db.execute('SELECT 1 FROM people WHERE id=?',(identifier,)).fetchone():
                raise Error('person exists; aliases require a versioned update')
            db.execute('DELETE FROM tombstones WHERE id=?',(identifier,))
            db.execute('INSERT INTO people VALUES(?,?)',(identifier,canonical(aliases)))
            db.executemany('INSERT INTO aliases VALUES(?,?)',[(a,identifier) for a in aliases])
        return {'person_id':identifier,'revision':self.s.revision('person:'+identifier)}

    def resolve(self, alias):
        rows = self.s.query('SELECT person_id FROM aliases WHERE alias=? ORDER BY person_id',(text(alias,80),))
        return {'matches':[r['person_id'] for r in rows], 'resolved':len(rows)==1}

    def update_aliases(self,identifier,aliases,expected):
        person_id(identifier);expected_version(expected)
        if not isinstance(aliases,list) or len(aliases)>16:raise Error('invalid aliases')
        values=list(dict.fromkeys(text(a,80) for a in aliases))
        with self.s.write('person:'+identifier,expected) as db:
            if not db.execute('SELECT 1 FROM people WHERE id=?',(identifier,)).fetchone():raise Error('person unavailable')
            db.execute('UPDATE people SET aliases=? WHERE id=?',(canonical(values),identifier))
            db.execute('DELETE FROM aliases WHERE person_id=?',(identifier,))
            db.executemany('INSERT INTO aliases VALUES(?,?)',[(a,identifier) for a in values])
        return {'person_id':identifier,'revision':self.s.revision('person:'+identifier)}

    def source(self, identifier, kind, content, event_group=None, sent=True):
        if identifier is not None:
            person_id(identifier)
            if not self.s.db.execute('SELECT 1 FROM people WHERE id=?',(identifier,)).fetchone():
                raise Error('unknown person; explicit creation required')
        if kind not in {'chat','document','feedback','transcript','legacy','video-note'} or type(sent) is not bool:
            raise Error('invalid source metadata')
        content = text(content, 2*1024*1024)
        digest = sha(content)
        row = self.s.db.execute('SELECT id FROM sources WHERE person_id IS ? AND kind=? AND digest=?',(identifier,kind,digest)).fetchone()
        if row:
            return {'source_id':row[0],'duplicate':True}
        source_id = 'S'+uuid.uuid4().hex
        with self.s.write('person:'+identifier if identifier else 'knowledge') as db:
            db.execute('INSERT INTO sources VALUES(?,?,?,?,?,?,?,?)',
                       (source_id,identifier,kind,content,digest,text(event_group or digest,120),int(sent),now()))
        return {'source_id':source_id,'duplicate':False}

    def claim(self, identifier, content, source_refs, evidence_type, confidence, reason, expected,
              claim_id=None, status='active', preserve_existing=False):
        person_id(identifier)
        content = text(content,1000)
        if evidence_type not in TYPES or confidence not in {'high','medium','low','unknown'} or reason not in REASONS:
            raise Error('invalid promotion metadata')
        if status not in {'active','pending','corrected','revoked'} or not isinstance(source_refs,list) or not 1<=len(source_refs)<=8:
            raise Error('important claims require bounded actual sources')
        if evidence_type in {'inference','unknown'} and confidence=='high':
            raise Error('inference cannot be a verified high-confidence fact')
        if type(expected) is not int:
            raise Error('expected person revision required')
        with self.s.write('person:'+identifier,expected) as db:
            groups=set()
            for ref in set(source_refs):
                row=db.execute('SELECT person_id,sent,event_group FROM sources WHERE id=?',(ref,)).fetchone()
                if not row or row[0]!=identifier or not row[1]:
                    raise Error('missing, draft, or cross-person evidence')
                groups.add(row[2])
            if reason=='stable_pattern' and len(groups)<2:
                raise Error('stable pattern needs independent contexts')
            existing=db.execute('SELECT id FROM claims WHERE person_id=? AND content=?',(identifier,content)).fetchone()
            if existing and preserve_existing:
                return {'claim_id':existing[0],'preserved_existing':True}
            if existing and claim_id is None:
                claim_id=existing[0]
            if claim_id:
                if not db.execute('SELECT 1 FROM claims WHERE id=? AND person_id=?',(claim_id,identifier)).fetchone():
                    raise Error('claim does not belong to person')
                db.execute('UPDATE claims SET content=?,evidence_type=?,confidence=?,status=?,reason=?,updated_at=? WHERE id=?',
                           (content,evidence_type,confidence,status,reason,now(),claim_id))
                db.execute('DELETE FROM claim_sources WHERE claim_id=?',(claim_id,))
            else:
                count=db.execute('SELECT count(*) FROM claims WHERE person_id=?',(identifier,)).fetchone()[0]
                if count>=MAX_CLAIMS:
                    raise Error('compact profile limit reached; consolidate before adding')
                claim_id='C'+uuid.uuid4().hex
                db.execute('INSERT INTO claims VALUES(?,?,?,?,?,?,?,?)',(claim_id,identifier,content,evidence_type,confidence,status,reason,now()))
            db.executemany('INSERT INTO claim_sources VALUES(?,?)',[(claim_id,r) for r in set(source_refs)])
        return {'claim_id':claim_id,'revision':self.s.revision('person:'+identifier)}

    def profile(self, identifier):
        if self.s.db.in_transaction:return self._profile(identifier)
        try:
            self.s.db.execute('BEGIN')
            result=self._profile(identifier)
            self.s.db.execute('COMMIT')
            return result
        except Exception:
            if self.s.db.in_transaction:self.s.db.execute('ROLLBACK')
            raise

    def _profile(self, identifier):
        person_id(identifier)
        rows=self.s.query('SELECT id,aliases FROM people WHERE id=?',(identifier,))
        if not rows:
            raise Error('unknown person')
        claims=self.s.query('SELECT id,content,evidence_type,confidence,status,reason,updated_at FROM claims WHERE person_id=? ORDER BY id LIMIT ?',
                           (identifier,MAX_CLAIMS))
        refs=self.s.query('SELECT cs.claim_id,cs.source_id FROM claim_sources cs JOIN claims c ON c.id=cs.claim_id WHERE c.person_id=?',(identifier,))
        for claim in claims:
            claim['source_refs']=[r['source_id'] for r in refs if r['claim_id']==claim['id']]
        return {'person_id':identifier,'aliases':json.loads(rows[0]['aliases']),'revision':self.s.revision('person:'+identifier),'claims':claims}

    def delete_source(self, source_id, retain_anonymized=None):
        if retain_anonymized is not None:
            retain_anonymized=text(retain_anonymized,1000)
        row=self.s.db.execute('SELECT person_id FROM sources WHERE id=?',(source_id,)).fetchone()
        if not row:
            raise Error('source not found; nothing deleted')
        identifier=row[0]
        removed=[]; kept=[]
        with self.s.write('person:'+identifier if identifier else 'knowledge') as db:
            ids=[r[0] for r in db.execute('SELECT claim_id FROM claim_sources WHERE source_id=?',(source_id,))]
            db.execute('DELETE FROM sources WHERE id=?',(source_id,))
            orphans=[]
            for cid in ids:
                remaining=db.execute('SELECT count(*) FROM claim_sources WHERE claim_id=?',(cid,)).fetchone()[0]
                if remaining:
                    kept.append(cid)
                else:
                    orphans.append(cid)
            summary_id=None
            if retain_anonymized is not None and orphans:
                existing=db.execute('SELECT id FROM claims WHERE person_id=? AND content=?',(identifier,retain_anonymized)).fetchone()
                summary_id=existing[0] if existing else orphans[0]
                if summary_id in orphans:
                    db.execute("UPDATE claims SET content=?,evidence_type='unknown',confidence='unknown',status='pending',updated_at=? WHERE id=?",(retain_anonymized,now(),summary_id))
                kept.append(summary_id)
            for cid in orphans:
                if cid!=summary_id:db.execute('DELETE FROM claims WHERE id=?',(cid,));removed.append(cid)
            from .knowledge import Knowledge
            Knowledge(self.s).purge_source(db,source_id)
        return {'source_deleted':True,'claims_removed':removed,'claims_retained':kept,
                'boundary':'local managed records only; external originals and platform backups are outside this operation'}

    def delete_person(self, identifier, expected):
        person_id(identifier)
        expected_version(expected)
        with self.s.write('person:'+identifier,expected) as db:
            if not db.execute('SELECT 1 FROM people WHERE id=?',(identifier,)).fetchone():
                raise Error('person not found')
            db.execute('DELETE FROM extension_history WHERE scope=?',(identifier,))
            db.execute('DELETE FROM extensions WHERE scope=?',(identifier,))
            db.execute('DELETE FROM config WHERE scope=?',(identifier,))
            db.execute('DELETE FROM people WHERE id=?',(identifier,))
            db.execute('INSERT OR REPLACE INTO tombstones VALUES(?,?)',(identifier,now()))
            db.execute('DELETE FROM revisions WHERE scope IN (?,?)',('config:'+identifier,'extension:'+identifier))
        return {'person_deleted':True,'scope':'profile, evidence, extensions, configuration, aliases, local cache',
                'boundary':'external originals, prior exports and platform versions are not remotely erased'}
