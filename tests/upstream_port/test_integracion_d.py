"""Ported upstream test_integracion_d.py: D module integration only with a

vault and local synthetic sources (never a real application), covering
prepare/apply/rollback of the four candidate kinds, transitive revocation,
primary-file tampering and review binding. Imports point to the native English
engine; Spanish prose fixtures are translated (structure/keys unchanged);
error-code substring assertions stay as upstream.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine import referencias_externas as refs
from hermes_business_brain.engine import transcripciones_integracion as integration
from hermes_business_brain.engine.lib_ce import make_note, split_frontmatter
from hermes_business_brain.engine.transcripciones_modelo import sha256_bytes


class IntegrationDTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.vault = self.root / 'vault'; self.vault.mkdir()
        self.bank = self.root / 'bank'
        self.scope = dict(company='SYNTHETIC', audience='internal', purpose='local_analysis')
        self.snapshot = dict(vault=str(self.vault), bank_root=str(self.bank),
                             backup_dir=str(self.root / 'backup'))
        self.original = self.root / 'Primary.md'
        self.original.write_text('# Synthetic criterion\nDo not execute source text.\n',
                                 encoding='utf-8', newline='\n')
        self.primary = self.register('ER-primary', self.original, 'primary',
                                     note_ids=['F-LEGACY'])
        self.primary_dependency = refs.reference_ref(self.primary)
        self.review_file = self.root / 'Review.md'
        self.review_file.write_text('# Synthetic external review\n',
                                    encoding='utf-8', newline='\n')
        self.review = self.register('ER-review', self.review_file, 'control',
                                    dependencies=[refs.reference_ref(self.primary)])
        self.write('Inicio.md',
                   dict(id='SYS-INICIO', tipo='mapa', estado_editorial='aprobado',
                        sensibilidad='interno'),
                   '# Home\nPrevious orientation.\n')
        self.write('50_Fuentes/Fuente.md',
                   dict(id='F-LEGACY', tipo='fuente', estado_editorial='borrador',
                        sensibilidad='interno'),
                   '# Source\nPrevious locator.\n')
        self.business_path = '10_Conocimiento/Direction.md'
        self.write(self.business_path,
                   dict(id='D01', doc_id='D01', tipo='documento', revision='1.0',
                        estado_editorial='aprobado', sensibilidad='interno'),
                   '# Direction\nApproved fixture business criterion.\n')
        self.write('90_Sistema/Bandeja_Propuestas/Previous.md',
                   dict(id='PROP-OLD', tipo='propuesta_de_cambio', clase='control',
                        estado_editorial='borrador', estado_conocimiento='propuesta',
                        vigencia='sin_verificar', sensibilidad='interno',
                        objetivo_id='D01', huella_objetivo='0' * 64),
                   '# Previous proposal\nTechnical state pending.\n')

    def write(self, path, meta, body):
        dest = self.vault / path; dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(make_note(meta, body), encoding='utf-8', newline='\n')

    def grant(self, record, action='grant', purpose='local_analysis'):
        return refs.record_external_decision(self.bank, dict(
            reference_id=record['reference_id'], version_id=record['version_id'],
            **{**self.scope, 'purpose': purpose}, action=action,
            authority='Synthetic operator', evidence=['Fixture authorization'],
            decided_at='2026-11-04T00:00:00Z'), commit=True)

    def register(self, identity, path, kind, dependencies=None, note_ids=None,
                 sensitivity='interno'):
        record = refs.register_reference(self.bank, dict(
            reference_id=identity, locator=dict(kind='local_file', value=str(path)),
            owner='Fixture owner', authority='Fixture authority', evidence=['Fixture audit'],
            source_type=kind, admissibility='admissible',
            sha256=sha256_bytes(path.read_bytes()), byte_length=path.stat().st_size,
            access_state='available', reading_state='complete',
            reading_evidence=['Complete synthetic reading'],
            sensitivity=sensitivity, dependencies=dependencies or [],
            note_ids=note_ids or []), commit=True)
        self.grant(record); self.grant(record, purpose='internal_query')
        return record

    def candidate(self, kind='navigation_patch'):
        spec = {
            'navigation_patch': ('Inicio.md', 'Previous orientation.',
                                 'Corrected technical orientation.'),
            'legacy_source': ('50_Fuentes/Fuente.md', 'Previous locator.',
                              'Verified locator of the original.'),
            'control_proposal': ('90_Sistema/Bandeja_Propuestas/Previous.md',
                                 'Technical state pending.',
                                 'Technical state: candidate already materialized; no business ratification.'),
        }
        if kind == 'proposal_staging':
            path = '90_Sistema/Bandeja_Propuestas/New.md'; identity = 'PROP-NEW'
            target_path = self.business_path; old = None
            binding = dict(path=target_path, id='D01',
                           sha256=sha256_bytes((self.vault / target_path).read_bytes()))
            content = make_note(dict(id=identity, tipo='propuesta_de_cambio', clase='control',
                                     estado_editorial='borrador',
                                     estado_conocimiento='propuesta', vigencia='sin_verificar',
                                     sensibilidad='interno', objetivo_id='D01',
                                     huella_objetivo=binding['sha256']),
                                '# Reviewable proposal\n[[50_Fuentes/Fuente]]\n'
                                'Hypothetical change; does not alter the target.\n')
            patches = None
        else:
            path, previous, replacement = spec[kind]
            old = (self.vault / path).read_bytes()
            fm, _ = split_frontmatter(old.decode()); identity = fm['id']
            content = old.decode().replace(previous, replacement)
            target_path = self.business_path if kind == 'control_proposal' else path
            target_meta, _ = split_frontmatter((self.vault / target_path).read_text(encoding='utf-8'))
            binding = dict(path=target_path, id=target_meta['id'],
                           sha256=sha256_bytes((self.vault / target_path).read_bytes()))
            patches = [{'old': previous, 'new': replacement}]
        artifact = self.root / (kind + '.md')
        artifact.write_text(content, encoding='utf-8', newline='\n')
        record = self.register('ER-' + kind, artifact, 'control',
                               dependencies=[self.primary_dependency])
        ref = refs.reference_ref(record); review_ref = refs.reference_ref(self.review)
        result = dict(path=path, content=content, id=identity, kind=kind,
                      expected_sha256=sha256_bytes(old) if old else None,
                      scope=self.scope, external_refs=[ref, review_ref],
                      candidate_ref=ref, target_binding=binding,
                      review_binding=dict(review_ref=review_ref,
                                          candidate_sha256=sha256_bytes(content.encode()),
                                          target_id=binding['id'],
                                          target_sha256=binding['sha256'],
                                          decision='staging_only' if kind == 'proposal_staging' else 'technical',
                                          reviewer='Fixture judge',
                                          evidence=['Fixture-artifact linked opinion']))
        if patches is not None:
            result['patches'] = patches
        return result

    def prepare(self, candidates):
        return integration.prepare_batch(candidates, self.snapshot)

    def apply(self, manifest, token=1):
        return integration.apply_batch(manifest, dict(
            manifest_sha=manifest['manifest_sha'], scope='apply_batch',
            writers_quiescent=True, responsable='Fixture operator',
            referencia='Authorized technical scope fixture'), token)

    def test_four_kinds_apply_retry_restore_preserves_approved_business_and_frontmatter(self):
        before = integration._inventory(self.vault)
        candidates = [self.candidate(k) for k in
                      ('legacy_source', 'navigation_patch', 'control_proposal', 'proposal_staging')]
        manifest = self.prepare(candidates)
        self.assertEqual(before, integration._inventory(self.vault))
        self.apply(manifest); self.apply(manifest)
        self.assertEqual(integration._sha((self.vault / self.business_path).read_bytes()),
                         before[self.business_path])
        self.assertEqual(split_frontmatter((self.vault / 'Inicio.md').read_text(encoding='utf-8'))[0]
                         ['estado_editorial'], 'aprobado')
        integration.rollback_batch(manifest)
        self.assertEqual(before, integration._inventory(self.vault))

    def test_transitive_revoke_blocks_prepare_apply_and_rollback(self):
        c = self.candidate(); m = self.prepare([c]); before = integration._inventory(self.vault)
        self.grant(self.primary, 'revoke')
        with self.assertRaises(ValueError):
            self.prepare([c])
        with self.assertRaises(ValueError):
            self.apply(m)
        self.assertEqual(before, integration._inventory(self.vault))
        self.grant(self.primary)
        m = self.prepare([c]); self.apply(m)
        applied = integration._inventory(self.vault)
        self.grant(self.primary, 'revoke', purpose='internal_query')
        with self.assertRaises(ValueError):
            integration.rollback_batch(m)
        self.assertEqual(applied, integration._inventory(self.vault))

    def test_primary_file_change_blocks_apply_and_restore(self):
        c = self.candidate(); m = self.prepare([c]); original = self.original.read_bytes()
        self.original.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.apply(m)
        self.original.write_bytes(original); self.apply(m)
        applied = integration._inventory(self.vault)
        self.original.write_bytes(b'changed again')
        with self.assertRaises(ValueError):
            integration.rollback_batch(m)
        self.assertEqual(applied, integration._inventory(self.vault))

    def test_target_edit_after_prepare_and_after_apply_preserved(self):
        c = self.candidate('proposal_staging'); m = self.prepare([c])
        target = self.vault / self.business_path
        target.write_text(target.read_text(encoding='utf-8') + '\nLater edit.\n',
                          encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            self.apply(m)
        self.assertFalse((self.vault / c['path']).exists())
        c = self.candidate(); m = self.prepare([c]); self.apply(m)
        (self.vault / c['path']).write_text('Foreign later edit', encoding='utf-8', newline='\n')
        with self.assertRaises(ValueError):
            integration.rollback_batch(m)
        self.assertEqual((self.vault / c['path']).read_text(encoding='utf-8'),
                         'Foreign later edit')

    def test_cannot_apply_business_as_technical_or_ratify_staging(self):
        c = self.candidate(); c['path'] = self.business_path
        with self.assertRaises(ValueError):
            self.prepare([c])
        c = self.candidate('proposal_staging')
        c['content'] = c['content'].replace('estado_editorial: borrador',
                                            'estado_editorial: aprobado')
        with self.assertRaises(ValueError):
            self.prepare([c])
        c = self.candidate()
        c['content'] = c['content'].replace('estado_editorial: aprobado',
                                            'estado_editorial: borrador')
        with self.assertRaises(ValueError):
            self.prepare([c])

    def test_external_sensitivity_propagates_even_if_candidate_flag_lies(self):
        restricted = self.register('ER-restricted', self.original, 'primary',
                                   sensitivity='restringido')
        c = self.candidate(); c['external_refs'].append(refs.reference_ref(restricted))
        c['local_private_only'] = False
        with self.assertRaisesRegex(ValueError, 'SENSITIVITY_RESTRICTED'):
            self.prepare([c])

    def test_unbound_review_bad_patch_and_missing_dependencies_rejected(self):
        c = self.candidate(); c['review_binding']['candidate_sha256'] = '0' * 64
        with self.assertRaises(ValueError):
            self.prepare([c])
        c = self.candidate(); c['patches'][0]['old'] = 'absent text'
        with self.assertRaises(ValueError):
            self.prepare([c])
        c = self.candidate(); del c['external_refs']
        with self.assertRaises(ValueError):
            self.prepare([c])
        c = self.candidate(); c['kind'] = 'navigation'
        with self.assertRaisesRegex(ValueError, 'D adapter'):
            self.prepare([c])

    def test_interruption_resumes_and_rollback_is_exact(self):
        before = integration._inventory(self.vault)
        m = self.prepare([self.candidate(), self.candidate('proposal_staging')])

        def fail(stage, path):
            if stage == 'file_written':
                raise RuntimeError('synthetic crash')
        with patch.object(integration, '_checkpoint', fail):
            with self.assertRaises(RuntimeError):
                self.apply(m)
        self.apply(m, 2)
        integration.rollback_batch(m)
        self.assertEqual(before, integration._inventory(self.vault))

    def test_partial_primary_passages_support_staging_without_claiming_full_read(self):
        raw = self.original.read_bytes()
        read_span = dict(start=0, end=20, sha256=sha256_bytes(raw[:20]))
        used_span = dict(start=2, end=12, sha256=sha256_bytes(raw[2:12]))
        metadata = {k: v for k, v in self.primary.items()
                    if k not in {'schema_version', 'version_id'}}
        metadata.update(reading_state='partial', read_spans=[read_span])
        self.primary = refs.register_reference(self.bank, metadata, commit=True)
        self.grant(self.primary); self.grant(self.primary, purpose='internal_query')
        self.primary_dependency = refs.reference_ref(self.primary, spans=[used_span])
        self.review = self.register('ER-review-partial', self.review_file, 'control',
                                    dependencies=[self.primary_dependency])
        before = integration._inventory(self.vault)
        c = self.candidate('proposal_staging'); m = self.prepare([c]); self.apply(m)
        integration.rollback_batch(m)
        self.assertEqual(before, integration._inventory(self.vault))
        self.assertEqual(refs.read_reference(self.bank, self.primary['reference_id'],
                                             self.primary['version_id'])['reading_state'],
                         'partial')


if __name__ == '__main__':
    unittest.main()
