import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from compaction_policy import COMPACTION_SYSTEM, apply_compaction_policy, is_compaction


class CompactionPolicyTest(unittest.TestCase):
    def test_exact_system_forms(self):
        for system in (COMPACTION_SYSTEM, ' ' + COMPACTION_SYSTEM + '\n',
                       [{'type': 'text', 'text': COMPACTION_SYSTEM, 'cache_control': {'type': 'ephemeral'}}],
                       [NS(type='text', text=COMPACTION_SYSTEM)]):
            self.assertTrue(is_compaction(system))

    def test_fail_closed(self):
        for system in (None, [], {}, 'Summarize this conversation',
                       'Normal coding prompt ' + COMPACTION_SYSTEM,
                       COMPACTION_SYSTEM + ' extra instructions',
                       [{'type': 'image', 'text': COMPACTION_SYSTEM}],
                       [NS(type='text', text=COMPACTION_SYSTEM), NS(type='text', text='extra')]):
            self.assertFalse(is_compaction(system))

    def test_explicit_disable_even_when_client_enables(self):
        for thinking in (None, NS(type='enabled'), NS(type='adaptive'), NS(type='disabled')):
            serving, chat = Mock(), NS(max_tokens=16000)
            request = NS(system=COMPACTION_SYSTEM, thinking=thinking)
            self.assertTrue(apply_compaction_policy(request, chat, serving))
            serving.apply_reasoning_enabled.assert_called_once_with(chat, False)
            self.assertEqual(chat.max_tokens, 16000)

    def test_user_text_cannot_trigger(self):
        serving = Mock()
        request = NS(system='You are a coding assistant.', messages=[COMPACTION_SYSTEM])
        self.assertFalse(apply_compaction_policy(request, NS(), serving))
        serving.apply_reasoning_enabled.assert_not_called()


if __name__ == '__main__':
    unittest.main()
