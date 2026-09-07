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

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
