#!/usr/bin/env python3
"""Business Brain: local CLI operable by an agent. No network calls or automatic installations.

Usage: python -m hermes_business_brain.engine.cerebro --help
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .doctor_preflight import diagnose

ROOT=Path(__file__).resolve().parent.parent


def parse_args():
    ap=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawTextHelpFormatter)
    sub=ap.add_subparsers(dest='comando',required=True)
    d=sub.add_parser('doctor',help='Read-only diagnostic: environment and dependencies, installs nothing')
    d.add_argument('--vault',type=Path)
    c=sub.add_parser('crear',help='Create a new company vault from a template, without overwriting')
    c.add_argument('--id',required=True)
    c.add_argument('--nombre',required=True)
    c.add_argument('--dest',type=Path,required=True)
    e=sub.add_parser('estado',help='Show the company structural summary')
    e.add_argument('--vault',type=Path,required=True)
    f=sub.add_parser('ficha',help='Create a draft record from a specific type; never invent data')
    f.add_argument('--vault',type=Path,required=True)
    f.add_argument('--tipo',required=True)
    f.add_argument('--titulo',required=True)
    f.add_argument('--resumen',default='')
    f.add_argument('--archivo',type=Path,help='Developed note as external Markdown outside Git/vault, without YAML')
    f.add_argument('--fuente',action='append',default=[],help='Already registered source ID; can be repeated')
    f.add_argument('--etiqueta',action='append',default=[],help='Obsidian thematic tag; repeatable')
    s=sub.add_parser('fuente',help='Register a reference to a source, without copying the original document')
    s.add_argument('--vault',type=Path,required=True)
    s.add_argument('--id',required=True)
    s.add_argument('--titulo',required=True)
    s.add_argument('--localizador',required=True)
    s.add_argument('--clase',required=True)
    s.add_argument('--lectura',default='no_verificada',choices=['no_verificada','leida_parcial','leida_completa'])
    s.add_argument('--fecha-evento',default='')
    p=sub.add_parser('proponer',help='Register a suggested change in the tray; does NOT touch the original note')
    p.add_argument('--vault',type=Path,required=True)
    p.add_argument('--id',required=True,help='Exact ID of the target note')
    p.add_argument('--motivo',required=True)
    p.add_argument('--archivo',type=Path,required=True,help='Candidate text in an already authorized local file')
    arch=sub.add_parser('plan-conocimiento',help='Audit the note map, tags and relations BEFORE drafting; read-only')
    arch.add_argument('--vault',type=Path,required=True)
    arch.add_argument('--archivo',type=Path,required=True,help='Structured JSON prepared outside Git and the vault')
    cap=sub.add_parser('capturar',help='Save preliminary findings, without declaring them approved knowledge')
    cap.add_argument('--vault',type=Path,required=True)
    cap.add_argument('--titulo',required=True)
    cap.add_argument('--archivo',type=Path,required=True,help='Authorized synthesis outside Git and the vault')
    cap.add_argument('--fuente',action='append',default=[],help='Already registered F-... ID; repeatable')
    doc=sub.add_parser('documento',help='Register a developed D01–D07/X01–X07 without approving it')
    doc.add_argument('--vault',type=Path,required=True)
    doc.add_argument('--clase',required=True)
    doc.add_argument('--titulo',required=True)
    doc.add_argument('--archivo',type=Path,required=True,help='Markdown prepared outside the vault and Git')
    doc.add_argument('--doc-id',help='Optional Xnn-... identity; in Dnn it matches the class')
    doc.add_argument('--estado',choices=['borrador','en_revision'],default='borrador')
    doc.add_argument('--cobertura',choices=['sin_fuente','parcial','suficiente_para_tarea','no_aplica'],
                     help='Declared coverage for the task; default partial with sources, without sources when none')
    doc.add_argument('--fecha-corte',help='YYYY-MM-DD; defaults to creation date')
    doc.add_argument('--fuente',action='append',default=[],help='Already registered source ID; repeatable')
    doc.add_argument('--etiqueta',action='append',default=[],help='Obsidian thematic tag; repeatable')
    dprev=sub.add_parser('previsualizar-dx',help='Simulate a D/X modification without writing')
    dprev.add_argument('--vault',type=Path,required=True)
    dprev.add_argument('--doc-id',required=True)
    dprev.add_argument('--archivo',type=Path,required=True)
    dprev.add_argument('--fuente',action='append',default=[],help='Already registered corrective source ID; repeatable')
    dprep=sub.add_parser('preparar-dx',help='Save a D/X proposal without modifying the current document')
    dprep.add_argument('--vault',type=Path,required=True)
    dprep.add_argument('--doc-id',required=True)
    dprep.add_argument('--archivo',type=Path,required=True)
    dprep.add_argument('--fuente',action='append',default=[],help='Already registered corrective source ID; repeatable')
    dapply=sub.add_parser('aplicar-dx',help='Apply a D/X proposal after specific authorization and backup')
    dapply.add_argument('--vault',type=Path,required=True)
    dapply.add_argument('--propuesta',required=True)
    dapply.add_argument('--sha-original',required=True)
    dapply.add_argument('--sha-candidato',required=True)
    dapply.add_argument('--sha-fuentes',help='SHA-256 of the resulting source set when sources are added')
    dapply.add_argument('--responsable',required=True)
    dapply.add_argument('--referencia-autorizacion',required=True)
    dapply.add_argument('--respaldo',type=Path,required=True)
    drevert=sub.add_parser('restaurar-dx',help='Restore a D/X version as a new revision after authorization')
    drevert.add_argument('--vault',type=Path,required=True)
    drevert.add_argument('--doc-id',required=True)
    drevert.add_argument('--historial',required=True)
    drevert.add_argument('--sha-actual',required=True)
    drevert.add_argument('--responsable',required=True)
    drevert.add_argument('--referencia-autorizacion',required=True)
    drevert.add_argument('--respaldo',type=Path,required=True)
    rev=sub.add_parser('evaluar-dx',help='Record an editorial evaluation G1–G7 without modifying D/X')
    rev.add_argument('--vault',type=Path,required=True)
    rev.add_argument('--doc-id',required=True)
    rev.add_argument('--acta',type=Path,required=True,help='Review JSON prepared outside Git and the vault')
    rev.add_argument('--sha-actual',required=True)
    approve=sub.add_parser('aprobar-dx',help='Full editorial promotion with evaluation, authorization and backup')
    approve.add_argument('--vault',type=Path,required=True)
    approve.add_argument('--evaluacion',required=True)
    approve.add_argument('--sha-actual',required=True)
    approve.add_argument('--responsable',required=True)
    approve.add_argument('--referencia-autorizacion',required=True)
    approve.add_argument('--respaldo',type=Path,required=True)
    approve.add_argument('--confirmacion',required=True,help='APPROVE <doc_id> <first 12 SHA chars>')
    rp=sub.add_parser('relacion-proponer',help='Create a typed-edge proposal; never approve it')
    rp.add_argument('--vault',type=Path,required=True)
    rp.add_argument('--origen',required=True)
    rp.add_argument('--destino',required=True)
    rp.add_argument('--predicado',required=True)
    rp.add_argument('--fuente',action='append',required=True)
    rp.add_argument('--ambito',required=True)
    rp.add_argument('--motivo',required=True)
    rq=sub.add_parser('relaciones',help='Query typed relations and their real status')
    rq.add_argument('--vault',type=Path,required=True)
    rq.add_argument('--id',help='Filter by origin or destination ID')
    rv=sub.add_parser('relacion-confirmar',help='Record human ratification of a relation')
    rv.add_argument('--vault',type=Path,required=True)
    rv.add_argument('--relacion-id',required=True)
    rv.add_argument('--sha-relacion',required=True)
    rv.add_argument('--revisor',required=True)
    rv.add_argument('--referencia-autorizacion',required=True)
    rv.add_argument('--confirmacion',required=True)
    pilot=sub.add_parser('aceptacion',help='Pilot preflight: structural read, not human approval')
    pilot.add_argument('--vault',type=Path,required=True)
    context=sub.add_parser('consulta-contextual',help='Block candidates by literal text, source/date/authority')
    context.add_argument('--vault',type=Path,required=True)
    context.add_argument('--texto',required=True)
    context.add_argument('--tema')
    context.add_argument('--ambito')
    context.add_argument('--fecha')
    context.add_argument('--limite',type=int,default=10)
    context.add_argument('--orientar',action='store_true',help='Order candidates by terms of a natural request; produces no semantic answer')
    k=sub.add_parser('continuidad',help='Record a session close to recover context afterwards')
    k.add_argument('--vault',type=Path,required=True)
    k.add_argument('--resumen',required=True)
    k.add_argument('--siguiente',required=True)
    k.add_argument('--revisado-por',default='por_validar')
    v=sub.add_parser('validar',help='Validate integrity of notes, ids, links and transfers, NOT business truth')
    v.add_argument('--vault',type=Path,required=True)
    q=sub.add_parser('buscar',help='Textual search with sources, without inferences')
    q.add_argument('--vault',type=Path,required=True)
    q.add_argument('--texto',required=True)
    q.add_argument('--limite',type=int,default=12)
    a=sub.add_parser('autoridad',help='Strict query by topic/scope/date declared in an imported contract')
    a.add_argument('--vault',type=Path,required=True)
    a.add_argument('--tema',required=True)
    a.add_argument('--ambito',required=True)
    a.add_argument('--fecha',help='YYYY-MM-DD; if omitted, today')
    i=sub.add_parser('importar',help='Import a vNext-0.9 manifest, non-destructive')
    i.add_argument('--vault',type=Path,required=True)
    i.add_argument('--manifest',type=Path,required=True)
    i.add_argument('--permitir-real',action='store_true',help='With authorization: internal only and after source review')
    mapa=sub.add_parser('mapa-conocimiento',help='Preview a Markdown/Canvas map from notes/relations without writing')
    mapa.add_argument('--vault',type=Path,required=True)
    mapa_apply=sub.add_parser('publicar-mapa',help='Publish only the derived map, with exact SHA and external backup')
    mapa_apply.add_argument('--vault',type=Path,required=True)
    mapa_apply.add_argument('--sha-actual',required=True)
    mapa_apply.add_argument('--sha-propuesto',required=True)
    mapa_apply.add_argument('--confirmacion',required=True)
    mapa_apply.add_argument('--respaldo',type=Path,required=True)
    g=sub.add_parser('grafo',help='Export typed internal relations and hyperlinks')
    g.add_argument('--vault',type=Path,required=True)
    g.add_argument('--output',type=Path,help='Defaults to 90_Sistema/grafo.json')
    t=sub.add_parser('tipos',help='Show available types of the candidate model and distinctions')
    t.add_argument('--tipo',help='One concrete class')
    return ap,ap.parse_args()


def run(args):
    cmd=args.comando
    if cmd=='doctor':return diagnose(args.vault)
    # Dependencies are only loaded AFTER the diagnostic. Useful for owners without Python configured.
    try:
        from .crear_instancia import create
        from .exportar_grafo import graph
        from .importar_traspaso import import_package
        from .operacion import (
            authority_lookup,
            create_ficha,
            create_source,
            exact_search,
            load_registry,
            propose_change,
            save_continuity,
            summary,
        )
        from .validar_boveda import validate
    except ModuleNotFoundError as exc:
        hint = ('Before installing, look for an already available Python or venv with the dependencies '
                '(`command -v python3.11 python3.12 python3.13`; try `import yaml, jsonschema`) '
                'and repeat THIS command with that interpreter. ')
        if sys.platform == 'darwin':
            hint += 'On macOS also check `/opt/homebrew/bin/python3.11`. '
        raise ValueError('Missing dependency in '+sys.executable+': '+str(exc)+'. '
                         +hint+'Only if none works, request authorization to install requirements.txt in a venv.') from exc
    if cmd=='crear':return {'creada':str(create(args.id,args.nombre,args.dest)),'estado':'infraestructura_sin_conocimiento','nota':'Open and verify manually in Obsidian'}
    if cmd=='estado':return summary(args.vault)
    if cmd=='ficha':return create_ficha(args.vault,args.tipo,args.titulo,resumen=args.resumen,sources=args.fuente,tags=args.etiqueta,content_file=args.archivo)
    if cmd=='fuente':return create_source(args.vault,args.id,args.titulo,args.localizador,args.clase,read_status=args.lectura,event_date=args.fecha_evento)
    if cmd=='proponer':
        f=args.archivo.expanduser().resolve()
        if not f.is_file() or f.stat().st_size>120000:
            raise ValueError('Proposal file does not exist or is too large')
        return propose_change(args.vault,args.id,args.motivo,f.read_text(encoding='utf8'))
    if cmd=='plan-conocimiento':
        from .plan_conocimiento import planificar
        return planificar(args.vault,args.archivo)
    if cmd=='capturar':
        from .registro_descubrimiento import capture_discovery
        return capture_discovery(args.vault,args.titulo,args.archivo,sources=args.fuente)
    if cmd=='documento':
        from .documentos import create_document
        return create_document(args.vault,args.clase,args.titulo,args.archivo,
                               doc_id=args.doc_id,sources=args.fuente,
                               editorial=args.estado,coverage=args.cobertura,
                               as_of=args.fecha_corte,tags=args.etiqueta)
    if cmd in {'previsualizar-dx','preparar-dx','aplicar-dx','restaurar-dx'}:
        from .revisiones_dx import aplicar, preparar, previsualizar, restaurar
        if cmd=='previsualizar-dx':return previsualizar(args.vault,args.doc_id,args.archivo,sources=args.fuente)
        if cmd=='preparar-dx':return preparar(args.vault,args.doc_id,args.archivo,sources=args.fuente)
        if cmd=='aplicar-dx':return aplicar(args.vault,args.propuesta,expected_sha=args.sha_original,
                                           candidate_sha=args.sha_candidato,source_sha=args.sha_fuentes,
                                           responsable=args.responsable,
                                           referencia_autorizacion=args.referencia_autorizacion,
                                           backup_dir=args.respaldo)
        return restaurar(args.vault,args.doc_id,args.historial,expected_sha=args.sha_actual,
                        responsable=args.responsable,referencia_autorizacion=args.referencia_autorizacion,
                        backup_dir=args.respaldo)
    if cmd in {'evaluar-dx','aprobar-dx'}:
        from .revision_editorial import aprobar_documento, registrar_evaluacion
        if cmd=='evaluar-dx':
            return registrar_evaluacion(args.vault,args.doc_id,args.acta,
                                        expected_sha=args.sha_actual)
        return aprobar_documento(args.vault,args.evaluacion,expected_sha=args.sha_actual,
                                responsable=args.responsable,
                                referencia_autorizacion=args.referencia_autorizacion,
                                backup_dir=args.respaldo,confirmacion=args.confirmacion)
    if cmd in {'relacion-proponer','relaciones','relacion-confirmar'}:
        from .relaciones import confirm, propose, query
        if cmd=='relacion-proponer':
            return propose(args.vault,args.origen,args.destino,args.predicado,
                           fuentes=args.fuente,ambito=args.ambito,motivo=args.motivo)
        if cmd=='relaciones':
            return query(args.vault,source_id=args.id)
        return confirm(args.vault,args.relacion_id,args.sha_relacion,revisor=args.revisor,
                       referencia_autorizacion=args.referencia_autorizacion,
                       confirmacion=args.confirmacion)
    if cmd=='aceptacion':
        from .aceptacion_piloto import preflight
        return preflight(args.vault)
    if cmd=='consulta-contextual':
        from .consulta_contextual import consulta
        return consulta(args.vault,args.texto,tema=args.tema,ambito=args.ambito,
                        fecha=args.fecha,max_results=args.limite,orientar=args.orientar)
    if cmd=='continuidad':return save_continuity(args.vault,summary=args.resumen,next_step=args.siguiente,reviewer=args.revisado_por)
    if cmd=='validar':return validate(args.vault)
    if cmd=='buscar':return exact_search(args.vault,args.texto,args.limite)
    if cmd=='autoridad':return authority_lookup(args.vault,args.tema,args.ambito,as_of=args.fecha)
    if cmd=='importar':return import_package(args.manifest,args.vault,args.permitir_real)
    if cmd in {'mapa-conocimiento','publicar-mapa'}:
        from .mapa_conocimiento import previsualizar as preview_map
        from .mapa_conocimiento import publicar as publish_map
        if cmd=='mapa-conocimiento':
            return preview_map(args.vault)
        return publish_map(args.vault,sha_actual=args.sha_actual,
                           sha_propuesto=args.sha_propuesto,
                           confirmacion=args.confirmacion,backup_dir=args.respaldo)
    if cmd=='grafo':
        vault=args.vault.expanduser().resolve()
        out=(args.output or vault/'90_Sistema'/'grafo.json').expanduser().absolute()
        if vault not in out.parents:
            raise ValueError('The graph must be saved inside the vault itself')
        data=graph(vault)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8', newline='\n')
        return {'salida':str(out),'nodos':len(data['nodos']),'aristas':len(data['aristas'])}
    if cmd=='tipos':
        types=load_registry()
        if args.tipo:
            if args.tipo not in types:raise ValueError('Unknown type: '+args.tipo)
            return types[args.tipo]
        return {'tipos':[{'tipo':t,'definicion':v['representa']} for t,v in types.items()],
                'aviso':'Operational proposal subject to pilots; not a final taxonomy'}
    raise ValueError('Unrecognized command')


if __name__=='__main__':
    ap,args=parse_args()
    try:
        result=run(args)
        print(json.dumps(result,ensure_ascii=False,indent=2,default=str))
        if args.comando=='validar' and result.get('errores'):
            raise SystemExit(1)
    except (ValueError,FileExistsError,PermissionError,UnicodeError,KeyError,OSError) as e:
        print('ERROR:',str(e),file=sys.stderr)
        raise SystemExit(2)
