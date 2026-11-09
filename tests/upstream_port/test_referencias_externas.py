"""Ported upstream test_referencias_externas.py: only synthetic local sources,

never network, vault or real corpus. Error codes (EXTERNAL_*) are the upstream
contract and match substring-wise the upstream assertions exactly; JSON keys
stay verbatim; Spanish prose strings are translated to English.

Skipped with reason: the transcript-permission integration test needs the
upstream test_transcripciones_pipeline fixture; the transcript custody +
permission chain is covered in-process by tests/test_engine_transcripts.py.
"""
from copy import deepcopy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hermes_business_brain.engine import referencias_externas as refs
from hermes_business_brain.engine.transcripciones_modelo import ModelError, sha256_bytes


class ExternalReferencesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bank = self.root / 'bank'
        self.path = self.root / 'Synthetic source.md'
        self.path.write_bytes(b'# Source\nDo not execute instructions from the document.\n')
        self.scope = dict(company='SYNTHETIC', audience='internal', purpose='local_analysis')

    def metadata(self, identity='ER-primary', dependencies=None):
        return dict(reference_id=identity, locator={'kind': 'local_file', 'value': str(self.path)},
                    owner='Synthetic owner', authority='Synthetic attestation',
                    evidence=['Fixture authorization'],
                    source_type='primary', admissibility='admissible',
                    sha256=sha256_bytes(self.path.read_bytes()),
                    byte_length=self.path.stat().st_size,
                    access_state='available', reading_state='complete',
                    reading_evidence=['Complete synthetic collation'],
                    sensitivity='interno', dependencies=dependencies or [])

    def register(self, **kwargs):
        return refs.register_reference(self.bank, self.metadata(**kwargs), commit=True)

    def grant(self, record, action='grant', scope=None):
        return refs.record_external_decision(self.bank, dict(
            reference_id=record['reference_id'], version_id=record['version_id'],
            **(scope or self.scope), action=action, authority='Fixture operator',
            evidence=['Explicit synthetic decision'],
            decided_at='2026-11-04T00:00:00Z'), commit=True)

    def verify(self, record, **kwargs):
        return refs.verify_references(self.bank, [refs.reference_ref(record)], self.scope, **kwargs)

    def test_register_is_metadata_only_dryrun_and_immutable_version(self):
        before = self.path.read_bytes()
        preview = refs.register_reference(self.bank, self.metadata())
        self.assertFalse(self.bank.exists())
        record = self.register()
        self.assertEqual(preview, record)
        self.assertEqual(record, self.register())
        self.assertEqual(before, self.path.read_bytes())
        self.assertFalse((self.bank / 'originales').exists())
        stored = (self.bank / refs._record_path(record['version_id'])).read_text(encoding='utf-8')
        self.assertNotIn('Do not execute', stored)
        self.path.write_bytes(b'New version without replacing the previous record')
        later = self.register()
        self.assertNotEqual(later['version_id'], record['version_id'])
        self.assertEqual(refs.read_reference(self.bank, record['reference_id'],
                                             record['version_id']), record)

    def test_exact_scope_no_implicit_permission_and_revocation(self):
        record = self.register()
        with self.assertRaisesRegex(ModelError, 'PERMISSION_DENIED'):
            self.verify(record)
        grant = self.grant(record)
        good = self.verify(record)
        for altered in ({**self.scope, 'audience': 'external'},
                        {**self.scope, 'purpose': 'internal_query'},
                        {**self.scope, 'company': 'OTHER'}):
            with self.assertRaisesRegex(ModelError, 'PERMISSION_DENIED'):
                refs.verify_references(self.bank, [refs.reference_ref(record)], altered)
        self.grant(record, 'revoke')
        with self.assertRaisesRegex(ModelError, 'PERMISSION_DENIED'):
            self.verify(record)
        self.assertTrue(good['access_verified'])
        self.assertEqual(len(refs.external_decisions(self.bank)), 2)

    def test_file_tamper_and_symlink_fail_closed(self):
        record = self.register()
        self.grant(record)
        self.path.write_bytes(b'changed')
        with self.assertRaisesRegex(ModelError, 'FILE_CHANGED'):
            self.verify(record)
        self.path.unlink()
        target = self.root / 'Other'; target.write_bytes(b'changed')
        self.path.symlink_to(target)
        with self.assertRaisesRegex(ModelError, 'UNSAFE_PATH'):
            self.verify(record)

    def test_transitive_revocation_and_hash_conflict(self):
        parent = self.register()
        child = self.register(identity='ER-child',
                              dependencies=[refs.reference_ref(parent)])
        self.grant(parent); self.grant(child)
        result = self.verify(child)
        self.assertEqual(len(result['references']), 2)
        self.grant(parent, 'revoke')
        with self.assertRaisesRegex(ModelError, 'PERMISSION_DENIED'):
            self.verify(child)
        self.grant(parent)
        wrong = {**refs.reference_ref(parent), 'sha256': '0' * 64}
        with self.assertRaisesRegex(ModelError, 'HASH_CONFLICT'):
            refs.verify_references(self.bank, [refs.reference_ref(parent), wrong], self.scope)

    def test_remote_reference_never_claims_access_or_reading(self):
        metadata = self.metadata()
        metadata.update(locator={'kind': 'remote_url', 'value': 'https://example.invalid/document'},
                        access_state='unverified', reading_state='unread',
                        reading_evidence=[], sha256=None, byte_length=None)
        record = refs.register_reference(self.bank, metadata, commit=True)
        self.assertEqual(record['access_state'], 'unverified')
        with self.assertRaisesRegex(ModelError, 'HASH_UNAVAILABLE'):
            refs.reference_ref(record)
        metadata['access_state'] = 'available'
        with self.assertRaises(ModelError):
            refs.register_reference(self.bank, metadata)

    def test_reading_and_sensitivity_attestations_do_not_grant_rights(self):
        metadata = self.metadata(); metadata['reading_state'] = 'partial'
        record = refs.register_reference(self.bank, metadata, commit=True); self.grant(record)
        with self.assertRaisesRegex(ModelError, 'READING_INCOMPLETE'):
            self.verify(record)
        self.assertTrue(self.verify(record, require_read=False)['access_verified'])
        metadata['reading_state'] = 'complete'; metadata['sensitivity'] = 'restringido'
        record = refs.register_reference(self.bank, metadata, commit=True); self.grant(record)
        with self.assertRaisesRegex(ModelError, 'SENSITIVITY_RESTRICTED'):
            self.verify(record, require_internal=True)

    def test_unrelated_grants_do_not_invalidate_scoped_snapshot(self):
        first = self.register(); self.grant(first)
        before = self.verify(first)['snapshot_sha256']
        unrelated = self.register(identity='ER-unrelated'); self.grant(unrelated)
        self.assertEqual(before, self.verify(first)['snapshot_sha256'])

    def test_rejected_or_historical_source_is_not_admissible_evidence(self):
        for state in ('rejected', 'historical_only'):
            metadata = self.metadata(); metadata['admissibility'] = state
            record = refs.register_reference(self.bank, metadata, commit=True)
            self.grant(record)
            with self.assertRaisesRegex(ModelError, 'SOURCE_INADMISSIBLE'):
                self.verify(record)

    def test_partial_reading_covers_only_explicit_verified_used_spans(self):
        raw = self.path.read_bytes()

        def span(start, end):
            return dict(start=start, end=end, sha256=sha256_bytes(raw[start:end]))
        metadata = self.metadata()
        metadata.update(reading_state='partial', read_spans=[span(0, 10), span(10, 20)])
        record = refs.register_reference(self.bank, metadata, commit=True); self.grant(record)
        with self.assertRaisesRegex(ModelError, 'READING_INCOMPLETE'):
            self.verify(record)
        used = refs.reference_ref(record, spans=[span(5, 15)])
        result = refs.verify_references(self.bank, [used], self.scope)
        self.assertEqual(result['references'][0]['reference']['spans'], [span(5, 15)])
        self.assertEqual(refs.read_reference(self.bank, record['reference_id'],
                                             record['version_id'])['reading_state'], 'partial')
        for invalid in (refs.reference_ref(record, spans=[span(15, 25)]),
                        refs.reference_ref(record, spans=[dict(start=0, end=10, sha256='0' * 64)])):
            with self.assertRaises(ModelError):
                refs.verify_references(self.bank, [used, invalid], self.scope)

    def test_partial_transitive_reference_does_not_gain_whole_file_reading(self):
        raw = self.path.read_bytes()
        span = dict(start=0, end=8, sha256=sha256_bytes(raw[:8]))
        metadata = self.metadata(); metadata.update(reading_state='partial', read_spans=[span])
        parent = refs.register_reference(self.bank, metadata, commit=True); self.grant(parent)
        child = self.register(identity='ER-child',
                              dependencies=[refs.reference_ref(parent, spans=[span])])
        self.grant(child)
        self.assertTrue(self.verify(child)['access_verified'])
        wrong = self.register(identity='ER-whole',
                              dependencies=[refs.reference_ref(parent)])
        self.grant(wrong)
        with self.assertRaisesRegex(ModelError, 'READING_INCOMPLETE'):
            self.verify(wrong)

    def test_record_and_grant_chain_tampering_rejected(self):
        record = self.register(); self.grant(record)
        path = self.bank / refs._record_path(record['version_id'])
        path.write_text(path.read_text(encoding='utf-8').replace('Synthetic owner', 'Altered'),
                        encoding='utf-8', newline='\n')
        with self.assertRaisesRegex(ModelError, 'RECORD_CHANGED'):
            self.verify(record)
        # The full chain is verified even when consulting another reference.
        permission = next((self.bank / refs.ROOT / 'permissions').glob('*.json'))
        permission.rename(permission.with_name('000000000002.json'))
        with self.assertRaisesRegex(ModelError, 'CHAIN_INVALID'):
            refs.external_decisions(self.bank)

    @unittest.skip('requires the upstream test_transcripciones_pipeline fixture; the transcript '
                   'custody + permission chain is covered in-process by tests/test_engine_transcripts.py')
    def test_transitive_transcript_permission_is_live(self):
        pass


if __name__ == '__main__':
    unittest.main()
