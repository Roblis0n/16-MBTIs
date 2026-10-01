"""Opt-in POSIX dirfd storage. Unsupported platforms fail closed.

No replace/overwrite primitive is used. Publication is an atomic hard-link from
an fsynced same-directory temporary file. Permissions are owner-only.
"""
import hashlib
import os
import re
import secrets
import stat
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from .contracts import canonical, strict_loads, MAX_BYTES
from .errors import fail, MindsError
from .render import render, public_payload
from .tool_policy import request_object

RUN_RE=re.compile(r'^\d{8}T\d{6}Z-[a-f0-9]{16}$')
RESERVED=re.compile(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)',re.I)

def _parts(relative):
    if not isinstance(relative,str) or not relative or '\\' in relative or ':' in relative or relative.startswith('/'):
        fail('E_PATH_OUTSIDE_ROOT','Only a relative authorized path is supported.')
    parts=relative.split('/')
    if any(p in ('','.', '..') or p.endswith((' ','.')) or RESERVED.match(p) or '\x00' in p or len(p.encode('utf-8'))>240 for p in parts):
        fail('E_PATH_OUTSIDE_ROOT','Unsafe or unsupported path component.')
    if len(relative.encode('utf-8'))>3000: fail('E_PATH_OUTSIDE_ROOT','Path exceeds the supported length.')
    return parts

@contextmanager
def _root(root):
    if os.name!='posix' or not hasattr(os,'O_NOFOLLOW'): fail('E_CAPABILITY','Secure storage requires POSIX dirfd and O_NOFOLLOW support.')
    if not isinstance(root,(str,Path)) or not Path(root).is_absolute(): fail('E_PATH_OUTSIDE_ROOT','An explicit absolute authorized root is required.')
    p=Path(root)
    if '..' in p.parts: fail('E_PATH_OUTSIDE_ROOT','Root cannot contain traversal.')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY)
    try:
        for part in p.parts[1:]:
            n=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd); os.close(fd); fd=n
        yield fd
    except OSError: fail('E_PATH_OUTSIDE_ROOT','Root or parent is unavailable or contains a link.',side_effect_status='unknown')
    finally: os.close(fd)

@contextmanager
def _parent(root,relative,create=False):
    parts=_parts(relative)
    with _root(root) as base:
        fd=os.dup(base)
        try:
            for part in parts[:-1]:
                if create:
                    try: os.mkdir(part,0o700,dir_fd=fd)
                    except FileExistsError: pass
                n=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd); os.close(fd); fd=n
            yield fd,parts[-1]
        except OSError: fail('E_PATH_OUTSIDE_ROOT','A parent path is unavailable or unsafe.',side_effect_status='unknown')
        finally: os.close(fd)

def resolve_authorized_path(root,relative):
    with _parent(root,relative) as (fd,name):
        try:
            s=os.stat(name,dir_fd=fd,follow_symlinks=False)
            if stat.S_ISLNK(s.st_mode): fail('E_PATH_OUTSIDE_ROOT','Links are not allowed.')
        except FileNotFoundError: pass
    return str(Path(root)/relative)

def _consent(persist):
    if type(persist) is not bool: fail('E_SCHEMA','Persistence must be a boolean.')
    if persist is not True: fail('E_PERMISSION','Persistence requires explicit opt-in; no run directory was created.')

def _check_ignore(root):
    # Check literal project ignore plus tracked files. Never modify git configuration.
    with _parent(root,'.gitignore') as (fd,name):
        try:
            f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
            try:
                raw=os.read(f,MAX_BYTES+1)
                if len(raw)>MAX_BYTES: fail('E_SCHEMA','Project ignore file exceeds the supported size.')
                text=raw.decode('utf-8')
            finally: os.close(f)
        except (OSError,UnicodeError): fail('E_PERMISSION','Review and authorize project .gitignore coverage before saving.')
    if not any(x.strip() in ('.16minds/','.16minds/runs/','/.16minds/','/.16minds/runs/') for x in text.splitlines()) or any(x.strip().startswith('!') for x in text.splitlines()):
        fail('E_PERMISSION','Project ignore must cover .16minds/runs without ambiguous negations.')
    if (Path(root)/'.git').exists():
        try:
            r=subprocess.run(['git','-C',str(root),'ls-files','-z','--','.16minds/runs'],capture_output=True,timeout=5,check=False)
        except (OSError,subprocess.TimeoutExpired): fail('E_PERMISSION','Cannot verify tracked-log exposure.')
        if r.returncode or r.stdout: fail('E_PERMISSION','Run files may already be tracked; ignore rules do not remove history.')

def create_run_dir(root,persist=False):
    _consent(persist); _check_ignore(root)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ-')+secrets.token_hex(8)
    relative='.16minds/runs/'+run_id
    with _parent(root,relative,create=True) as (fd,name):
        try: os.mkdir(name,0o700,dir_fd=fd); os.fsync(fd)
        except FileExistsError: fail('E_EXISTS','Unique run directory already exists; retry with a new run ID.')
    return run_id

def write_no_clobber(root,relative,data,persist=False):
    _consent(persist)
    if not isinstance(data,(str,bytes)): fail('E_SCHEMA','Write payload must be UTF-8 text or bytes.')
    raw=data.encode('utf-8') if isinstance(data,str) else data
    if len(raw)>MAX_BYTES: fail('E_SCHEMA','Stored record exceeds 1 MiB.')
    with _parent(root,relative) as (fd,name):
        temp='.tmp-'+secrets.token_hex(12)
        try: lock=os.open('.minds-lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=fd)
        except FileExistsError: fail('E_CONCURRENT_MODIFICATION','Another writer or deletion owns this run.')
        os.close(lock)
        out=None
        try:
            out=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600,dir_fd=fd)
            with os.fdopen(out,'wb') as f: out=None; f.write(raw); f.flush(); os.fsync(f.fileno())
            try: os.link(temp,name,src_dir_fd=fd,dst_dir_fd=fd,follow_symlinks=False)
            except FileExistsError: fail('E_EXISTS','Destination exists; original bytes are unchanged.')
            os.fsync(fd)
        finally:
            if out is not None: os.close(out)
            try: os.unlink(temp,dir_fd=fd)
            except FileNotFoundError: pass
            os.unlink('.minds-lock',dir_fd=fd)
    return {'path':relative,'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def read_record(root,relative):
    with _parent(root,relative) as (fd,name):
        f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            s=os.fstat(f)
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1: fail('E_PATH_OUTSIDE_ROOT','Record must be a regular non-linked file.')
            raw=os.read(f,MAX_BYTES+1)
            if len(raw)>MAX_BYTES: fail('E_SCHEMA','Record exceeds size limit.')
            return strict_loads(raw.decode('utf-8'))
        finally: os.close(f)

def export_run(root,relative,payload,persist=False,format='json'):
    _consent(persist)
    text=render(payload,format)
    result=write_no_clobber(root,relative,text,persist=True)
    result.update(source_sha256=hashlib.sha256(canonical(payload).encode()).hexdigest(),display_escaped=public_payload(payload)!=payload,canonical_body=False)
    return result

def _run_path(run_id):
    if not isinstance(run_id,str) or not RUN_RE.fullmatch(run_id): fail('E_PATH_OUTSIDE_ROOT','An exact generated run ID is required.')
    return '.16minds/runs/'+run_id

def _manifest(fd):
    files=[]
    for name in sorted(os.listdir(fd)):
        if name=='.minds-lock': continue
        _parts(name)
        f=os.open(name,os.O_RDONLY|os.O_NOFOLLOW,dir_fd=fd)
        try:
            st=os.fstat(f)
            if not stat.S_ISREG(st.st_mode) or st.st_nlink!=1: fail('E_PATH_OUTSIDE_ROOT','Delete preview supports only regular non-linked run files.')
            if st.st_size>MAX_BYTES: fail('E_SCHEMA','Run record exceeds size limit.')
            raw=os.read(f,MAX_BYTES+1)
            files.append({'name':name,'sha256':hashlib.sha256(raw).hexdigest(),'inode':st.st_ino,'bytes':len(raw)})
        finally: os.close(f)
    return files

def delete_selected_run(root,run_id,confirmed=False,preview_digest=None):
    if type(confirmed) is not bool: fail('E_SCHEMA','Deletion confirmation must be boolean.')
    relative=_run_path(run_id)
    with _parent(root,relative) as (parent,name):
        fd=os.open(name,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=parent)
        lock_owned=False; deleted=[]
        try:
            try: lock=os.open('.minds-lock',os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600,dir_fd=fd)
            except FileExistsError: fail('E_CONCURRENT_MODIFICATION','Another write or deletion is active.')
            os.close(lock); lock_owned=True
            files=_manifest(fd)
            digest=hashlib.sha256(canonical({'run_id':run_id,'files':files}).encode()).hexdigest()
            preview={'run_id':run_id,'files':files,'preview_digest':digest,'deletion_limits':'Does not delete host history, Git history, backups, or securely erase disk.'}
            if not confirmed: return {'status':'preview',**preview}
            if preview_digest!=digest: fail('E_CONCURRENT_MODIFICATION','Confirmed preview does not match the exact current run.')
            if os.stat(name,dir_fd=parent,follow_symlinks=False).st_ino!=os.fstat(fd).st_ino:
                fail('E_CONCURRENT_MODIFICATION','Run directory changed after preview.')
            # Recheck every hash while holding the same lock used by all plugin writers.
            if _manifest(fd)!=files: fail('E_CONCURRENT_MODIFICATION','Run content changed after preview.')
            for item in files:
                s=os.stat(item['name'],dir_fd=fd,follow_symlinks=False)
                if s.st_ino!=item['inode'] or not stat.S_ISREG(s.st_mode):
                    if deleted: return {'status':'partial','deleted_files':deleted,'side_effect_status':'partial','reason':'concurrent_modification'}
                    fail('E_CONCURRENT_MODIFICATION','Run file changed during deletion.')
                os.unlink(item['name'],dir_fd=fd); deleted.append(item['name'])
        except OSError:
            if deleted: return {'status':'partial','deleted_files':deleted,'side_effect_status':'partial','reason':'filesystem_failure'}
            fail('E_PATH_OUTSIDE_ROOT','Run path is unavailable or unsafe.')
        finally:
            if lock_owned: os.unlink('.minds-lock',dir_fd=fd)
            os.close(fd)
        try: os.rmdir(name,dir_fd=parent)
        except OSError: return {'status':'partial','deleted_files':deleted,'side_effect_status':'partial','reason':'run_directory_not_empty'}
    return {'status':'deleted',**preview}

def dispatch(data):
    if not isinstance(data,dict): fail('E_SCHEMA','Expected storage request object.')
    action=data.get('action'); root=data.get('root')
    shapes={'create':({'action','root'},{'persist'}),'export':({'action','root','path','payload'},{'persist','format'}),'delete':({'action','root','run_id'},{'confirmed','preview_digest'})}
    if not isinstance(action,str): fail('E_SCHEMA','Action must be a string.')
    if action not in shapes: fail('E_SCHEMA','Unknown storage action.')
    request_object(data,*shapes[action],booleans={'persist','confirmed'})
    if action=='create': return {'status':'ok','run_id':create_run_dir(root,data.get('persist',False))}
    if action=='export': return {'status':'ok',**export_run(root,data.get('path'),data.get('payload'),data.get('persist',False),data.get('format','json'))}
    if action=='delete': return delete_selected_run(root,data.get('run_id'),data.get('confirmed',False),data.get('preview_digest'))
    fail('E_SCHEMA','Unknown storage action.')
