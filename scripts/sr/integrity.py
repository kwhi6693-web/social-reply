"""Configuration & Integrity: transactions, private boundaries, safe ZIP handling."""
import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import stat
import tempfile
import unicodedata
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

PUBLIC_ROOT = Path(__file__).resolve().parents[2]
SCHEMA = 2
CONFIG_KEYS = {'language', 'tone', 'max_chars', 'nickname', 'avoid', 'relationship_goal',
               'output_mode', 'extension_enabled', 'extension_generate', 'extension_auto_lowrisk'}
REQUIRED = {
    'people':{'id','aliases'}, 'aliases':{'alias','person_id'}, 'tombstones':{'id','deleted_at'},
    'revisions':{'scope','value'}, 'sources':{'id','person_id','kind','content','digest','event_group','sent','created_at'},
    'claims':{'id','person_id','content','evidence_type','confidence','status','reason','updated_at'},
    'claim_sources':{'claim_id','source_id'}, 'config':{'scope','data'},
    'core_versions':{'version','reason','created_at'}, 'core_rules':{'version','id','topic','data'},
    'core_active':{'singleton','version'}, 'theory_proposals':{'id','data','state'},
    'extensions':{'id','scope','version','data','state'}, 'extension_history':{'id','version','scope','data'},
    'cache':{'person_id','topic','fingerprint','payload'},
}
_SCHEMA_SIGNATURE=None

class Error(Exception):
    pass

class Conflict(Error):
    pass

def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')

def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))

def sha(value):
    return hashlib.sha256(value if isinstance(value, bytes) else value.encode('utf-8')).hexdigest()

def file_sha(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()

def private_path(value):
    path = Path(value).expanduser().absolute()
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise Error('symlink storage is not supported')
    path = path.resolve()
    if path == PUBLIC_ROOT or PUBLIC_ROOT in path.parents:
        raise Error('private data must be outside the skill directory')
    return path

class StorageBinding:
    """A private, explicitly approved locator; never scans for user databases."""
    def __init__(self, path=None):
        base = Path(os.environ.get('XDG_STATE_HOME') or Path.home() / '.local' / 'state')
        self.path = private_path(path if path is not None else base / 'social-reply' / 'binding.json')

    def read(self):
        if not self.path.exists():
            return {'revision': 0}
        if not self.path.is_file() or self.path.stat().st_size > 8192:
            raise Error('private storage binding invalid; supply an authorized directory explicitly')
        try:
            value = json.loads(self.path.read_text(encoding='utf-8'))
            if (not isinstance(value, dict) or set(value) != {'format', 'revision', 'data_directory'}
                    or value['format'] != 1 or type(value['revision']) is not int or value['revision'] < 1
                    or not isinstance(value['data_directory'], str) or not Path(value['data_directory']).is_absolute()):
                raise ValueError()
            private_path(value['data_directory'])
            return value
        except (ValueError, TypeError):
            raise Error('private storage binding invalid; no data loaded') from None

    def directory(self):
        value = self.read()
        if 'data_directory' not in value:
            raise Error('private storage not bound; use current context or explicitly configure storage')
        return private_path(value['data_directory'])

    def status(self):
        value = self.read()
        configured = 'data_directory' in value
        available = configured and (self.directory() / 'social-reply.sqlite3').is_file()
        return {'configured': configured, 'available': bool(available), 'revision': value['revision'],
                'recovery_needed': configured and not available, 'checked': 'locator and file presence only',
                'durability': 'local binding; cross-host recovery requires an independently retained private backup'}

    def bind(self, directory, expected, confirmed=False):
        expected_version(expected)
        if confirmed is not True:
            raise Error('explicit private storage binding confirmation required')
        root = private_path(directory)
        check = Store(root)
        check.close()
        if self.path == root / 'social-reply.sqlite3':
            raise Error('binding must not replace a database')
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock = self.path.with_name(self.path.name + '.lock')
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            raise Conflict('storage binding busy; inspect an interrupted operation before retrying') from None
        temporary = None
        try:
            os.close(descriptor)
            current = self.read()
            if current['revision'] != expected:
                raise Conflict('storage binding revision changed; reread before switching')
            value = {'format': 1, 'revision': expected + 1, 'data_directory': str(root)}
            descriptor, temporary = tempfile.mkstemp(prefix='.binding-', dir=self.path.parent)
            with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
                stream.write(canonical(value))
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            if self.read() != value:
                raise Error('binding write could not be verified')
            return {'bound': True, 'revision': value['revision'], 'cross_host_durability': False}
        finally:
            if temporary and Path(temporary).exists():
                Path(temporary).unlink()
            lock.unlink()

def backup_bundle(store, destination):
    """An unencrypted, self-checking snapshot in a new directory, never the public tree."""
    root = private_path(destination)
    root.parent.mkdir(parents=True, exist_ok=True)
    root.mkdir(mode=0o700)  # Exclusive: existing user files are never replaced.
    try:
        snapshot = root / 'snapshot.sqlite3'
        store.export(snapshot)
        with sqlite3.connect(snapshot.as_uri()+'?mode=ro', uri=True) as db:
            validate_schema(db, full=True)
        manifest = {'format': 1, 'schema': SCHEMA, 'snapshot': snapshot.name, 'created_at': now(),
                    'sha256': file_sha(snapshot), 'bytes': snapshot.stat().st_size, 'encrypted': False}
        with (root / 'recovery.json').open('x', encoding='utf-8') as stream:
            os.chmod(stream.fileno(), 0o600)
            stream.write(canonical(manifest))
            stream.flush()
            os.fsync(stream.fileno())
        return {'exported': True, 'verified': True, 'sha256': manifest['sha256'], 'bytes': manifest['bytes'],
                'encrypted': False, 'durability': 'local snapshot only; external persistence requires a verified host receipt'}
    except Exception:
        # Only this newly-created directory is removed; never a pre-existing user directory.
        shutil.rmtree(root)
        raise

def person_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Z][A-Z0-9_-]{0,31}', value):
        raise Error('invalid stable person ID')
    return value

def expected_version(value):
    if type(value) is not int or value<0:
        raise Error('nonnegative expected version required')
    return value

def validate_schema(db, full=False):
    global _SCHEMA_SIGNATURE
    if db.execute('PRAGMA user_version').fetchone()[0]!=SCHEMA:
        raise Error('unsupported schema; migrate explicitly')
    objects=db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall()
    def signature(rows):return sorted((r[0],r[1],' '.join((r[2] or '').split()).casefold()) for r in rows)
    if _SCHEMA_SIGNATURE is None:
        reference=object.__new__(Store)
        reference.db=sqlite3.connect(':memory:',isolation_level=None)
        try:
            reference._schema()
            _SCHEMA_SIGNATURE=signature(reference.db.execute("SELECT type,name,sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'").fetchall())
        finally:reference.db.close()
    if signature(objects)!=_SCHEMA_SIGNATURE:raise Error('schema constraints or indexes differ from this version')
    tables={r[1] for r in objects if r[0]=='table'}
    if tables!=set(REQUIRED) or any(r[0] in {'trigger','view'} or 'VIRTUAL' in (r[2] or '').upper() for r in objects):
        raise Error('invalid private schema')
    for table,columns in REQUIRED.items():
        if {r[1] for r in db.execute('PRAGMA table_info('+table+')')}!=columns:
            raise Error('incompatible private schema')
    if full and (db.execute('PRAGMA integrity_check').fetchone()[0]!='ok' or db.execute('PRAGMA foreign_key_check').fetchall()):
        raise Error('private integrity check failed')
    if full:
        active=db.execute('SELECT version FROM core_active WHERE singleton=1').fetchall()
        if len(active)!=1 or not db.execute('SELECT 1 FROM core_versions WHERE version=?',(active[0][0],)).fetchone():
            raise Error('core initialization incomplete')
        expected_fks={'aliases':{'people'},'sources':{'people'},'claims':{'people'},'claim_sources':{'claims','sources'},'core_rules':{'core_versions'}}
        for table,parents in expected_fks.items():
            if {r[2] for r in db.execute('PRAGMA foreign_key_list('+table+')')}!=parents:
                raise Error('foreign key schema invalid')

def text(value, limit=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > limit or '\x00' in value:
        raise Error('invalid or excessive text')
    return value.strip()

def validate_configuration(data):
    if not isinstance(data,dict) or set(data)-CONFIG_KEYS:raise Error('unsupported configuration field')
    for key,value in data.items():
        if key.startswith('extension_'):
            if type(value) is not bool:raise Error('extension flags require booleans')
        elif key=='max_chars':
            if type(value) is not int or not 1<=value<=2000:raise Error('invalid reply length')
        elif key=='avoid':
            if not isinstance(value,list) or len(value)>32 or any(not isinstance(x,str) or not x or len(x)>80 for x in value):raise Error('invalid avoid list')
        else:text(value,500)
    if data.get('extension_auto_lowrisk') is True:raise Error('automatic activation is not available; confirm each reviewed branch')
    if 'output_mode' in data and data['output_mode'] not in {'reply','analysis','review'}:raise Error('invalid output mode')
    return data

class Store:
    def __init__(self, root, create=False):
        self.root = private_path(root)
        self.path = self.root / 'social-reply.sqlite3'
        self.reads = 0
        self.bytes_loaded = 0
        if create:
            self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not create and not self.path.is_file():
            raise Error('private storage unavailable; nothing was loaded')
        if self.path.is_symlink():
            raise Error('symlink database rejected')
        existed=self.path.exists()
        try:
            self.db = sqlite3.connect(self.path, timeout=2, isolation_level=None)
            self.db.row_factory = sqlite3.Row
            if existed:validate_schema(self.db)
            self.db.execute('PRAGMA foreign_keys=ON')
            self.db.execute('PRAGMA secure_delete=ON')
            self.db.execute('PRAGMA journal_mode=DELETE')
            if create and not existed:
                self._schema()
                os.chmod(self.path, 0o600)
            version = self.db.execute('PRAGMA user_version').fetchone()[0]
            if version != SCHEMA:
                raise Error('unsupported schema; restore or migrate explicitly')
            self.db.set_trace_callback(self._trace)
        except sqlite3.DatabaseError as exc:
            if hasattr(self,'db'):self.db.close()
            raise Error('storage is corrupt or inaccessible; restore an explicit export') from exc
        except Error:
            if hasattr(self,'db'):self.db.close()
            raise

    def _schema(self):
        self.db.executescript('''
        BEGIN IMMEDIATE;
        CREATE TABLE IF NOT EXISTS people(id TEXT PRIMARY KEY, aliases TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS aliases(alias TEXT NOT NULL, person_id TEXT REFERENCES people(id) ON DELETE CASCADE,
          PRIMARY KEY(alias,person_id));
        CREATE TABLE IF NOT EXISTS tombstones(id TEXT PRIMARY KEY, deleted_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS revisions(scope TEXT PRIMARY KEY, value INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS sources(id TEXT PRIMARY KEY, person_id TEXT REFERENCES people(id) ON DELETE CASCADE,
          kind TEXT NOT NULL, content TEXT NOT NULL, digest TEXT NOT NULL, event_group TEXT NOT NULL,
          sent INTEGER NOT NULL, created_at TEXT NOT NULL);
        CREATE UNIQUE INDEX IF NOT EXISTS source_dedup ON sources(COALESCE(person_id,''),kind,digest);
        CREATE INDEX IF NOT EXISTS source_person ON sources(person_id);
        CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY, person_id TEXT NOT NULL REFERENCES people(id) ON DELETE CASCADE,
          content TEXT NOT NULL, evidence_type TEXT NOT NULL, confidence TEXT NOT NULL, status TEXT NOT NULL,
          reason TEXT NOT NULL, updated_at TEXT NOT NULL, UNIQUE(person_id,content));
        CREATE INDEX IF NOT EXISTS claim_person ON claims(person_id,status);
        CREATE TABLE IF NOT EXISTS claim_sources(claim_id TEXT REFERENCES claims(id) ON DELETE CASCADE,
          source_id TEXT REFERENCES sources(id) ON DELETE CASCADE, PRIMARY KEY(claim_id,source_id));
        CREATE INDEX IF NOT EXISTS by_source ON claim_sources(source_id);
        CREATE TABLE IF NOT EXISTS config(scope TEXT PRIMARY KEY, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS core_versions(version INTEGER PRIMARY KEY, reason TEXT NOT NULL, created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS core_rules(version INTEGER REFERENCES core_versions(version) ON DELETE CASCADE,
          id TEXT NOT NULL, topic TEXT NOT NULL, data TEXT NOT NULL, PRIMARY KEY(version,id));
        CREATE INDEX IF NOT EXISTS core_topic ON core_rules(version,topic,id);
        CREATE TABLE IF NOT EXISTS core_active(singleton INTEGER PRIMARY KEY CHECK(singleton=1), version INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS theory_proposals(id TEXT PRIMARY KEY, data TEXT NOT NULL, state TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS extensions(id TEXT PRIMARY KEY, scope TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL,
          state TEXT NOT NULL DEFAULT 'proposed');
        CREATE INDEX IF NOT EXISTS extension_scope ON extensions(scope,state);
        CREATE TABLE IF NOT EXISTS extension_history(id TEXT NOT NULL, version INTEGER NOT NULL, scope TEXT NOT NULL,
          data TEXT NOT NULL, PRIMARY KEY(id,version));
        CREATE TABLE IF NOT EXISTS cache(person_id TEXT NOT NULL, topic TEXT NOT NULL, fingerprint TEXT NOT NULL,
          payload TEXT NOT NULL, PRIMARY KEY(person_id,topic));
        PRAGMA user_version=2;
        COMMIT;
        ''')

    def close(self):
        self.db.close()

    def _trace(self, statement):
        if statement.lstrip().upper().startswith(('SELECT','WITH')):
            self.reads += 1

    def query(self, sql, args=()):
        try:
            rows = self.db.execute(sql, args).fetchall()
        except sqlite3.DatabaseError as exc:
            raise Error('private read failed') from exc
        self.bytes_loaded += sum(len(canonical(dict(r)).encode('utf-8')) for r in rows)
        return [dict(row) for row in rows]

    def revision(self, scope):
        row = self.db.execute('SELECT value FROM revisions WHERE scope=?', (scope,)).fetchone()
        return row[0] if row else 0

    @contextlib.contextmanager
    def write(self, scope, expected=None):
        try:
            self.db.execute('BEGIN IMMEDIATE')
            if expected is not None and self.revision(scope) != expected:
                raise Conflict('version changed; reread and merge')
            yield self.db
            self.db.execute('INSERT INTO revisions VALUES(?,1) ON CONFLICT(scope) DO UPDATE SET value=value+1', (scope,))
            affected = scope.split(':', 1)[-1]
            if scope.startswith(('person:','config:','extension:')) and affected != 'global':
                self.db.execute('DELETE FROM cache WHERE person_id=?', (affected,))
            elif scope in {'core','config:global','extension:global'}:
                self.db.execute('DELETE FROM cache')
            if affected == 'SELF':
                self.db.execute('DELETE FROM cache')
            self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            raise

    def get_config(self, scope):
        rows = self.query('SELECT data FROM config WHERE scope=?', (scope,))
        return json.loads(rows[0]['data']) if rows else {}

    def configure(self, scope, data, expected):
        expected_version(expected)
        validate_configuration(data)
        if scope != 'global':
            person_id(scope)
            if not self.db.execute('SELECT 1 FROM people WHERE id=?', (scope,)).fetchone():
                raise Error('unknown configuration person')
        if not isinstance(data, dict) or set(data) - CONFIG_KEYS:
            raise Error('unsupported configuration field')
        for key, value in data.items():
            if key.startswith('extension_') and type(value) is not bool:
                raise Error('extension flags require booleans')
            if key == 'max_chars' and (type(value) is not int or not 1 <= value <= 2000):
                raise Error('invalid reply length')
            if key == 'avoid' and (not isinstance(value, list) or len(value) > 32 or any(not isinstance(x,str) or len(x)>80 for x in value)):
                raise Error('invalid avoid list')
            if key not in {'avoid','max_chars'} and not key.startswith('extension_'):
                text(value, 500)
        if data.get('extension_auto_lowrisk') is True:
            raise Error('automatic activation is not available; confirm each reviewed branch')
        revision_scope = 'config:' + scope
        with self.write(revision_scope, expected) as db:
            if scope!='global' and not db.execute('SELECT 1 FROM people WHERE id=?',(scope,)).fetchone():
                raise Error('configuration person removed')
            row = db.execute('SELECT data FROM config WHERE scope=?', (scope,)).fetchone()
            merged = json.loads(row[0]) if row else {}
            merged.update(data)
            db.execute('INSERT INTO config VALUES(?,?) ON CONFLICT(scope) DO UPDATE SET data=excluded.data', (scope, canonical(merged)))
        return {'revision': self.revision(revision_scope), 'config': merged}

    def export(self, destination):
        target = private_path(destination)
        if target.exists():
            raise Error('export target exists; choose a new filename')
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, temporary = tempfile.mkstemp(prefix='.sr-export-', dir=target.parent)
        os.close(handle)
        try:
            with sqlite3.connect(temporary) as copy:
                self.db.backup(copy)
                if copy.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
                    raise Error('export integrity failure')
            os.chmod(temporary, 0o600)
            os.link(temporary, target)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {'exported': True, 'sha256': file_sha(target), 'bytes': target.stat().st_size,
                'scope': 'all effective private data and retained local histories; unencrypted'}

def safe_extract(archive, destination, max_total=4*1024**3, max_file=256*1024**2, max_entries=2048, max_ratio=200):
    target = private_path(destination)
    if target.exists():
        raise Error('extraction destination must not exist')
    target.parent.mkdir(parents=True, exist_ok=True)
    seen, total = set(), 0
    with zipfile.ZipFile(archive) as z:
        entries = z.infolist()
        if len(entries) > max_entries:
            raise Error('archive entry limit exceeded')
        for item in entries:
            name = item.filename
            path = PurePosixPath(name)
            mode = item.external_attr >> 16
            if (not name or name.startswith('/') or '\\' in name or ':' in name or
                any(ord(c)<32 or unicodedata.category(c)=='Cf' for c in name) or
                any(p in {'..','.'} or p.endswith((' ','.')) or re.fullmatch(r'(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?',p) for p in path.parts) or
                (stat.S_IFMT(mode) not in {0,stat.S_IFREG,stat.S_IFDIR}) or item.flag_bits & 1):
                raise Error('unsafe archive member')
            key = unicodedata.normalize('NFC', name.rstrip('/')).casefold()
            if key in seen:
                raise Error('duplicate archive destination')
            seen.add(key)
            total += item.file_size
            if item.file_size > max_file or total > max_total or item.file_size/max(1,item.compress_size) > max_ratio:
                raise Error('archive expansion limit exceeded')
        staging = Path(tempfile.mkdtemp(prefix='.sr-extract-', dir=target.parent))
        try:
            actual = 0
            for item in entries:
                out = staging.joinpath(*PurePosixPath(item.filename).parts)
                if item.is_dir():
                    out.mkdir(parents=True, exist_ok=True)
                    continue
                out.parent.mkdir(parents=True, exist_ok=True)
                written = 0
                with z.open(item) as inp, out.open('xb') as stream:
                    for block in iter(lambda: inp.read(1024*1024), b''):
                        actual += len(block)
                        written += len(block)
                        if written > max_file or actual > max_total:
                            raise Error('stream expansion limit exceeded')
                        stream.write(block)
                os.chmod(out, 0o600)
            os.replace(staging, target)
        finally:
            if staging.exists():
                shutil.rmtree(staging)
    return {'entries': len(entries), 'uncompressed_bytes': total}
