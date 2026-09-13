# manual_processor/tests/test_gemini_processor.py
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.gemini_processor import (
    GeminiProcessor,
    GeminiResult,
    GeminiAPIError
)
from src.text_processor import Section
from src.prompt_engine.prompt_builder import HandwrittenPromptBuilder, PromptConfig

class TestGeminiProcessor:
    """GeminiProcessor クライアント移行後の GeminiProcessor クラスのテスト"""

    def test_gemini_processor_initialization_success(self):
        """正常な初期化ができること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            
            processor = GeminiProcessor(api_key="test-key", model_name="gemini-2.0-flash")
            assert processor.model_name == "gemini-2.0-flash"
            assert processor.temperature == 0.3
            assert processor.max_output_tokens == 2048
            mock_client_class.assert_called_once_with(api_key="test-key")

    def test_gemini_processor_initialization_no_api_key(self):
        """APIキーがない場合にエラーになること"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(GeminiAPIError, match="Gemini APIキーが設定されていません"):
                GeminiProcessor(api_key=None)

    def test_chunk_text_short(self):
        """短いテキストはチャンク分割されないこと"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            chunks = processor._chunk_text("短いテキスト")
            assert chunks == ["短いテキスト"]

    def test_chunk_text_long(self):
        """長いテキストはチャンク分割されること"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            long_text = "段落1\n\n" * 2000  # 長いテキストを作成
            chunks = processor._chunk_text(long_text, max_tokens=1000)
            assert len(chunks) > 1

    def test_summarize_text_empty(self):
        """空のテキストを要約すると空文字が返ること"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            result = processor.summarize_text("")
            assert result == ""

    def test_summarize_text_success(self):
        """正常な要約ができること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = "要約結果: これはテストです。"
            mock_client_instance.models.generate_content.return_value = mock_response
            
            processor = GeminiProcessor(api_key="test-key")
            result = processor.summarize_text("テストテキスト", target_audience="beginner")
            
            assert "要約結果" in result
            mock_client_instance.models.generate_content.assert_called_once()

    def test_summarize_text_uses_handwritten_context(self):
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = "要約結果"
            mock_client_instance.models.generate_content.return_value = mock_response

            builder = HandwrittenPromptBuilder(PromptConfig(
                layout="vertical",
                domain_terms=["固有名詞"],
            ))
            processor = GeminiProcessor(api_key="test-key", prompt_builder=builder)

            processor.summarize_text("テストテキスト")

            prompt = mock_client_instance.models.generate_content.call_args.kwargs["contents"]
            assert "縦書き" in prompt
            assert "固有名詞" in prompt

    def test_summarize_text_multiple_chunks(self):
        """複数チャンクに分割された場合、各チャンクが要約されること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            
            mock_response1 = Mock()
            mock_response1.text = "要約1"
            mock_response2 = Mock()
            mock_response2.text = "要約2"
            
            mock_client_instance.models.generate_content.side_effect = [mock_response1, mock_response2]
            
            processor = GeminiProcessor(api_key="test-key")
            long_text = "段落1\n\n" * 2000
            result = processor.summarize_text(long_text, max_tokens=100)
            
            assert "要約1" in result
            assert "要約2" in result
            assert mock_client_instance.models.generate_content.call_count == 2

    def test_summarize_text_api_error(self):
        """APIエラー時にGeminiAPIErrorが送出されること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_client_instance.models.generate_content.side_effect = Exception("API Error")
            
            processor = GeminiProcessor(api_key="test-key")
            with pytest.raises(GeminiAPIError, match="テキスト要約に失敗しました"):
                processor.summarize_text("テストテキスト")

    def test_extract_key_points_empty(self):
        """空のテキストの場合は空リストを返すこと"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            result = processor.extract_key_points("")
            assert result == []

    def test_extract_key_points_success(self):
        """正常なキーポイント抽出ができること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = "- ポイント1\n- ポイント2\n- ポイント3"
            mock_client_instance.models.generate_content.return_value = mock_response
            
            processor = GeminiProcessor(api_key="test-key")
            result = processor.extract_key_points("テストテキスト", max_points=10)
            
            assert len(result) == 3
            assert "ポイント1" in result[0]
            assert "ポイント2" in result[1]
            assert "ポイント3" in result[2]

    def test_extract_key_points_filters_markers(self):
        """様々な箇条書きマーカーを除去すること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = "• ポイントA\n- ポイントB\n* ポイントC"
            mock_client_instance.models.generate_content.return_value = mock_response
            
            processor = GeminiProcessor(api_key="test-key")
            result = processor.extract_key_points("テストテキスト")
            
            assert "ポイントA" in result[0]
            assert "ポイントB" in result[1]
            assert "ポイントC" in result[2]

    def test_extract_key_points_max_limit(self):
        """最大ポイント数で制限されること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = "\n".join([f"- ポイント{i}" for i in range(15)])
            mock_client_instance.models.generate_content.return_value = mock_response
            
            processor = GeminiProcessor(api_key="test-key")
            result = processor.extract_key_points("テストテキスト", max_points=5)
            
            assert len(result) == 5

    def test_extract_key_points_api_error(self):
        """APIエラー時にGeminiAPIErrorが送出されること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_client_instance.models.generate_content.side_effect = Exception("API Error")
            
            processor = GeminiProcessor(api_key="test-key")
            with pytest.raises(GeminiAPIError, match="キーポイント抽出に失敗しました"):
                processor.extract_key_points("テストテキスト")

    def test_process_document_empty(self):
        """空のテキストを処理すると空の結果が返ること"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            result = processor.process_document("")
            
            assert isinstance(result, GeminiResult)
            assert result.summary == ""
            assert result.key_points == []
            assert result.sections == []

    def test_process_document_success(self):
        """正常なドキュメント処理ができること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            
            # 要約用のモック
            mock_summary_response = Mock()
            mock_summary_response.text = "ドキュメントの要約"
            
            # キーポイント用のモック
            mock_keypoints_response = Mock()
            mock_keypoints_response.text = "- キー1\n- キー2"
            
            mock_client_instance.models.generate_content.side_effect = [
                mock_summary_response,
                mock_keypoints_response
            ]
            
            processor = GeminiProcessor(api_key="test-key")
            result = processor.process_document("ドキュメントのテキスト", target_audience="beginner")
            
            assert isinstance(result, GeminiResult)
            assert result.summary == "ドキュメントの要約"
            assert result.key_points == ["キー1", "キー2"]
            assert result.difficulty_level == "beginner"
            assert len(result.sections) == 2
            assert result.sections[0].title == "概要"
            assert result.sections[1].title == "重要ポイント"

    def test_generate_title_success(self):
        """正常にタイトル生成ができること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = "テストマニュアル"
            mock_client_instance.models.generate_content.return_value = mock_response

            processor = GeminiProcessor(api_key="test-key")
            result = processor.generate_title("これはテストテキストです")
            assert result == "テストマニュアル"

    def test_generate_title_empty_text(self):
        """空テキストでデフォルトタイトルが返ること"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            result = processor.generate_title("")
            assert result == "処理済みマニュアル"

    def test_generate_title_exception(self):
        """タイトル生成でエラー時にデフォルトが返ること"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_client_instance.models.generate_content.side_effect = Exception("API Error")

            processor = GeminiProcessor(api_key="test-key")
            result = processor.generate_title("some text")
            assert result == "手書き整理マニュアル"

    def test_convert_sections_empty(self):
        """空セクションの変換"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            result = processor._convert_sections([])
            assert result == []

    def test_convert_sections_with_nested(self):
        """ネストしたセクションの変換"""
        with patch('src.gemini_processor.genai.Client'):
            processor = GeminiProcessor(api_key="test-key")
            sections_data = [
                {"title": "Sec1", "content": "Content1", "subsections": [
                    {"title": "Sub1", "content": "SubContent1"}
                ]}
            ]
            result = processor._convert_sections(sections_data)
            assert len(result) == 1
            assert result[0].title == "Sec1"
            assert result[0].subsections is not None
            assert len(result[0].subsections) == 1
            assert result[0].subsections[0].title == "Sub1"

    def test_process_document_text_markers_success(self):
        """テキストマーカーフォーマットの処理"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = """[TITLE]
テストタイトル

[SUMMARY]
これはテストサマリーです。

[KEY_POINTS]
- ポイント1
- ポイント2

[SECTIONS]
## セクション1
セクション1の本文

[GLOSSARY]
- 用語: 解説
"""
            mock_client_instance.models.generate_content.return_value = mock_response

            processor = GeminiProcessor(api_key="test-key")
            result = processor._process_document_text_markers("テストテキスト")

            assert result.title == "テストタイトル"
            assert result.summary == "これはテストサマリーです。"
            assert "ポイント1" in result.key_points
            assert len(result.sections) >= 1

    def test_process_document_text_markers_only_sections(self):
        """SECTIONSのみの場合 - パースされずデフォルト値が返る"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_response = Mock()
            mock_response.text = """[SECTIONS]
## Sec1
content
"""
            mock_client_instance.models.generate_content.return_value = mock_response

            processor = GeminiProcessor(api_key="test-key")
            result = processor._process_document_text_markers("テスト")
            assert result.title == "手書き整理マニュアル"
            assert result.sections == []
            assert result.summary == ""
            assert result.key_points == []

    def test_generate_with_retry_raises(self):
        """リトライでもエラーが発生する場合"""
        with patch('src.gemini_processor.genai.Client') as mock_client_class:
            mock_client_instance = mock_client_class.return_value
            mock_client_instance.models.generate_content.side_effect = Exception("API Error")

            processor = GeminiProcessor(api_key="test-key")
            with pytest.raises(GeminiAPIError):
                processor._generate_with_retry("test prompt")

class TestGeminiProcessorCoverageStep8:
    """Step 8: gemini_processor.py 未到達行のカバレッジテスト"""

    def _make_processor(self):
        with patch('src.gemini_processor.genai.Client'):
            return GeminiProcessor(api_key="test-key")

    # ---------- L102: _chunk_text 空テキスト ----------
    def test_chunk_text_empty_returns_empty_list(self):
        """空テキストは空リストを返すこと"""
        processor = self._make_processor()
        assert processor._chunk_text("") == []
        assert processor._chunk_text("   ") == []

    # ---------- L69-73: __init__ 例外パス ----------
    def test_init_generic_error_wrapped(self):
        """初期化中の予期せぬ例外は GeminiAPIError でラップされること"""
        with patch('src.gemini_processor.genai.Client', side_effect=Exception("init boom")):
            with pytest.raises(GeminiAPIError, match="Gemini API initialization failed"):
                GeminiProcessor(api_key="test-key")

    def test_init_gemini_api_error_reraised(self):
        """初期化中の GeminiAPIError はそのまま再送出されること"""
        with patch('src.gemini_processor.genai.Client', side_effect=GeminiAPIError("直接エラー")):
            with pytest.raises(GeminiAPIError, match="直接エラー"):
                GeminiProcessor(api_key="test-key")

    # ---------- L165, L178: summarize_text 分岐 ----------
    def test_summarize_cancel_token_checked_per_chunk(self):
        """チャンクごとに cancel_token がチェックされること"""
        processor = self._make_processor()
        cancel_token = Mock()
        with patch.object(processor, '_chunk_text', return_value=["チャンク1"]), \
             patch.object(processor, '_generate_with_retry', return_value="要約"):
            result = processor.summarize_text("テキスト", cancel_token=cancel_token)
        assert result == "要約"
        cancel_token.throw_if_cancelled.assert_called()

    def test_summarize_empty_summaries_returns_empty(self):
        """生成結果が空の場合、空文字を返すこと"""
        processor = self._make_processor()
        with patch.object(processor, '_chunk_text', return_value=["チャンク1"]), \
             patch.object(processor, '_generate_with_retry', return_value=""):
            result = processor.summarize_text("テキスト")
        assert result == ""

    # ---------- L189-197: 3チャンク以上の Map-Reduce 統合 ----------
    def test_summarize_multi_chunk_map_reduce(self):
        """3チャンク以上の場合、最終統合が行われること"""
        processor = self._make_processor()
        cancel_token = Mock()
        with patch.object(processor, '_chunk_text',
                          return_value=["c1", "c2", "c3"]), \
             patch.object(processor, '_generate_with_retry',
                          side_effect=["s1", "s2", "s3", "統合要約"]):
            result = processor.summarize_text("長いテキスト", cancel_token=cancel_token)
        assert result == "統合要約"

    # ---------- L201: summarize_text キャンセル時の再送出 ----------
    def test_summarize_cancelled_reraises_original(self):
        """キャンセルされた場合は元の例外が再送出されること"""
        processor = self._make_processor()
        cancel_token = Mock()
        cancel_token.is_cancelled = True
        with patch.object(processor, '_chunk_text', return_value=["c1"]), \
             patch.object(processor, '_generate_with_retry',
                          side_effect=Exception("キャンセル")):
            with pytest.raises(Exception, match="キャンセル"):
                processor.summarize_text("テキスト", cancel_token=cancel_token)

    # ---------- L213, L242: extract_key_points 分岐 ----------
    def test_extract_key_points_cancel_token_checked(self):
        """cancel_token がチェックされること"""
        processor = self._make_processor()
        cancel_token = Mock()
        with patch.object(processor, '_generate_with_retry',
                          return_value="- ポイント1\n- ポイント2"):
            points = processor.extract_key_points("テキスト", cancel_token=cancel_token)
        assert points == ["ポイント1", "ポイント2"]
        cancel_token.throw_if_cancelled.assert_called_once()

    def test_extract_key_points_cancelled_reraises(self):
        """キャンセルされた場合は元の例外が再送出されること"""
        processor = self._make_processor()
        cancel_token = Mock()
        cancel_token.is_cancelled = True
        with patch.object(processor, '_generate_with_retry',
                          side_effect=Exception("キャンセル")):
            with pytest.raises(Exception, match="キャンセル"):
                processor.extract_key_points("テキスト", cancel_token=cancel_token)

    # ---------- L252, L279-285: process_document 分岐 ----------
    def test_process_document_cancel_token_checked(self):
        """cancel_token がチェックされること"""
        processor = self._make_processor()
        cancel_token = Mock()
        with patch.object(processor, 'summarize_text', return_value="要約"), \
             patch.object(processor, 'extract_key_points', return_value=["k"]):
            result = processor.process_document("テキスト", cancel_token=cancel_token)
        assert result.summary == "要約"
        cancel_token.throw_if_cancelled.assert_called_once()

    def test_process_document_gemini_api_error_reraised(self):
        """GeminiAPIError はそのまま再送出されること"""
        processor = self._make_processor()
        with patch.object(processor, 'summarize_text',
                          side_effect=GeminiAPIError("要約エラー")):
            with pytest.raises(GeminiAPIError, match="要約エラー"):
                processor.process_document("テキスト")

    def test_process_document_cancelled_reraises_original(self):
        """キャンセルされた場合は元の例外が再送出されること"""
        processor = self._make_processor()
        cancel_token = Mock()
        cancel_token.is_cancelled = True
        with patch.object(processor, 'summarize_text',
                          side_effect=ValueError("中断")):
            with pytest.raises(ValueError, match="中断"):
                processor.process_document("テキスト", cancel_token=cancel_token)

    def test_process_document_generic_error_wrapped(self):
        """予期せぬ例外は GeminiAPIError でラップされること"""
        processor = self._make_processor()
        with patch.object(processor, 'summarize_text',
                          side_effect=ValueError("予期せぬエラー")):
            with pytest.raises(GeminiAPIError, match="ドキュメント処理に失敗しました"):
                processor.process_document("テキスト")

    # ---------- L378, L384: text マーカーパーサ分岐 ----------
    def test_text_markers_without_glossary_multiple_sections(self):
        """[GLOSSARY] なし・複数セクションのマーカーテキストをパースできること"""
        processor = self._make_processor()
        marker_text = (
            "[TITLE]\n"
            "テストタイトル\n"
            "[SUMMARY]\n"
            "サマリーです。\n"
            "[KEY_POINTS]\n"
            "- ポイント1\n"
            "[SECTIONS]\n"
            "## 1. 準備\n"
            "内容A\n"
            "## 2. 実行\n"
            "内容B\n"
        )
        with patch.object(processor, '_generate_with_retry', return_value=marker_text):
            result = processor._process_document_text_markers("入力")
        assert result.title == "テストタイトル"
        assert result.summary == "サマリーです。"
        assert result.key_points == ["ポイント1"]
        assert result.glossary == []
        assert len(result.sections) == 2
        assert result.sections[0].title == "1. 準備"
        assert result.sections[0].content == "内容A"
        assert result.sections[1].title == "2. 実行"
        assert result.sections[1].content == "内容B"

    # ---------- L397: タイトルが空の場合の自動生成 ----------
    def test_text_markers_empty_title_generates_title(self):
        """タイトルが空の場合 generate_title で自動生成されること"""
        processor = self._make_processor()
        marker_text = (
            "[TITLE]\n"
            "\n"
            "[SUMMARY]\n"
            "サマリーです。\n"
            "[KEY_POINTS]\n"
            "- ポイント1\n"
            "[SECTIONS]\n"
            "## 1. 準備\n"
            "内容\n"
        )
        with patch.object(processor, '_generate_with_retry', return_value=marker_text), \
             patch.object(processor, 'generate_title', return_value="自動生成タイトル") as mock_gt:
            result = processor._process_document_text_markers("入力")
        mock_gt.assert_called_once()
        assert result.title == "自動生成タイトル"


class TestModuleImportFallbackStep8:
    """モジュールレベル import 分岐のテスト (L14-16, L66-67, L91-92)"""

    def test_genai_import_fallback_uses_generativeai(self):
        """google.genai が使えない場合 google.generativeai へフォールバックすること"""
        import importlib
        import sys
        import types
        import src.gemini_processor as gemini_mod

        original_processor_cls = gemini_mod.GeminiProcessor
        original_result_cls = gemini_mod.GeminiResult

        saved = {
            name: sys.modules[name]
            for name in ("google", "google.genai", "google.generativeai")
            if name in sys.modules
        }

        fake_google = types.ModuleType("google")
        fake_gg = types.ModuleType("google.generativeai")
        fake_gg.configure = Mock()
        fake_gg.GenerativeModel = Mock()

        try:
            sys.modules["google"] = fake_google
            # NOTE: sys.modules["google.genai"] = None では CPython が None を
            # 返してしまうため ImportError にならない。genai を sys.modules から
            # 削除し、親 fake モジュールに __path__ を与えないことで
            # 「cannot import name 'genai' from 'google'」の ImportError を発生させる。
            sys.modules.pop("google.genai", None)  # from google import genai -> ImportError
            sys.modules["google.generativeai"] = fake_gg
            importlib.reload(gemini_mod)

            assert gemini_mod._HAS_GENAI is False

            # L66-67: genai.configure + GenerativeModel パス
            processor = gemini_mod.GeminiProcessor(
                api_key="fallback-key", model_name="fallback-model")
            fake_gg.configure.assert_called_once_with(api_key="fallback-key")
            fake_gg.GenerativeModel.assert_called_once_with("fallback-model")

            # L91-92: self.model.generate_content パス
            fake_model = fake_gg.GenerativeModel.return_value
            fake_response = Mock()
            fake_response.text = "  フォールバック結果  "
            fake_model.generate_content.return_value = fake_response
            result = processor._generate_with_retry("prompt")
            assert result == "フォールバック結果"
        finally:
            for name in ("google", "google.genai", "google.generativeai"):
                if name in saved:
                    sys.modules[name] = saved[name]
                else:
                    sys.modules.pop(name, None)
            importlib.reload(gemini_mod)
            # クラス同一性を復元（他テストモジュールが保持する参照を保護）
            gemini_mod.GeminiProcessor = original_processor_cls
            gemini_mod.GeminiResult = original_result_cls


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
