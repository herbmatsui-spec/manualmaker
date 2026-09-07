"""
i18n Templates Module
Provides multilingual support for prompt templates
"""

from typing import Final, Dict

LANGUAGE_CODES = ["ja", "en", "zh"]


TRANSLATIONS: Final[Dict[str, Dict[str, str]]] = {
    "ja": {
        "system_prompt": "あなたは日本語の手書き文書の文字起こし専門AIです。以下の厳密なルールに従って、正確な文字起こしを行ってください。",
        "header": "# 指示\n添付した手書きのPDF文書を、以下の厳密なルールに従って高精度でテキスト化（文字起こし）してください。",
        "rule_header": "# 厳守事項（ルール）",
        "output_format": "# 出力形式\n上記ルールを適用したプレーンテキストのみを出力してください。",
        "transcription_rule": "完全な書き起こし：要約、解説、意図の解釈などは一切行わないでください。画像に書かれている文字のみを一字一句正確に出力してください。",
        "unreadable_rule": "推測と自動補正の禁止：くせ字やカスレなどで判読できない文字、またはAIとして確信が持てない箇所については、文脈から勝手に推測・補完しないでください。判読不能な箇所は必ず「●」または「[読解不能]」という記号に置き換えてください。",
        "ruby_rule": "ルビ（ふりがな）の無視：漢字の上に小さく振られているルビは、テキストに含めず完全に無視してください。",
        "noise_rule": "ノイズの除外：ノートの罫線、用紙の汚れ、消し跡、取り込み時の影などを、「一」「・」「━」などの記号や文字として誤認識しないよう注意してください。",
        "layout_horizontal": "読み取り方向の指定：この文書は横書きです。左から右、上から下へ向かって順番に読み取ってください。",
        "layout_vertical": "読み取り方向の指定：この文書は縦書きです。右の行から左の行へ向かって順番に読み取ってください。",
        "domain_glossary": "# 読み取り補助情報\n以下の専門用語や固有名詞が含まれる可能性があるため、読み取りの参考情報として記載します。\n{terms}",
        "diagram_rule": "構造化指定：矢印や線で繋がれた図解メモが含まれる場合は、関係性がわかるように箇条書き（マークダウン形式）で構造化してください。",
        "low_quality_rule": "低品質画像対応：鉛筆で薄く書かれた文字や、かすれた文字は背景の一部ではなく、意図された文字として認識してください。空白と判断せず、必ずテキストとして出力してください。",
        "confusing_chars": "類似文字の注意：以下の類似文字の組合せに注意してください。必ず文脈から判断せず、画像の状態を正確に読み取ってください。\n   - 「シ」と「ツ」（カタカナ）\n   - 「ソ」と「ン」（カタカナ）\n   - 「0（ゼロ）」と「O（オー）」\n   - 「1（数字のいち）」と「l（小文字のエル）」と「I（大文字のアイ）」\n   - 「一（漢字）」と「ー（長音記号）」",
    },
    "en": {
        "system_prompt": "You are an AI specialized in transcribing handwritten Japanese documents. Follow the strict rules below to perform accurate text transcription.",
        "header": "# Instruction\nTranscribe the attached handwritten PDF document into high-precision text according to the following strict rules.",
        "rule_header": "# Strict Rules",
        "output_format": "# Output Format\nOutput only plain text following the rules above.",
        "transcription_rule": "Complete transcription: Do not summarize, interpret, or explain. Output only the exact characters written in the image, word for word.",
        "unreadable_rule": "No speculation or auto-correction: For unreadable characters or uncertain passages, do not guess or fill in based on context. Mark unreadable parts with 「●」 or 「[unreadable]」.",
        "ruby_rule": "Ignore ruby text: Do not include furigana (small characters above kanji) in the output.",
        "noise_rule": "Exclude noise: Do not mistake notebook grid lines, paper stains, eraser marks, or scan shadows for characters like 「一」, 「・」, or 「━」.",
        "layout_horizontal": "Reading direction: This is horizontal text. Read from left to right, top to bottom.",
        "layout_vertical": "Reading direction: This is vertical text. Read from right column to left column.",
        "domain_glossary": "# Reference Information\nThe following technical terms or proper nouns may appear:\n{terms}",
        "diagram_rule": "Structure diagrams: If the document contains diagrams or arrows, structure them as bullet points in markdown format.",
        "low_quality_rule": "Low quality handling: Thin pencil marks or faded characters are intentional text, not background. Do not treat them as blank spaces.",
        "confusing_chars": "Similar character warning: Pay attention to these similar characters:\n   - 「シ」vs「ツ」(Katakana)\n   - 「ソ」vs「ン」(Katakana)\n   - 「0」(zero) vs「O」(letter O)\n   - 「1」(one) vs「l」(lowercase L) vs「I」(uppercase i)\n   - 「一」(kanji) vs「ー」(long vowel)",
    },
    "zh": {
        "system_prompt": "您是专门转录日文手写文件的AI。请遵循以下严格规则进行准确的文本转录。",
        "header": "# 指示\n请根据以下严格规则，将附加的手写PDF文档高精度地转换为文本。",
        "rule_header": "# 严格规则",
        "output_format": "# 输出格式\n仅输出遵循上述规则的纯文本。",
        "transcription_rule": "完整转录：不要总结、解释或推断。只准确输出图像中写的文字，逐字逐句。",
        "unreadable_rule": "禁止推测和自动纠正：对于难以辨认的文字或不确定的部分，请勿根据上下文猜测或补充。无法辨认的部分请用「●」或「[无法识别]」标记。",
        "ruby_rule": "忽略振假名：请勿在输出中包含汉字上方的小字振假名。",
        "noise_rule": "排除噪音：请勿将笔记本格子线、纸张污渍、橡皮擦痕迹或扫描阴影误认为「一」「・」「━」等字符。",
        "layout_horizontal": "阅读方向：这是横排文本。从左到右、从上到下依次阅读。",
        "layout_vertical": "阅读方向：这是竖排文本。从右列到左列依次阅读。",
        "domain_glossary": "# 参考信息\n以下专业术语或固有名词可能出现：\n{terms}",
        "diagram_rule": "结构化图表：如果文档包含图表或箭头，请用markdown格式的项目符号进行结构化。",
        "low_quality_rule": "低质量处理：淡淡的铅笔字迹或褪色的字符是有意写入的文本，不是背景。请勿将其视为空白。",
        "confusing_chars": "相似字符警告：请注意以下相似字符：\n   - 「シ」vs「ツ」（片假名）\n   - 「ソ」vs「ン」（片假名）\n   - 「0」（零）vs「O」（字母O）\n   - 「1」（数字1）vs「l」（小写L）vs「I」（大写I）\n   - 「一」（汉字）vs「ー」（长音符号）",
    },
}


def get_translation(lang: str, key: str) -> str:
    """Get translation for a specific language and key"""
    if lang not in TRANSLATIONS:
        lang = "ja"
    return TRANSLATIONS.get(lang, TRANSLATIONS["ja"]).get(key, key)
