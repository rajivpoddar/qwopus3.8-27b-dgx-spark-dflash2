"""CPU integration: actual adapter, grammar-manager budget and grammar transitions."""
import unittest
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch
import os
from sglang.srt.entrypoints.anthropic.serving import AnthropicServing
from sglang.srt.entrypoints.anthropic.protocol import AnthropicMessagesRequest
from sglang.srt.entrypoints.anthropic.compaction_policy import COMPACTION_SYSTEM
from sglang.srt.entrypoints.anthropic.effort_policy import BUDGETS
from sglang.srt.constrained.grammar_manager import GrammarManager
from sglang.srt.constrained.reasoner_grammar_backend import ReasonerGrammarObject


class Backend:
    tokenizer_manager = NS(server_args=NS(enable_strict_thinking=True, grammar_backend='xgrammar'))
    def apply_reasoning_enabled(self, request, enabled):
        request.chat_template_kwargs = {**(request.chat_template_kwargs or {}), 'enable_thinking': enabled}


class TestEffort(unittest.TestCase):
    def test_operator_force_off_wins(self):
        with patch.dict(os.environ, {'QWOPUS_FORCE_THINKING_OFF':'1', 'QWOPUS_EFFORT_BUDGETS':'0'}):
            for effort in BUDGETS:
                chat = self.convert(effort, thinking={'type':'enabled','budget_tokens':32768})
                self.assertFalse(chat.chat_template_kwargs['enable_thinking'])
                self.assertEqual(chat.custom_params['thinking_budget'], 0)
                self.assertEqual(chat.max_tokens, 40000)

    def convert(self, effort='low', **extra):
        adapter = AnthropicServing.__new__(AnthropicServing)
        adapter._merge_inline_system = False
        adapter.openai_serving_chat = Backend()
        data = dict(model='qwen3.8-27b', system='Coding assistant', max_tokens=40000,
                    messages=[{'role':'user','content':'Solve the task'}])
        if effort is not None:
            data['output_config'] = {'effort':effort}
        data.update(extra)
        return adapter._convert_to_chat_completion_request(AnthropicMessagesRequest(**data))

    def test_levels_and_real_grammar(self):
        for effort, budget in BUDGETS.items():
            chat = self.convert(effort)
            self.assertEqual(chat.custom_params['thinking_budget'], budget)
            mask = Mock()
            grammar = ReasonerGrammarObject(None, [99], enable_token_filter=True, token_filter_fn=mask)
            grammar.maybe_init_reasoning(True)
            manager = GrammarManager.__new__(GrammarManager)
            manager._apply_request_reasoning_budget(NS(grammar=grammar, sampling_params=NS(custom_params=chat.custom_params)))
            for _ in range(budget):
                grammar.accept_token(1)
            grammar.fill_vocab_mask(None, 0)
            mask.assert_called_once_with(None, [99], 0, True)
            grammar.accept_token(99)
            self.assertTrue(grammar._is_generation())
            grammar.accept_token(2)
            self.assertFalse(grammar.is_terminated())
            self.assertEqual(chat.max_tokens, 40000)

    def test_compaction_and_disabled(self):
        for extra in ({'system':COMPACTION_SYSTEM}, {'thinking':{'type':'disabled'}}):
            chat = self.convert('high', **extra)
            self.assertFalse(chat.chat_template_kwargs['enable_thinking'])

    def test_explicit_budget_and_headroom(self):
        self.assertEqual(self.convert('high', thinking={'type':'enabled','budget_tokens':2048}).custom_params['thinking_budget'], 2048)
        self.assertEqual(self.convert('high', max_tokens=1500).custom_params['thinking_budget'], 476)
        self.assertFalse(self.convert('high', max_tokens=512).chat_template_kwargs['enable_thinking'])
        self.assertEqual(self.convert(None).custom_params['thinking_budget'], 1024)


if __name__ == '__main__':
    unittest.main()
