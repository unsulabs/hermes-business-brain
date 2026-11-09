"""Rebuildable SQLite FTS. Current verified sources, never cached rights, govern reads."""
import re
import sqlite3

from .transcripciones_custodia import load_catalog
from .transcripciones_lectura import guarded_read
from .transcripciones_modelo import (
    ModelError,
    atomic_write,
    bank_lock,
    json_bytes,
    load_json,
    read_bytes,
    safe_path,
    sha256_bytes,
)
from .transcripciones_permisos import authorized, permission_snapshot


def _source(bank, tr_id, version_id):
    rows = load_catalog(bank)  # validates custody journals and exact original bytes
    row = next((r for r in rows if r['tr_id'] == tr_id and version_id in r['version_ids']), None)
    if row is None:
        raise ModelError('SOURCE_UNKNOWN')
    original = load_json(safe_path(bank, f'versiones/{version_id}.json'))
    data = read_bytes(bank, original['blob_path'])
    if sha256_bytes(data) != original['sha256']:
        raise ModelError('HASH_MISMATCH')
    return row, original, data


def watermark(bank):
    return sha256_bytes(json_bytes({'catalog': load_catalog(bank), 'permissions': permission_snapshot(bank)}))


def _database():
    db = sqlite3.connect(':memory:')
    try:
        db.execute('CREATE VIRTUAL TABLE passages USING fts5(id UNINDEXED, text)')
        mode = 'fts5'
    except sqlite3.OperationalError:
        db.execute('CREATE TABLE passages(id TEXT, text TEXT)')
        mode = 'literal_fallback'
    return db, mode


def rebuild_index(bank, snapshot=None, *, company=None, audience=None, purpose='local_analysis', commit=False):
    """Private derivative, never authority; preview has no writes."""
    def build():
        if (company is None)!=(audience is None) or company=='' or audience=='':
            raise ModelError('ACCESS_CONTEXT_REQUIRED')
        mark = watermark(bank)
        if snapshot is not None and snapshot != mark:
            raise ModelError('SNAPSHOT_CHANGED')
        db, mode = _database()
        count = 0
        try:
            for row in load_catalog(bank):
                for vid in row['version_ids']:
                    if company is not None and not authorized(bank,row['tr_id'],vid,company,audience,purpose):
                        continue
                    _, original, data = _source(bank, row['tr_id'], vid)
                    # Index permission-filtered content only; no inferred custody license.
                    from .transcripciones_permisos import effective_decisions
                    if not any(d['tr_id']==row['tr_id'] and d['version_id']==vid and d['action']=='grant'
                               and d['purpose'] in ('local_analysis','internal_query') for d in effective_decisions(bank)):
                        continue
                    try:
                        text = data.decode('utf-8')
                    except UnicodeDecodeError:
                        continue
                    db.execute('INSERT INTO passages VALUES (?,?)', (vid,text))
                    count += 1
            db.execute('CREATE TABLE metadata(watermark TEXT, mode TEXT, scope TEXT)')
            scope={'company':company,'audience':audience,'purpose':purpose}
            db.execute('INSERT INTO metadata VALUES (?,?,?)', (mark,mode,json_bytes(scope).decode()))
            db.commit()
            if watermark(bank) != mark:
                raise ModelError('SNAPSHOT_CHANGED')
            if commit:
                atomic_write(bank, 'index/search.sqlite', db.serialize(), immutable=False)
            return {'watermark':mark,'mode':mode,'scope':scope,'indexed_versions':count,'committed':commit}
        finally:
            db.close()
    if commit:
        with bank_lock(bank):
            return build()
    return build()


rebuild = rebuild_index


def search_request(query, access_context):
    """Annex adapter; access_context requires bank, company, audience, purpose."""
    return search(access_context['bank'],query,company=access_context['company'],
                  audience=access_context['audience'],purpose=access_context['purpose'],
                  limit=access_context.get('limit',10))


@guarded_read
def search(bank, query, *, company, audience, purpose='internal_query', limit=10, candidate_filter=None):
    """Fresh authorized FTS corpus prevents both stale text and ranking leakage.

    The persisted index is a rebuildable artifact, not a serving authority.
    v1 intentionally rebuilds the scoped in-memory search table per request.
    """
    if not isinstance(query,str) or not 2 <= len(query.strip()) <= 220 or type(limit) is not int or not 1 <= limit <= 40:
        raise ModelError('QUERY_INVALID')
    if not company or not audience:
        raise ModelError('ACCESS_CONTEXT_REQUIRED')
    start = watermark(bank)
    db, mode = _database()
    records, gaps = {}, []
    try:
        from .transcripciones_segmentacion import segment_text
        for row in load_catalog(bank):
            if row['states']['editorial'] in ('rechazado','legado_rechazado'):
                continue
            for vid in row['version_ids']:
                if not authorized(bank,row['tr_id'],vid,company,audience,purpose):
                    continue
                _, original, data = _source(bank,row['tr_id'],vid)
                try:
                    data.decode('utf-8')
                except UnicodeDecodeError:
                    gaps.append('AUTHORIZED_SOURCE_ENCODING_UNSUPPORTED')
                    continue
                for segment in segment_text(data,row['tr_id'],vid):
                    a,b = segment['core_start'],segment['core_end']
                    sid = segment['segment_id']
                    text = data[a:b].decode('utf-8')
                    record = {'tr_id':row['tr_id'],'version_id':vid,'sha256':original['sha256'],
                        'segment_id':sid,'start':a,'end':b,'text':text,'data_not_instructions':True,
                        'completeness':row['states']['completeness']}
                    projected=candidate_filter(record) if candidate_filter is not None else [record]
                    for selected in projected:
                        key=f"{sid}:{selected['start']}:{selected['end']}"
                        if key not in records:
                            records[key]=selected
                            db.execute('INSERT INTO passages VALUES (?,?)',(key,selected['text']))
        tokens = re.findall(r'\w+',query,flags=re.UNICODE)
        if not tokens:
            raise ModelError('QUERY_INVALID')
        if mode == 'fts5':
            expression = ' AND '.join('"'+t.replace('"','""')+'"' for t in tokens)
            hits = db.execute('SELECT id FROM passages WHERE passages MATCH ? ORDER BY id LIMIT ?', (expression,limit)).fetchall()
        else:
            hits = [(sid,) for sid,r in sorted(records.items()) if query.casefold() in r['text'].casefold()][:limit]
        candidates = [records[h[0]] for h in hits]
        if watermark(bank) != start:
            raise ModelError('SNAPSHOT_CHANGED')
        return {'candidates':candidates,'watermark':start,'mode':'fresh_scoped_'+mode,'gaps':gaps,
                'semantic_answer_generated':False,'coverage':'directed_search_not_exhaustive'}
    finally:
        db.close()
