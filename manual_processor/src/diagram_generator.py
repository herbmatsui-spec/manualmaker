"""
Diagram Generator Module
Creates flowchart/process diagrams from structured manual content using Mermaid.js
"""

import logging
from pathlib import Path
from typing import Optional, List
from dataclasses import dataclass

try:
    from google import genai
    _HAS_GENAI = True
except ImportError:
    _HAS_GENAI = False
    import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class DiagramResult:
    """ダイアグラム生成結果"""
    mermaid_code: str          # 生成された Mermaid 記法のコード
    image_path: Optional[Path] # レンダリングされた画像のパス（PNG）
    diagram_type: str          # "flowchart", "sequence", "mindmap" 等
    success: bool              # 生成成功フラグ
    error_message: str = ""    # エラー時のメッセージ
    markdown_path: Optional[Path] = None  # Markdown ファイルパス (.md)
    mermaid_path: Optional[Path] = None   # Mermaid ファイルパス (.mmd)


class DiagramGenerator:
    """Mermaid.js を使用してフローチャート・構造図を生成するクラス"""

    def __init__(self, api_key: str, model_name: str = "gemini-3.1-flash-lite"):
        """
        Args:
            api_key: Gemini API キー
            model_name: 使用する Gemini モデル名
        """
        self.api_key = api_key
        self.model_name = model_name
        if _HAS_GENAI:
            self.client = genai.Client(api_key=self.api_key)
        else:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel(self.model_name)
        logger.info(f"DiagramGenerator initialized ({self.model_name})")

    def render_to_image(self, mermaid_code: str, output_path: Path,
                        theme: str = "default",
                        width: int = 800, height: int = 600) -> Path:
        """
        Mermaid コードを PNG 画像にレンダリング

        Args:
            mermaid_code: Mermaid 記法の文字列
            output_path: 出力ファイルパス (.png)
            theme: テーマ名 (default, dark, forest, neutral)
            width: 画像幅
            height: 画像高さ

        Returns:
            生成された画像ファイルのパス

        Raises:
            DiagramGenerationError: レンダリング失敗時
        """
        from src.exceptions import DiagramGenerationError

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Pattern 1: mermaidx.render(code, output=path)
            try:
                from mermaidx import render as mermaid_render
                mermaid_render(mermaid_code, output=str(output_path), theme=theme,
                               width=width, height=height)
                logger.info(f"Mermaid diagram rendered (mermaidx.render): {output_path}")
                return output_path
            except (ImportError, TypeError, Exception) as e1:
                logger.debug(f"mermaidx.render attempt failed: {e1}")

            # Pattern 2: mermaidx.Mermaid class
            try:
                from mermaidx import Mermaid
                m = Mermaid(mermaid_code)
                m.to_png(str(output_path))
                logger.info(f"Mermaid diagram rendered (Mermaid.to_png): {output_path}")
                return output_path
            except (ImportError, AttributeError, Exception) as e2:
                logger.debug(f"Mermaid.to_png attempt failed: {e2}")

            # Pattern 3: subprocess で mmdc CLI を試行
            import subprocess
            result = subprocess.run(
                ["mmdc", "-i", "-", "-o", str(output_path), "-t", theme,
                 "-w", str(width), "-H", str(height)],
                input=mermaid_code, capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                logger.info(f"Mermaid diagram rendered (mmdc CLI): {output_path}")
                return output_path
            else:
                raise DiagramGenerationError(f"mmdc CLI failed: {result.stderr}")

        except DiagramGenerationError:
            raise
        except Exception as e:
            logger.error(f"All Mermaid rendering methods failed: {e}")
            raise DiagramGenerationError(f"Mermaid レンダリング失敗（全手段不可）: {e}")

    def _create_fallback_image(self, text_lines: List[str], output_path: Path,
                               width: int = 800, height: int = 600) -> Path:
        """
        Mermaid レンダリングが不可能な場合、Pillow でシンプルなフロー図画像を生成
        """
        from PIL import Image, ImageDraw, ImageFont

        img = Image.new("RGB", (width, height), color=(255, 255, 255))
        draw = ImageDraw.Draw(img)

        # フォント（日本語対応）
        font = None
        import os
        for candidate in [
            "C:/Windows/Fonts/msgothic.ttc",
            "C:/Windows/Fonts/meiryo.ttc",
            "C:/Windows/Fonts/msmincho.ttc"
        ]:
            if os.path.exists(candidate):
                try:
                    font = ImageFont.truetype(candidate, 14)
                    break
                except Exception:
                    continue
        if font is None:
            font = ImageFont.load_default()

        # タイトル
        draw.text((width // 2 - 60, 15), "📋 作業フロー図", fill=(0, 0, 0), font=font)

        # 各ステップをボックスで描画
        y = 55
        box_width = width - 100
        box_height = 35
        for i, step in enumerate(text_lines[:10]):
            x = 50
            if i > 0:
                arrow_x = width // 2
                draw.line([(arrow_x, y - 5), (arrow_x, y + 5)], fill=(100, 100, 100), width=2)
                draw.polygon([(arrow_x - 5, y + 2), (arrow_x + 5, y + 2), (arrow_x, y + 8)],
                             fill=(100, 100, 100))
                y += 10

            draw.rounded_rectangle(
                [(x, y), (x + box_width, y + box_height)],
                radius=8, outline=(70, 130, 180), width=2, fill=(240, 248, 255)
            )
            step_text = f"{i + 1}. {step[:40]}"
            draw.text((x + 10, y + 8), step_text, fill=(0, 0, 0), font=font)
            y += box_height + 8

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path))
        logger.info(f"Fallback diagram image created: {output_path}")
        return output_path

    def generate_mermaid_code(self, text: str, sections: list,
                              key_points: list) -> str:
        """
        Gemini API を使ってマニュアル内容から Mermaid フローチャートコードを生成
        """
        sections_text = ""
        for i, sec in enumerate(sections, 1):
            sections_text += f"\n{i}. {sec.get('title', '')}\n{sec.get('content', '')}\n"

        key_points_text = "\n".join(f"- {kp}" for kp in key_points) if key_points else "なし"

        prompt = f"""以下のマニュアルの内容を分析し、作業手順のフローチャートを Mermaid 記法で生成してください。

## ルール
1. 必ず `flowchart TD` で始めてください（上から下方向のフローチャート）
2. ノードIDは A, B, C... のようにシンプルな英字にしてください
3. ノードのラベルは日本語で、簡潔に（20文字以内）記述してください
4. 条件分岐がある場合は菱形ノード {{条件}} を使ってください
5. Mermaid コードのみを出力してください（説明文やマークダウン記法は不要）
6. ノード数は最大15個までにしてください

## マニュアル内容

### セクション
{sections_text}

### 重要ポイント
{key_points_text}

## 出力例
flowchart TD
    A[準備: 材料を用意する] --> B[ステップ1: 電源を入れる]
    B --> C{{ランプが点灯したか?}}
    C -->|はい| D[ステップ2: 設定を確認]
    C -->|いいえ| E[電源コードを確認]
    E --> B
    D --> F[完了]
"""

        try:
            if _HAS_GENAI:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt
                )
                result = response.text.strip() if response.text else ""
            else:
                response = self.model.generate_content(prompt)
                result = response.text.strip() if response.text else ""

            if result.startswith("```"):
                result = result.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

            return result

        except Exception as e:
            logger.error(f"Mermaid code generation failed: {e}")
            raise

    @staticmethod
    def validate_mermaid_code(code: str) -> tuple:
        """
        Mermaid コードの基本構文を検証

        Returns:
            (is_valid: bool, error_message: str)
        """
        if not code or not code.strip():
            return False, "空のMermaidコード"

        lines = code.strip().split('\n')
        first_line = lines[0].strip().lower()

        valid_starts = ['flowchart', 'graph', 'sequencediagram', 'mindmap',
                        'flowchart td', 'flowchart lr', 'graph td', 'graph lr']
        if not any(first_line.startswith(vs) for vs in valid_starts):
            return False, f"無効な開始行: {first_line}"

        has_node = False
        for line in lines[1:]:
            stripped = line.strip()
            if stripped and ('-->' in stripped or '---' in stripped or '[' in stripped):
                has_node = True
                break

        if not has_node:
            return False, "ノード定義が見つかりません"

        open_brackets = code.count('[') + code.count('{') + code.count('(')
        close_brackets = code.count(']') + code.count('}') + code.count(')')
        if abs(open_brackets - close_brackets) > 3:
            return False, f"括弧の不一致 (開: {open_brackets}, 閉: {close_brackets})"

        return True, ""

    @staticmethod
    def repair_mermaid_code(code: str) -> str:
        """
        よくある Mermaid 構文エラーを自動修復
        """
        import re

        if not code or not code.strip():
            return code

        lines = code.strip().split('\n')

        first_line = lines[0].strip().lower()
        if not first_line.startswith(('flowchart', 'graph')):
            lines.insert(0, "flowchart TD")

        repaired = []
        for line in lines:
            line = line.replace('"', "'")
            repaired.append(line)

        result = '\n'.join(repaired)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()

    def generate(self, text: str, sections: list, key_points: list,
                 output_path: Optional[Path] = None, theme: str = "default",
                 width: int = 800, height: int = 600,
                 markdown_path: Optional[Path] = None,
                 mermaid_path: Optional[Path] = None) -> DiagramResult:
        """テキストとセクション情報からフローチャート画像を生成"""

        # Phase 1: Gemini でMermaidコードを生成
        mermaid_code = ""
        try:
            mermaid_code = self.generate_mermaid_code(text, sections, key_points)
        except Exception as e:
            logger.warning(f"Mermaid コード生成失敗: {e}")
            mermaid_code = self._build_simple_flowchart(sections, key_points)

        # Phase 2: バリデーション＆修復
        is_valid, error_msg = self.validate_mermaid_code(mermaid_code)
        if not is_valid:
            logger.warning(f"Mermaid バリデーション失敗 ({error_msg}), 修復を試行")
            mermaid_code = self.repair_mermaid_code(mermaid_code)
            is_valid, error_msg = self.validate_mermaid_code(mermaid_code)

        # Phase 3: レンダリング
        image_path = None
        if is_valid and output_path is not None:
            try:
                image_path = self.render_to_image(
                    mermaid_code, output_path, theme=theme,
                    width=width, height=height
                )
            except Exception as e:
                logger.warning(f"Mermaid レンダリング失敗: {e}, フォールバック画像を生成")

        if image_path is not None:
            result = DiagramResult(
                mermaid_code=mermaid_code,
                image_path=image_path,
                diagram_type="flowchart",
                success=True
            )
            if markdown_path:
                result.markdown_path = self.save_as_markdown(mermaid_code, markdown_path)
            if mermaid_path:
                result.mermaid_path = self.save_as_mermaid(mermaid_code, mermaid_path)
            return result

        # Phase 4: フォールバック画像
        step_texts = [sec.get('title', f'ステップ {i+1}') for i, sec in enumerate(sections)]
        if not step_texts:
            step_texts = key_points[:10] if key_points else ["手順情報なし"]

        if output_path is not None:
            try:
                image_path = self._create_fallback_image(step_texts, output_path, width, height)
                result = DiagramResult(
                    mermaid_code=mermaid_code,
                    image_path=image_path,
                    diagram_type="flowchart_fallback",
                    success=True,
                    error_message="フォールバック画像を使用"
                )
                if markdown_path:
                    result.markdown_path = self.save_as_markdown(mermaid_code, markdown_path)
                if mermaid_path:
                    result.mermaid_path = self.save_as_mermaid(mermaid_code, mermaid_path)
                return result
            except Exception as e:
                logger.warning(f"フォールバック画像生成失敗: {e}")

        # 画像生成なしでも Markdown / Mermaid は返す
        result = DiagramResult(
            mermaid_code=mermaid_code,
            image_path=None,
            diagram_type="flowchart",
            success=True,
            error_message="画像生成なし"
        )
        if markdown_path:
            result.markdown_path = self.save_as_markdown(mermaid_code, markdown_path)
        if mermaid_path:
            result.mermaid_path = self.save_as_mermaid(mermaid_code, mermaid_path)
        return result

    def _build_simple_flowchart(self, sections: list, key_points: list) -> str:
        """セクション名からシンプルなフローチャートを構築（API不要）"""
        lines = ["flowchart TD"]
        nodes = []

        items = [sec.get('title', f'ステップ{i+1}') for i, sec in enumerate(sections)]
        if not items:
            items = key_points[:8] if key_points else ["開始", "処理", "完了"]

        for i, item in enumerate(items[:12]):
            node_id = chr(65 + i)
            label = item[:20]
            nodes.append(node_id)
            lines.append(f"    {node_id}[{label}]")

        for i in range(len(nodes) - 1):
            lines.append(f"    {nodes[i]} --> {nodes[i+1]}")

        return "\n".join(lines)

    def save_as_markdown(self, mermaid_code: str, output_path: Path,
                         title: str = "フローチャート") -> Path:
        """
        Mermaid コードを Markdown 形式で保存

        Args:
            mermaid_code: Mermaid 記法の文字列
            output_path: 出力ファイルパス (.md)
            title: ドキュメントタイトル

        Returns:
            生成されたファイルのパス
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        content = f"# {title}\n\n```mermaid\n{mermaid_code}\n```\n"
        output_path.write_text(content, encoding="utf-8")
        logger.info(f"Markdown diagram saved: {output_path}")
        return output_path

    def save_as_mermaid(self, mermaid_code: str, output_path: Path) -> Path:
        """
        Mermaid コードを生の .mmd 形式で保存

        Args:
            mermaid_code: Mermaid 記法の文字列
            output_path: 出力ファイルパス (.mmd)

        Returns:
            生成されたファイルのパス
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(mermaid_code, encoding="utf-8")
        logger.info(f"Mermaid file saved: {output_path}")
        return output_path
