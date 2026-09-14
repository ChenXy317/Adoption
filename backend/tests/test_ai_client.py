"""ai_client 参数组装单元测试：生成参数透传与 num_predict 防御。"""
import unittest

from ai_client import AIClient


class BuildKwargsTest(unittest.TestCase):
    def test_params_passthrough(self):
        kwargs = AIClient._build_kwargs(
            [], "model", None, {"temperature": 0.5, "top_p": 0.9}, False
        )
        self.assertEqual(kwargs["temperature"], 0.5)
        self.assertEqual(kwargs["top_p"], 0.9)
        self.assertNotIn("max_tokens", kwargs)

    def test_num_predict_limits_max_tokens(self):
        kwargs = AIClient._build_kwargs([], "model", 8192, {"num_predict": 2048}, True)
        self.assertEqual(kwargs["max_tokens"], 2048)
        kwargs = AIClient._build_kwargs([], "model", 1024, {"num_predict": 2048}, True)
        self.assertEqual(kwargs["max_tokens"], 1024)

    def test_num_predict_zero_ignored(self):
        kwargs = AIClient._build_kwargs([], "model", None, {"num_predict": 0}, True)
        self.assertNotIn("max_tokens", kwargs)
        kwargs = AIClient._build_kwargs([], "model", 8192, {"num_predict": 0}, True)
        self.assertEqual(kwargs["max_tokens"], 8192)

    def test_num_predict_invalid_ignored(self):
        kwargs = AIClient._build_kwargs([], "model", None, {"num_predict": "bad"}, True)
        self.assertNotIn("max_tokens", kwargs)
        kwargs = AIClient._build_kwargs([], "model", None, {"num_predict": None}, True)
        self.assertNotIn("max_tokens", kwargs)

    def test_max_tokens_fallback(self):
        kwargs = AIClient._build_kwargs([], "model", 4096, {}, False)
        self.assertEqual(kwargs["max_tokens"], 4096)


if __name__ == "__main__":
    unittest.main()
