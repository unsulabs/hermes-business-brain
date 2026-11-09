"""Verifiable local operations for the Business Brain: business decisions are made by the agent with the person.

No function makes network calls, runs plugins, infers authority or changes official data.
"""
# ruff: noqa: FURB162, RUF059, UP017  (upstream-identical behavior: timezone.utc,
# the explicit 'Z'->'+00:00' normalization for pre-3.11 parsers, and the
# upstream unpack of read_note's triple are kept 1:1)
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import shutil
import sys
import unicodedata
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import yaml

from .lib_ce import (
    make_note,
    notes_in_vault,
    split_frontmatter,
    validate_tags,
    visible_filename,
)

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / 'modelo' / 'tipos_entidad.json'
ID_RE = re.compile(r'^[A-Za-z][A-Za-z0-9_-]{1,75}$')
SAFE_SOURCE_RE = re.compile(r'^F-[A-Za-z0-9_-]{2,60}$')


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_registry() -> dict:
    return {x['tipo']: x for x in json.loads(MODEL.read_text(encoding='utf-8'))['tipos']}


def safe_vault(path: Path) -> tuple[Path, dict]:
    path = path.expanduser().resolve()
    conf = path / '90_Sistema' / 'config_empresa.yaml'
    if not path.is_dir() or not conf.is_file():
        raise ValueError('Unrecognized vault: missing 90_Sistema/config_empresa.yaml')
    cfg = yaml.safe_load(conf.read_text(encoding='utf8'))
    if not isinstance(cfg, dict) or not cfg.get('company_id'):
        raise ValueError('Invalid company configuration')
    return path, cfg


def unique_path(vault: Path, dest: Path):
    # Deny symlink targets and symlink directories anywhere underneath vault.
    root = vault.resolve()
    if root not in dest.absolute().parents:
        raise ValueError('Destination outside the vault')
    rel = dest.absolute().relative_to(root)
    current = root
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError('Path contains a symbolic link: security rejection')
    if dest.exists():
        raise FileExistsError('The file already exists; do not overwrite: ' + str(dest))
    if dest.parent.exists() and any(p.name.casefold() == dest.name.casefold() for p in dest.parent.iterdir()):
        raise FileExistsError('Visible-name collision without case distinction: ' + str(dest))


def slugify(value: str) -> str:
    basic = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', basic).strip('-')[:55] or 'nota'


def valid_title(title: str) -> str:
    title = title.strip()
    if not title or len(title) > 180 or any(c in title for c in '\r\n\x00'):
        raise ValueError('Empty, too long, or forbidden-character title')
    return title


def index_ids(vault: Path) -> dict[str, Path]:
    out = {}
    for p in notes_in_vault(vault):
        props, _ = split_frontmatter(p.read_text(encoding='utf8'))
        nid = props.get('id')
        if nid:
            if nid in out:
                raise ValueError('Duplicate IDs in the vault: ' + str(nid))
            out[str(nid)] = p
    return out


def read_note(vault: Path, nid: str) -> tuple[Path, dict, str]:
    path = index_ids(vault).get(nid)
    if not path:
        raise ValueError(f'ID does not exist in the vault: {nid}')
    fm, body = split_frontmatter(path.read_text(encoding='utf8'))
    return path, fm, body


def local_sources(vault: Path, sources: list[str]) -> list[str]:
    resolved = []
    for sid in sources:
        if not SAFE_SOURCE_RE.fullmatch(sid):
            raise ValueError('Incorrect source ID: ' + sid)
        p, fm, _ = read_note(vault, sid)
        if fm.get('tipo') != 'fuente' or fm.get('sensibilidad') != 'interno':
            raise ValueError('Unknown or non-shareable source: ' + sid)
        resolved.append(f'[[{p.relative_to(vault).with_suffix("").as_posix()}]]')
    return sorted(set(resolved))


def create_ficha(vault: Path, tipo: str, title: str, *, resumen: str = '',
                 sources: list[str] | None = None, tags: list[str] | None = None,
                 content_file: Path | None = None) -> dict:
    vault, cfg = safe_vault(vault)
    reg = load_registry()
    if tipo not in reg or tipo == 'fuente':
        raise ValueError('Record type not allowed; sources require their specific registration. Valid: ' + ', '.join(sorted(x for x in reg if x != 'fuente')))
    title = valid_title(title)
    if len(resumen) > 7000:
        raise ValueError('Summary too long; attach a source and develop an appropriate document')
    r = reg[tipo]
    labels = validate_tags(tags)
    source_links = local_sources(vault, sources or [])
    nid = f'{r["prefijo"]}-{uuid4().hex[:12].upper()}'
    if nid in index_ids(vault):
        raise ValueError('Unexpected ID collision; retry')
    path = vault / r['carpeta'] / visible_filename(title)
    unique_path(vault, path)
    fm = {
        'id': nid, 'tipo': tipo, 'clase': tipo, 'empresa_id': cfg['company_id'],
        'estado_editorial': 'borrador', 'estado_conocimiento': 'pendiente',
        'vigencia': 'sin_verificar', 'sensibilidad': 'interno',
        'registrado_en': utcnow(), 'fuentes': source_links,
        **({'tags': labels} if labels else {}),
    }
    more = {
        'tarea': {'fecha_programada': '', 'fecha_limite': '', 'responsable': '', 'estado_tarea': 'por_hacer'},
        'proyecto': {'estado_proyecto': 'por_definir'},
        'oferta': {'precio_sistema_fuente': '', 'moneda': 'por_definir', 'impuestos': 'por_verificar'},
        'decision': {'tema_autoridad': '', 'ambito_autoridad': '', 'decisor': '', 'fecha_efectiva': ''},
    }.get(tipo, {})
    fm.update(more)
    sections = '\n\n'.join(f'### {s}\n\n_To be developed with sources or expert judgment._' for s in r['contenido_minimo'])
    source_txt = ', '.join(source_links) if source_links else 'None verified yet'
    body = (f'# {title}\n\n> **NON-AUTHORITATIVE DRAFT.** Type: `{tipo}`. It is not approval, contract, payment or policy.\n\n'
            f'**Represents:** {r["representa"]}\n\n**Do not confuse with:** {r["no_confundir"]}\n\n'
            f'## Initial context provided\n\n{resumen or "Pending documentation with the owning person."}\n\n'
            f'## Guided development\n\n{sections}\n\n'
            f'## Relations to verify\n\nCandidates: {", ".join(r["relaciones_candidatas"])}. '
            'Do not add links without confirming their type and scope.\n\n'
            f'## Sources, authority and open questions\n\n- Declared sources: {source_txt}\n'
            f'- Verification question: {r["pregunta_de_prueba"]}\n'
            '- Who approves the content: pending\n- What we do not know: pending\n')
    if content_file is not None:
        from .documentos import _read_input
        from .validar_boveda import validate
        prior = validate(vault)
        if prior["errores"]:
            raise ValueError("Vault has prior errors; do not write developed notes")
        developed, _ = _read_input(content_file, vault)
        body = developed
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf8', newline='\n') as f:
        f.write(make_note(fm, body))
    if content_file is not None:
        try:
            result = validate(vault)
            if result["errores"]:
                raise ValueError("Note failed validation: "+"; ".join(result["errores"][:3]))
        except Exception:
            path.unlink()
            raise
    return {'id': nid, 'tipo': tipo, 'ruta': str(path), 'aprobado': False,
            'fuentes': sources or [], 'nota_desarrollada': content_file is not None}


def create_source(vault: Path, sid: str, title: str, locator: str, kind: str, *, read_status: str='no_verificada', event_date: str='', permission: str='interno') -> dict:
    vault, cfg = safe_vault(vault)
    if not SAFE_SOURCE_RE.fullmatch(sid):
        raise ValueError('Invalid F-... source ID')
    title = valid_title(title)
    locator = locator.strip()
    if not locator or len(locator)>3000 or '\n' in locator or '\r' in locator:
        raise ValueError('A valid origin locator is required, without line breaks')
    if permission != 'interno':
        raise ValueError('Confidential/restricted sources are not admitted in the MVP vault without ACL')
    if read_status not in ('no_verificada','leida_parcial','leida_completa'):
        raise ValueError('Invalid reading status')
    if event_date:
        date.fromisoformat(event_date)
    if sid in index_ids(vault):
        raise FileExistsError('The source already exists; use a reference, do not duplicate: '+sid)
    p = vault / '50_Fuentes' / visible_filename(title)
    unique_path(vault,p)
    fm = {'id':sid,'tipo':'fuente','clase':'fuente','empresa_id':cfg['company_id'],
          'clase_fuente':kind,'lectura':read_status,'sensibilidad':permission,
          'registrado_en':utcnow(),'fecha_evento':event_date,'estado_editorial':'borrador'}
    body = (f'# {title}\n\n**Original reference:** `{locator.replace("`", "")}`\n\n'
            '**Supported claims:** to be documented after full/relevant reading.\n\n'
            '**Limits and usage permissions:** pending explicit authorization or verification.\n\n'
            '> Only provenance is recorded; the original document is not copied.\n')
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        f.write(make_note(fm,body))
    return {'id':sid,'ruta':str(p),'estado_lectura':read_status,'copia_original':False}


def propose_change(vault: Path, nid: str, reason: str, candidate: str, *, author: str='agente') -> dict:
    vault, cfg = safe_vault(vault)
    p, fm, text = read_note(vault,nid)
    if fm.get('sensibilidad','interno') != 'interno':
        raise ValueError('Protected material; it requires external access controls')
    reason, candidate = valid_title(reason), candidate.strip()
    if not candidate or len(candidate)>30000:
        raise ValueError('Empty or excessive candidate (>30 k characters)')
    raw_hash=hashlib.sha256(p.read_bytes()).hexdigest()
    pid=f'PROP-{uuid4().hex[:12].upper()}'
    out=vault/'90_Sistema'/'Bandeja_Propuestas'/f'{pid}.md'
    unique_path(vault,out)
    front={'id':pid,'tipo':'propuesta_de_cambio','clase':'control','empresa_id':cfg['company_id'],
           'estado_editorial':'borrador','estado_conocimiento':'propuesta','vigencia':'sin_verificar',
           'sensibilidad':'interno','objetivo_id':nid,'huella_objetivo':raw_hash,'registrado_en':utcnow()}
    quoted='\n'.join('> '+line for line in candidate.splitlines())
    body=(f'# Proposal for [[{p.relative_to(vault).with_suffix("").as_posix()}]]\n\n'
          f'- **Declared reason:** {reason}\n- **Proposal author:** {author}\n'
          f'- **SHA-256 fingerprint of the original note:** `{raw_hash}`\n'
          '- **Status:** pending human review and verification against sources/authority.\n\n'
          '## Candidate change (NOT incorporated)\n\n' + quoted + '\n\n'
          '## Checks before any approval\n\n'
          '- [ ] Contrast claims with relevant sources and permissions\n'
          '- [ ] Review scope, extent, author and validity\n'
          '- [ ] Review affected derivatives and conflicts\n'
          '- [ ] Obtain approval from the authorized decision-maker\n'
          '- [ ] Re-validate the fingerprint before writing, archive the previous version, re-validate when finished\n')
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open('x',encoding='utf8', newline='\n') as f: f.write(make_note(front,body))
    return {'propuesta':pid,'archivo':str(out),'modificacion_del_objetivo':False,'objetivo_sha256':raw_hash}


def save_continuity(vault: Path, *, summary: str, next_step: str, reviewer: str='por_validar') -> dict:
    vault,cfg=safe_vault(vault)
    if not summary.strip() or not next_step.strip():
        raise ValueError('Useful continuity requires concrete summary and next step')
    if len(summary)+len(next_step)>16000:
        raise ValueError('Summary too long; use links to documents')
    sid='SES-'+uuid4().hex[:12].upper()
    subject=summary.strip().splitlines()[0].strip(' #*-')[:80]
    target=vault/'90_Sistema'/'Continuidad'/visible_filename(
        datetime.now(timezone.utc).date().isoformat()+' - '+subject)
    unique_path(vault,target)
    fm={'id':sid,'tipo':'continuidad','empresa_id':cfg['company_id'],'estado_editorial':'borrador',
        'sensibilidad':'interno','registrado_en':utcnow(),'revisado_por':reviewer}
    text=(f'# Continuity: {subject}\n\n## Session outcome\n\n{summary.strip()}\n\n'
          f'## Next step\n\n{next_step.strip()}\n\n'
          '> This summary is a trail to recover sources; it is not authority over unverified facts.\n')
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('x',encoding='utf8', newline='\n') as f: f.write(make_note(fm,text))
    return {'id':sid,'ruta':str(target),'revisado_por':reviewer}


def summary(vault: Path) -> dict:
    """Owner-oriented state: counting infrastructure is NOT creating a business.

    Keeps the legacy keys (total_notas/por_tipo/editorial/conocimiento) for
    compatibility; adds an inventory of layers and business documents.
    """
    vault,cfg=safe_vault(vault)
    counter=Counter(); editorial=Counter(); knowledge=Counter()
    layers=Counter()
    doc_classes=Counter(); doc_statuses=Counter(); source_reads=Counter()
    docs=[]
    system_types={'control','mapa','sistema'}
    registry=set(load_registry())
    work_types={'continuidad','registro_descubrimiento','propuesta_de_cambio'}
    for p in notes_in_vault(vault):
        fm,_=split_frontmatter(p.read_text(encoding='utf8'))
        typ=str(fm.get('tipo') or 'sin_tipo')
        counter[typ]+=1
        if typ not in system_types:
            editorial[str(fm.get('estado_editorial','sin_estado'))]+=1
            if fm.get('estado_conocimiento'):
                knowledge[str(fm['estado_conocimiento'])]+=1
        if typ in system_types:
            layers['infraestructura']+=1
        elif typ=='fuente':
            layers['fuentes']+=1
            source_reads[str(fm.get('lectura') or 'no_verificada')]+=1
        elif typ=='documento':
            layers['documentos_dx']+=1
            doc_classes[str(fm.get('clase') or 'sin_clase')]+=1
            doc_statuses[str(fm.get('estado_editorial') or 'sin_estado')]+=1
            docs.append({'doc_id':fm.get('doc_id'),
                         'clase':fm.get('clase'),
                         'estado_editorial':fm.get('estado_editorial'),
                         'ruta':p.relative_to(vault).as_posix(),
                         'fuentes_referenciadas':len(fm.get('fuentes') or [])})
        elif typ in work_types:
            layers['trabajo_provisional']+=1
        elif typ in registry:
            layers['entidades_operativas']+=1
        else:
            layers['otras_notas']+=1
    # Sort closings by the declared time, not by their random identifier.
    # The timestamp must include timezone; malformed closings are flagged.
    continuity=[]
    invalid_continuity=[]
    for entry in (vault/'90_Sistema'/'Continuidad').glob('*.md'):
        try:
            front,_=split_frontmatter(entry.read_text(encoding='utf8'))
            stamp=str(front.get('registrado_en') or '')
            when=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if when.tzinfo is None or when.utcoffset() is None:
                raise ValueError('registrado_en without timezone')
            continuity.append((when.astimezone(timezone.utc),entry.relative_to(vault).as_posix()))
        except (ValueError,UnicodeError,TypeError):
            invalid_continuity.append(entry.relative_to(vault).as_posix())
    continuity.sort(key=lambda row:(row[0],row[1]))
    invalid_continuity.sort()
    totals={k:layers[k] for k in ('infraestructura','fuentes','trabajo_provisional',
                                 'documentos_dx','entidades_operativas','otras_notas')}
    return {'empresa':cfg['company_name'],'id_empresa':cfg['company_id'],
            'version_instancia':cfg.get('version_instancia','NO DECLARADA'),
            'total_notas':sum(counter.values()),'por_tipo':dict(sorted(counter.items())),
            'editorial':dict(editorial),'conocimiento':dict(knowledge),
            'capas':totals,
            'plantillas_instaladas':len(list((vault/'90_Sistema'/'Plantillas').glob('*.md'))),
            'vistas_bases_instaladas':len(list((vault/'90_Sistema'/'Vistas').glob('*.base'))),
            'fuentes_resumen':{'total':layers['fuentes'],
                               'por_lectura':dict(sorted(source_reads.items()))},
            'documentos_dx':{'total':layers['documentos_dx'],
                             'por_clase':dict(sorted(doc_classes.items())),
                             'por_estado_editorial':dict(sorted(doc_statuses.items())),
                             'registros':sorted(docs,key=lambda d:str(d['doc_id']))},
            'ultima_continuidad':continuity[-1][1] if continuity else None,
            'continuidades_fecha_invalida':invalid_continuity,
            'advertencia':'Structural count, NOT coverage sufficiency nor validated truth'}


def exact_search(vault: Path, term: str, limit: int=12) -> dict:
    vault,_=safe_vault(vault)
    term=term.strip()
    if len(term)<2 or len(term)>220:
        raise ValueError('Literal query between 2 and 220 characters')
    results=[]
    for p in notes_in_vault(vault):
        fm,body=split_frontmatter(p.read_text(encoding='utf8'))
        if fm.get('sensibilidad') != 'interno': continue
        if fm.get('tipo') in ('control','sistema','mapa'):continue
        count=body.casefold().count(term.casefold())
        if count:
            results.append({'id':fm.get('id'), 'tipo':fm.get('tipo'), 'ruta':str(p.relative_to(vault)), 'menciones':count,
                            'editorial':fm.get('estado_editorial'), 'vigencia':fm.get('vigencia','sin_verificar')})
    results.sort(key=lambda r:(-r['menciones'],str(r['ruta'])))
    return {'consulta':term,'resultados':results[:limit],'total':len(results),
            'alcance':'Textual search only, NOT semantic retrieval, nor an authority resolver.'}


def authority_lookup(vault: Path, topic: str, scope: str, *, as_of: str|None=None) -> dict:
    vault,_=safe_vault(vault)
    target_date=date.fromisoformat(as_of) if as_of else date.today()
    eligible=[]
    for m in sorted((vault/'90_Sistema'/'Traspasos').glob('*/manifest.json')):
        data=json.loads(m.read_text(encoding='utf8'))
        blocks={b['block_id']:b for b in data.get('blocks',[])}
        docs={d['doc_id']:d for d in data.get('documents',[])}
        sources={s['source_id']:s for s in data.get('sources',[])}
        for auth in data.get('authorities',[]):
            if auth['topic_key']!=topic or auth['scope']!=scope:continue
            start=auth.get('valid_from');end=auth.get('valid_to')
            if start and target_date<date.fromisoformat(start):continue
            if end and target_date>date.fromisoformat(end):continue
            block=blocks.get(auth['block_id'])
            doc=docs.get(auth['doc_id'])
            if not block or not doc or block.get('access')!='interno' or doc.get('access')!='interno':continue
            refs=[sources.get(s,{'source_id':s, 'read_status':'no_verificada'}) for s in block.get('source_ids',[])]
            refs=[{'source_id':s['source_id'],'read_status':s.get('read_status'),'locator':s.get('locator') if s.get('access')=='interno' else '[restringido]'} for s in refs]
            eligible.append({'documento_id':auth['doc_id'],'bloque_id':auth['block_id'],
                             'temporalidad_registrada':auth['temporal_status'],
                             'desde':start,'hasta':end,'fuentes':refs,'traspaso':str(m.relative_to(vault))})
    status='sin_autoridad_explicita' if not eligible else ('conflicto' if len(eligible)>1 else 'candidato_para_verificar')
    return {'asunto':topic,'ambito':scope,'fecha_consultada':target_date.isoformat(),
            'estado':status,'coincidencias':eligible,
            'limite':'Only authorities declared in imported packages, filtered by dates and internal access. It does not certify current sourcing nor legal/financial authorization; verify the original.'}


def diagnose(vault: Path|None=None) -> dict:
    obs_path=shutil.which('obsidian')
    found=[]
    if sys.platform=='darwin':
        found=[p for p in [Path('/Applications/Obsidian.app'),Path.home()/'Applications'/'Obsidian.app'] if p.exists()]
    elif sys.platform=='win32':
        found=[p for p in [Path(os.environ.get('LOCALAPPDATA',''))/'Programs'/'Obsidian'/'Obsidian.exe'] if p.exists()]
    else:
        found=[p for p in [Path('/usr/bin/obsidian'),Path('/opt/Obsidian/obsidian')] if p.exists()]
    try:
        import jsonschema
        js=jsonschema.__version__ if hasattr(jsonschema,'__version__') else 'available'
    except ImportError:js='NOT INSTALLED'
    try:
        import yaml
        yy=yaml.__version__
    except ImportError:yy='NOT INSTALLED'
    result={'so':platform.platform(),'python':sys.version.split()[0],'directorio_trabajo':str(Path.cwd()),
            'python_requisitos':{'PyYAML':yy,'jsonschema':js},
            'obsidian_cli_en_path':bool(obs_path),'obsidian_cli_ruta':obs_path,
            'posibles_instalaciones':[str(x) for x in found],
            'obsidian_abierto_en_interfaz':'NOT VERIFIED',
            'bases_habilitado':'NOT VERIFIED',
            'plugins_terceros':'NOT INSTALLED BY THIS PRODUCT',
            'conectores_codex':'NOT VERIFIED',
            'siguiente':'Verify real GUI/version and permissions with the owner before installing/configuring'}
    if vault:
        v,_=safe_vault(vault)
        result['boveda']=str(v)
        result['boveda_reconocida']=True
    return result
