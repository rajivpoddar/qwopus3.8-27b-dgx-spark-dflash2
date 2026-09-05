"""Offline launch-contract tests. All Docker/curl calls are mocked; no GPU needed."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


class ProfileTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        p = Path(self.tmp.name)
        self.p = p
        binary = p / 'bin'
        binary.mkdir()
        (binary / 'docker').write_text('''#!/usr/bin/env python3
import json, os, sys
a=sys.argv[1:]
if a[:2]==['container','inspect']:
    if '--format' in a:
        print(os.environ.get('PANGO_RUNNING','false')); sys.exit(0)
    sys.exit(0 if os.environ.get('EXISTS')=='1' else 1)
if a and a[0]=='run':
    with open(os.environ['CAPTURE'],'w') as f: json.dump(a,f)
if a and a[0]=='rm': sys.exit('unexpected destructive command')
''')
        (binary / 'curl').write_text('#!/bin/sh\nprintf 200\n')
        for file in binary.iterdir():
            file.chmod(0o755)
        sha = 'a' * 40
        self.snapshot = p / 'hf' / 'hub' / 'models--sojufx--Qwopus3.8-27B-Flash-NVFP4' / 'snapshots' / sha
        self.snapshot.mkdir(parents=True)
        for name in ('config.json', 'hf_quant_config.json', 'tokenizer.json'):
            (self.snapshot / name).write_text('{}')
        (self.snapshot / 'model.safetensors.index.json').write_text(json.dumps({'weight_map': {'weight': 'one.safetensors'}}))
        (self.snapshot / 'one.safetensors').write_text('mock weight')
        (self.snapshot / 'chat_template.jinja').write_text('(message.role == "system" and not loop.first) <tool_call>')
        (p / 'key').write_text('test-only-placeholder')
        self.env = {**os.environ, 'PATH': str(binary) + ':' + os.environ['PATH'],
                    'REVISION': sha, 'HF_CACHE': str(p / 'hf'), 'SGLANG_CACHE': str(p / 'tactics'),
                    'SPARK_API_KEY_FILE': str(p / 'key'), 'CAPTURE': str(p / 'args.json'),
                    'SPEC': '0', 'EXTRA_ARGS': '', 'PANGO_RUNNING': 'false', 'EXISTS': '0'}

    def launch(self, **env):
        return subprocess.run(['bash', str(ROOT / 'serve-qwopus.sh')], env={**self.env, **env},
                              capture_output=True, text=True, timeout=10)

    def test_target_only_launch(self):
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr)
        args = json.loads((self.p / 'args.json').read_text())
        for flag, value in {'--model-path': 'sojufx/Qwopus3.8-27B-Flash-NVFP4',
                            '--tool-call-parser': 'qwen', '--served-model-name': 'qwen3.8-27b',
                            '--mamba-full-memory-ratio': '0.9',
                            '--max-consecutive-prefill-batches': '1'}.items():
            self.assertEqual(args[args.index(flag) + 1], value)
        self.assertFalse(any(a.startswith('--speculative-') for a in args))
        thinking = json.loads(args[args.index('--default-chat-template-kwargs') + 1])
        self.assertEqual(thinking, {'enable_thinking': True, 'preserve_thinking': False})
        self.assertTrue(args[args.index('--chat-template') + 1].endswith('/' + 'a' * 40 + '/chat_template.jinja'))

    def test_reject_speculation(self):
        self.assertNotEqual(self.launch(SPEC='1').returncode, 0)
        self.assertFalse((self.p / 'args.json').exists())

    def test_reject_running_pango(self):
        self.assertIn('Pango is still running', self.launch(PANGO_RUNNING='true').stderr)
        self.assertFalse((self.p / 'args.json').exists())

    def test_preserve_existing_candidate(self):
        self.assertIn('already exists', self.launch(EXISTS='1').stderr)
        self.assertFalse((self.p / 'args.json').exists())

    def test_incomplete_snapshot(self):
        (self.snapshot / 'one.safetensors').unlink()
        self.assertIn('Incomplete cached weight shards', self.launch().stderr)
        self.assertFalse((self.p / 'args.json').exists())

    def test_invalid_revision(self):
        self.assertIn('full commit SHA', self.launch(REVISION='main').stderr)


if __name__ == '__main__':
    unittest.main()
