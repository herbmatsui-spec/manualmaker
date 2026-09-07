"""
Prompt Templates Module
Defines template constants for the 9 common handwritten PDF transcription problems
"""

from typing import Final

LITERAL_TRANSCRIPTION_RULE: Final[str] = """1. 完全な書き起こし：要約、解説、意図の解釈などは一切行わないでください。画像に書かれている文字のみを一字一句正確に出力してください。"""

UNREADABLE_CHAR_RULE: Final[str] = """2. 推測と自動補正の禁止：くせ字やカスレなどで判読できない文字、またはAIとして確信が持てない箇所については、文脈から勝手に推測・補完しないでください。判読不能な箇所は必ず「●」または「[読解不能]」という記号に置き換えてください。"""

RUBY_IGNORANCE_RULE: Final[str] = """3. ルビ（ふりがな）の無視：漢字の上に小さく振られているルビは、テキストに含めず完全に無視してください。"""

NOISE_EXCLUSION_RULE: Final[str] = """4. ノイズの除外：ノートの罫線、用紙の汚れ、消し跡、取り込み時の影などを、「一」「・」「━」などの記号や文字として誤認識しないよう注意してください。"""

LAYOUT_RULE_HORIZONTAL: Final[str] = """5. 読み取り方向の指定：この文書は横書きです。左から右、上から下へ向かって順番に読み取ってください。"""

LAYOUT_RULE_VERTICAL: Final[str] = """5. 読み取り方向の指定：この文書は縦書きです。右の行から左の行へ向かって順番に読み取ってください。"""

DOMAIN_GLOSSARY_RULE: Final[str] = """# 読み取り補助情報
以下の専門用語や固有名詞が含まれる可能性があるため、読み取りの参考情報として記載します。
{domain_terms}
"""

DIAGRAM_STRUCTURE_RULE: Final[str] = """6. 構造化指定：矢印や線で繋がれた図解メモが含まれる場合は、関係性がわかるように箇条書き（マークダウン形式）で構造化してください。"""

LOW_QUALITY_RULE: Final[str] = """7. 低品質画像対応：鉛筆で薄く書かれた文字や、かすれた文字は背景の一部ではなく、意図された文字として認識してください。空白と判断せず、必ずテキストとして出力してください。"""

DEFAULT_SYSTEM_PROMPT: Final[str] = """あなたは日本語の手書き文書の文字起こし専門AIです。以下の厳密なルールに従って、正確な文字起こしを行ってください。"""

DEFAULT_HEADER: Final[str] = """# 指示
添付した手書きのPDF文書を、以下の厳密なルールに従って高精度でテキスト化（文字起こし）してください。"""

DEFAULT_OUTPUT_FORMAT: Final[str] = """# 出力形式
上記ルールを適用したプレーンテキストのみを出力してください。"""
