"""Runtime Engine: bounded, indexed context; the host model generates the reply."""
import json
import re
from datetime import date, datetime, timedelta, timezone
from . import __version__
from .integrity import Error, CONFIG_KEYS, canonical, sha, validate_configuration
from .memory import Memory
from .knowledge import Knowledge, TOPICS

class Runtime:
    def __init__(self, store):
        self.s=store

    def context(self, identifier, topic='daily', mode=None, custom=None, as_of=None):
        try:
            self.s.db.execute('BEGIN IMMEDIATE')
            result=self._context(identifier,topic,mode,custom)
            self._dated_context(result,as_of)
            if len(canonical(result).encode('utf-8'))>64*1024:
                result={'path':'STANDARD','reason':'dated context exceeds budget; consolidate without dropping boundaries',
                        'profile_loaded':False,'needs_profile_consolidation':True}
            self.s.db.execute('COMMIT')
            return result
        except Exception:
            if self.s.db.in_transaction:self.s.db.execute('ROLLBACK')
            raise

    @staticmethod
    def _dated_context(result, as_of=None):
        try:today=date.fromisoformat(as_of) if as_of is not None else datetime.now(timezone.utc).date()
        except (ValueError,TypeError):raise Error('as_of must be an ISO calendar date') from None
        for key in ('profile','user_profile'):
            for claim in result.get(key,{}).get('claims',[]):
                content=claim['content']
                explicit=re.search(r'(?:有效至|截至)\s*(\d{4}-\d{2}-\d{2})',content)
                relative=re.search(r'今天|今日|这周|本周|最近|近期|暂时|近日|这几天|这两天|目前|现在|今晚|今早|昨天|昨日|明天|后天|上周|下周|周末|本月|这个月|下个月|今年|明年|本季度|下季度',content)
                if not explicit and not relative:continue
                temporal={'state':'context_check','needs_reconfirmation':True,
                          'date_basis':'explicit_content' if explicit else 'record_update_not_message_time',
                          'instruction':'Historical statement: verify current applicability, never assume a changed boundary or permission.'}
                try:
                    anchor=datetime.fromisoformat(claim['updated_at']).date()
                    until=date.fromisoformat(explicit[1]) if explicit else None
                    if not explicit and relative[0] in {'今天','今日'}:until=anchor
                    if not explicit and relative[0] in {'这周','本周'}:until=anchor+timedelta(days=6-anchor.weekday())
                    if until is not None:
                        temporal.update(valid_through=until.isoformat(),
                                        state='expired' if today>until else ('within_scope' if explicit else 'context_check'),
                                        needs_reconfirmation=(today>until or not explicit))
                except (ValueError,TypeError):pass
                if claim.get('reason')=='boundary':temporal['boundary_requires_explicit_change']=True
                claim['temporal']=temporal

    def status(self, identifier=None):
        """Settings inspection is separate from reply generation and raw-memory retrieval."""
        try:
            self.s.db.execute('BEGIN')
            if identifier is not None and not self.s.query('SELECT id FROM people WHERE id=?',(identifier,)):
                return {'needs_identity':True,'profile_loaded':False}
            config={};origins={};revisions={}
            for scope in dict.fromkeys(['global','SELF']+([identifier] if identifier else [])):
                values=self.s.get_config(scope)
                config.update(values)
                origins.update({key:scope for key in values})
                revisions[scope]=self.s.revision('config:'+scope)
            result={'person_id':identifier,'config':config,'origins':origins,'config_revisions':revisions,
                    'extensions':{'apply':config.get('extension_enabled',False),'propose':config.get('extension_generate',False)},
                    'inspection_only':True}
            if identifier:
                profile=Memory(self.s).profile(identifier)
                result['profile']=profile
                count=len(profile['claims'])
                result['profile_capacity']={'used':count,'limit':48,'maintenance_recommended':count>=40}
            return result
        finally:
            if self.s.db.in_transaction:self.s.db.execute('ROLLBACK')

    def _context(self, identifier, topic='daily', mode=None, custom=None):
        if topic not in TOPICS: raise Error('unknown topic; choose daily, invite, boundary, conflict, uncertainty, review or general')
        custom={} if custom is None else custom
        if not isinstance(custom,dict):raise Error('custom must be a JSON object')
        validate_configuration(custom)
        if not isinstance(custom,dict) or set(custom)-CONFIG_KEYS: raise Error('invalid one-turn configuration')
        if mode in {'learn','import','audit','migrate','archive','extend'}:
            return {'path':'DEEP','generation':'host model required','extension_default':False}
        if mode not in {None,'reply','analysis','review'}: raise Error('unknown output mode')
        people=self.s.query('SELECT id FROM people WHERE id=?',(identifier,))
        if not people:
            return {'path':'STANDARD','needs_identity':True,'profile_loaded':False,
                    'instruction':'Ask only the necessary identity question; do not combine similar aliases.'}
        scopes=['person:SELF','person:'+identifier,'config:global','config:SELF','config:'+identifier,
                'extension:global','extension:'+identifier,'core']
        placeholders=','.join('?' for _ in scopes)
        revisions=self.s.query('SELECT scope,value FROM revisions WHERE scope IN ('+placeholders+') ORDER BY scope',scopes)
        core_version=Knowledge(self.s).version()
        fingerprint=sha(canonical([__version__,revisions,core_version]))
        cached=self.s.query('SELECT fingerprint,payload FROM cache WHERE person_id=? AND topic=?',(identifier,topic))
        hit=bool(cached and cached[0]['fingerprint']==fingerprint)
        if hit:
            result=json.loads(cached[0]['payload'])
        else:
            memory=Memory(self.s)
            profile=memory.profile(identifier)
            own=self.s.query('SELECT 1 FROM people WHERE id=?',('SELF',))
            user_profile=memory.profile('SELF') if own and identifier!='SELF' else {'claims':[]}
            profile['claims']=[c for c in profile['claims'] if c['status'] in {'active','pending'}]
            user_profile['claims']=[c for c in user_profile['claims'] if c['status'] in {'active','pending'}]
            cfg={}
            for scope in dict.fromkeys(['global','SELF',identifier]): cfg.update(self.s.get_config(scope))
            rows=self.s.query('SELECT data FROM core_rules WHERE version=? AND topic IN (?,?) ORDER BY CASE topic WHEN ? THEN 0 ELSE 1 END,id LIMIT 17',
                              (core_version,topic,'general',topic))
            if len(rows)>16:
                return {'path':'STANDARD','person_id':identifier,'profile':profile,'user_profile':user_profile,
                        'config':dict(cfg,**custom),'core_version':core_version,'profile_loaded':True,
                        'needs_theory_consolidation':True,'topic':topic,'minimum_matching_rules':17,
                        'theory_applied':False,'reason':'relevant theory exceeds the FAST budget; review or consolidate this topic without silently omitting approved rules'}
            theory=[json.loads(r['data']) for r in rows]
            # Cache contains only compact decision data, never raw sources or drafts.
            result={'path':'FAST','person_id':identifier,'profile':profile,'user_profile':user_profile,'config':cfg,
                    'core_version':core_version,'theory':theory,'extensions':[],'generation':'host model required'}
            if len(canonical(result).encode('utf-8'))>64*1024:
                return {'path':'STANDARD','reason':'compact context exceeds budget; consolidate without dropping boundaries','profile_loaded':False}
            self.s.db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?,?)',(identifier,topic,fingerprint,canonical(result)))
        # Query active branches only when allowed. One-turn flags cannot bypass branch review.
        cfg=dict(result['config']);cfg.update(custom)
        mode=mode or cfg.get('output_mode','reply')
        if cfg.get('extension_enabled') is True:
            rows=self.s.query("SELECT id,scope,version,data FROM extensions WHERE scope IN (?,?) AND state='active' ORDER BY id LIMIT 32",('global',identifier))
            result['extensions']=[dict(id=r['id'],scope=r['scope'],version=r['version'],**json.loads(r['data'])) for r in rows if json.loads(r['data'])['state']=='active']
        result['config']=cfg
        if len(canonical(result).encode('utf-8'))>64*1024:
            return {'path':'STANDARD','reason':'context exceeds budget; consolidate approved branches without dropping boundaries','profile_loaded':False}
        result['path']='FAST' if mode=='reply' else 'STANDARD'
        result['output_mode']=mode
        result['cache_hit']=hit
        result['priority']='facts and latest user intent > current instruction > person rules > global configuration > profile and approved branches > core'
        return result

    @staticmethod
    def check_reply(reply, config):
        errors=[]
        if not isinstance(reply,str) or not reply.strip(): return ['empty reply']
        if '\n' in reply.strip(): errors.append('expected one sendable reply')
        if len(reply)>config.get('max_chars',2000): errors.append('length exceeds preference')
        if any(word.casefold() in reply.casefold() for word in config.get('avoid',[])): errors.append('forbidden expression')
        return errors

def degraded_context(reason='private storage unavailable'):
    return {'path':'STANDARD','degraded':True,'profile_loaded':False,'reason':reason,
            'instruction':'State the missing requested capability; use only current supplied facts, never claim memory was read or saved.'}
