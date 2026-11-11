import json
from pathlib import Path
import sys
import tempfile
import unittest
from reeltern.client_config import configuration


class ClientConfiguration(unittest.TestCase):
    def test_json_clients_preserve_paths_and_environment(self):
        with tempfile.TemporaryDirectory(prefix='reeltern config ') as temp:
            root = Path(temp)
            workspace = root / 'new project'
            for client in ('claude-code', 'cursor', 'vscode', 'generic'):
                value = json.loads(configuration(client, workspace, root))
                entry = value['servers' if client == 'vscode' else 'mcpServers']['reeltern']
                self.assertEqual(entry['command'], str(Path(sys.executable).absolute()))
                self.assertEqual(entry['args'][3:5], ['--workspace', str(workspace.resolve())])
                self.assertEqual(entry['args'][-1], str(root.resolve()))
            self.assertFalse(workspace.exists(), 'Printing configuration must not create a workspace')

    @unittest.skipIf(sys.version_info < (3, 11), 'TOML parser included in Python 3.11+')
    def test_codex_toml_roundtrip(self):
        import tomllib
        with tempfile.TemporaryDirectory(prefix='reeltern config ') as temp:
            entry = tomllib.loads(configuration('codex', Path(temp)/'project', temp, 'local-model:small'))['mcp_servers']['reeltern']
            self.assertEqual(entry['tool_timeout_sec'], 300)
            self.assertEqual(entry['args'][-2:], ['--agent-model', 'local-model:small'])
            self.assertEqual(entry['command'], str(Path(sys.executable).absolute()))

    def test_invalid_config_fails_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for client, media, model in [('unknown', root, None), ('codex', root/'missing', None), ('generic', root, 'model-cloud')]:
                with self.assertRaises(ValueError):
                    configuration(client, root/'new', media, model)
            self.assertEqual(list(root.iterdir()), [])
