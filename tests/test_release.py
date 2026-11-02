"""Publication controls use synthetic fixtures, never real conversations or keys."""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'scripts' / 'validate_skill.py'


class BootstrapTests(unittest.TestCase):
    def test_installable_entry_has_no_scaffold_markers(self):
        text = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
        self.assertTrue(text.startswith('---\nname: social-reply\n'))
        self.assertNotIn('TODO', text)

    def test_release_validator_is_available(self):
        self.assertTrue(SCRIPT.is_file(), 'Publication validator is required')


class ReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not SCRIPT.is_file():
            raise unittest.SkipTest('Validator is not implemented yet')
        spec = importlib.util.spec_from_file_location('release_validator', SCRIPT)
        cls.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.module)

    def rules(self, text):
        return {item['rule'] for item in self.module.scan_text(text, 'sample.txt')}

    def test_complete_package_passes(self):
        self.assertEqual(self.module.validate_package(ROOT), [])

    def test_github_credential_is_rejected_without_echoing_value(self):
        value = 'gh' + 'p_' + 'Ab9' * 13
        issues = self.module.scan_text(value, 'sample.txt')
        self.assertIn('access-token', {x['rule'] for x in issues})
        self.assertNotIn(value, json.dumps(issues))

    def test_model_credential_is_rejected(self):
        value = 's' + 'k-proj-' + 'Ab12' * 12
        self.assertIn('access-token', self.rules(value))

    def test_bearer_secret_is_rejected(self):
        text = 'Authorization: Bearer ' + 'aB23' * 12
        self.assertIn('bearer-secret', self.rules(text))

    def test_secret_assignment_is_rejected(self):
        text = 'api_' + 'key = ' + 'ab12' * 8
        self.assertIn('secret-assignment', self.rules(text))

    def test_private_key_is_rejected(self):
        text = '-' * 5 + 'BEGIN PRIVATE KEY' + '-' * 5
        self.assertIn('private-key', self.rules(text))

    def test_private_library_locator_is_rejected(self):
        text = 'lib' + 'file_' + 'a1' * 16
        self.assertIn('private-locator', self.rules(text))

    def test_posix_machine_path_is_rejected(self):
        text = '/' + 'Users/' + 'sample-owner/Documents/private.txt'
        self.assertIn('absolute-path', self.rules(text))

    def test_windows_machine_path_is_rejected(self):
        text = 'C' + ':\\' + 'Users\\sample-owner\\private.txt'
        self.assertIn('absolute-path', self.rules(text))

    def test_email_is_rejected(self):
        text = 'sample' + '@' + 'example.invalid'
        self.assertIn('email-address', self.rules(text))

    def test_phone_number_is_rejected(self):
        text = '138' + '0000' + '0000'
        self.assertIn('phone-number', self.rules(text))

    def test_signed_url_is_rejected(self):
        text = 'https://example.invalid/result?' + 'sig=' + 'ab12' * 8
        self.assertIn('signed-url', self.rules(text))

    def test_jwt_is_rejected(self):
        text = 'ey' + 'J' + 'a' * 30 + '.' + 'b' * 30 + '.' + 'c' * 30
        self.assertIn('jwt', self.rules(text))

    def test_relative_resources_and_public_links_are_allowed(self):
        text = 'references/methods.md https://github.com/example/project/issues/1'
        self.assertEqual(self.module.scan_text(text, 'README.md'), [])

    def test_report_does_not_expose_input_content(self):
        text = 'password=' + 'sample-secret-value-1234'
        issues = self.module.scan_text(text, 'sample.txt')
        self.assertTrue(issues)
        self.assertTrue(all(set(x) == {'path', 'line', 'rule'} for x in issues))

    def test_json_secret_key_is_rejected(self):
        text = json.dumps({'api_' + 'key': 'Ab12' * 8})
        self.assertIn('secret-assignment', self.rules(text))

    def test_quoted_yaml_secret_key_is_rejected(self):
        text = '"pass' + 'word": "' + 'Ab12' * 8 + '"'
        self.assertIn('secret-assignment', self.rules(text))

    def test_server_machine_path_is_rejected(self):
        text = '/' + 'srv/' + 'team/notes.md'
        self.assertIn('absolute-path', self.rules(text))

    def test_unc_machine_path_is_rejected(self):
        text = '\\' * 2 + 'sample-server' + '\\' + 'share' + '\\' + 'notes.md'
        self.assertIn('absolute-path', self.rules(text))

    def test_formatted_phone_is_rejected(self):
        text = '138' + ' 0000' + ' 0000'
        self.assertIn('phone-number', self.rules(text))

    def test_international_phone_is_rejected(self):
        text = '+' + '1 202' + ' 555' + ' 0100'
        self.assertIn('phone-number', self.rules(text))

    def test_phone_adjacent_to_chinese_is_rejected(self):
        text = '电话' + '138' + '0000' + '0000' + '联系我'
        self.assertIn('phone-number', self.rules(text))

    def test_formatted_phone_in_chinese_document_is_rejected(self):
        target = self.fixture()
        with (target / 'README.md').open('a', encoding='utf-8') as f:
            f.write('\n电话' + '138' + ' 0000' + ' 0000' + '联系我')
        self.assertIn('phone-number', {x['rule'] for x in self.module.validate_package(target)})

    def fixture(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        target = Path(tmp.name) / 'clean install with spaces'
        shutil.copytree(ROOT, target, ignore=shutil.ignore_patterns('__pycache__'))
        return target

    def test_clean_install_in_different_directory(self):
        target = self.fixture()
        result = subprocess.run([sys.executable, '-B', str(target / 'scripts' / 'validate_skill.py')], cwd=target.parent, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'passed')

    def test_unexpected_private_file_is_rejected(self):
        target = self.fixture()
        (target / '.env').write_text('synthetic fixture only', encoding='utf-8')
        self.assertIn('unexpected-file', {x['rule'] for x in self.module.validate_package(target)})

    def test_unexpected_filename_is_not_disclosed(self):
        target = self.fixture()
        sensitive_name = 'sample' + '@' + 'example.invalid' + '.txt'
        (target / sensitive_name).write_text('synthetic fixture', encoding='utf-8')
        report = self.module.validate_package(target)
        self.assertTrue(report)
        self.assertNotIn(sensitive_name, json.dumps(report))

    def test_json_secret_in_allowed_file_is_rejected(self):
        target = self.fixture()
        with (target / 'README.md').open('a', encoding='utf-8') as f:
            f.write('\n' + json.dumps({'pass' + 'word': 'Ab12' * 8}))
        self.assertIn('secret-assignment', {x['rule'] for x in self.module.validate_package(target)})

    def test_missing_reference_is_rejected(self):
        target = self.fixture()
        (target / 'references' / 'methods.md').unlink()
        self.assertIn('missing-resource', {x['rule'] for x in self.module.validate_package(target)})

    def test_escaping_resource_link_is_rejected(self):
        target = self.fixture()
        with (target / 'SKILL.md').open('a', encoding='utf-8') as f:
            f.write('\n[bad resource](../outside.md)\n')
        self.assertIn('unsafe-link', {x['rule'] for x in self.module.validate_package(target)})

    def test_missing_reference_style_resource_is_rejected(self):
        target = self.fixture()
        with (target / 'SKILL.md').open('a', encoding='utf-8') as f:
            f.write('\n[read][extra]\n\n[extra]: references/not-present.md\n')
        self.assertIn('missing-resource', {x['rule'] for x in self.module.validate_package(target)})

    def test_reference_style_escape_is_rejected(self):
        target = self.fixture()
        with (target / 'SKILL.md').open('a', encoding='utf-8') as f:
            f.write('\n[read][extra]\n\n[extra]: ../outside.md\n')
        self.assertIn('unsafe-link', {x['rule'] for x in self.module.validate_package(target)})

    def test_undefined_reference_label_is_rejected(self):
        target = self.fixture()
        with (target / 'SKILL.md').open('a', encoding='utf-8') as f:
            f.write('\n[read][not-defined]\n')
        self.assertIn('missing-resource', {x['rule'] for x in self.module.validate_package(target)})

    def test_symlink_is_rejected(self):
        target = self.fixture()
        link = target / 'references' / 'leak.md'
        try:
            link.symlink_to(target / 'SKILL.md')
        except OSError:
            self.skipTest('Symlink creation is unavailable on this platform')
        self.assertIn('symlink', {x['rule'] for x in self.module.validate_package(target)})

    def test_binary_payload_is_rejected(self):
        target = self.fixture()
        (target / 'references' / 'methods.md').write_bytes(b'not-text\x00payload')
        self.assertIn('binary-content', {x['rule'] for x in self.module.validate_package(target)})

    def test_real_secret_in_allowed_document_is_rejected(self):
        target = self.fixture()
        with (target / 'README.md').open('a', encoding='utf-8') as f:
            f.write('\n' + 'gh' + 'p_' + 'Ab9' * 13)
        self.assertIn('access-token', {x['rule'] for x in self.module.validate_package(target)})

    def test_command_metadata_matches_skill_name(self):
        target = self.fixture()
        file = target / 'agents' / 'openai.yaml'
        file.write_text(file.read_text(encoding='utf-8').replace('$social-reply', '$wrong-skill'), encoding='utf-8')
        self.assertIn('invocation-mismatch', {x['rule'] for x in self.module.validate_package(target)})

    def test_missing_scenario_expectations_are_rejected(self):
        target = self.fixture()
        file = target / 'tests' / 'scenarios.json'
        rows = json.loads(file.read_text(encoding='utf-8'))
        rows[0].pop('checks')
        file.write_text(json.dumps(rows, ensure_ascii=False), encoding='utf-8')
        self.assertIn('invalid-scenarios', {x['rule'] for x in self.module.validate_package(target)})


if __name__ == '__main__':
    unittest.main()
