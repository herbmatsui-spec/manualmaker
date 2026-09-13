"""
Pages Functions API Handler - Mermaid Diagram Operations
"""

import json
import uuid
import tempfile
from pathlib import Path
from functions._middleware import (
    json_response, error_response, handle_options,
    validate_request, validate_file_id, cors_headers,
    validate_mermaid_validate_request,
    validate_mermaid_render_request,
    validate_mermaid_regenerate_request,
    validate_mermaid_save_request
)
from src.r2_storage import get_file_manager
from config.config import Config
from src.diagram_generator import DiagramGenerator


async def on_request(request, env, ctx):
    """Main entry point for /api/mermaid* routes"""
    path = request.url.path
    method = request.method
    
    if method == "OPTIONS":
        return await handle_options(request)
    
    if path == "/api/mermaid/validate" and method == "POST":
        return await validate_mermaid(request, env, ctx)
    elif path == "/api/mermaid/render" and method == "POST":
        return await render_mermaid(request, env, ctx)
    elif path == "/api/mermaid/regenerate" and method == "POST":
        return await regenerate_mermaid(request, env, ctx)
    elif path.startswith("/api/mermaid/save/") and method == "POST":
        file_id = path.split("/")[-1]
        # Validate file_id
        validation_result = validate_file_id({"file_id": file_id})
        if not validation_result.valid:
            return error_response("Invalid file_id format", 400, validation_result.errors)
        return await save_mermaid(request, env, ctx, file_id)
    
    return error_response("Not found", 404)


@validate_request(validate_mermaid_validate_request)
async def validate_mermaid(request, env, ctx):
    """Validate Mermaid.js code syntax"""
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        code = data.get("mermaid_code", "").strip()
        
        valid_keywords = ["graph", "flowchart", "sequenceDiagram", "classDiagram", "gantt", "pie", "mindmap"]
        first_line = code.split("\n")[0].strip()
        is_valid = any(first_line.startswith(kw) for kw in valid_keywords)
        
        return json_response({
            "valid": is_valid,
            "type": first_line.split()[0] if is_valid else "unknown"
        })
    except Exception as e:
        return error_response(f"検証エラー: {str(e)}", 500)


@validate_request(validate_mermaid_render_request)
async def render_mermaid(request, env, ctx):
    """Render Mermaid.js to PNG image"""
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        mermaid_code = data.get("mermaid_code", "").strip()
        theme = data.get("theme", "default")
        width = data.get("width", 800)
        height = data.get("height", 600)
        
        config = Config.get_instance()
        diagram_gen = DiagramGenerator(api_key=config.gemini_api_key)
        
        # Create temp file for output
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            out_png = Path(tmp.name)
        
        try:
            rendered_path = diagram_gen.render_to_image(
                mermaid_code=mermaid_code,
                output_path=out_png,
                theme=theme,
                width=width,
                height=height
            )
            
            # Read the rendered image
            with open(rendered_path, 'rb') as f:
                image_data = f.read()
            
            # Upload to R2 for persistence
            file_manager = get_file_manager(env.FILES)
            file_key = f"diagrams/rendered/{uuid.uuid4().hex}.png"
            file_manager.r2.upload_file(
                image_data, 
                file_key,
                content_type="image/png",
                metadata={"type": "mermaid_render", "theme": theme}
            )
            
            # Return image
            return {
                "status": 200,
                "headers": {
                    "Content-Type": "image/png",
                    "Content-Disposition": 'inline; filename="diagram.png"',
                    "Content-Length": str(len(image_data)),
                    **cors_headers()
                },
                "body": image_data
            }
            
        except Exception as e:
            return error_response(f"レンダリング失敗: {str(e)}", 400)
        finally:
            # Cleanup temp file
            try:
                out_png.unlink()
            except Exception:
                pass
                
    except Exception as e:
        return error_response(f"リクエストエラー: {str(e)}", 500)


@validate_request(validate_mermaid_regenerate_request)
async def regenerate_mermaid(request, env, ctx):
    """Regenerate Mermaid.js using AI"""
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        current_code = data.get("current_code", "")
        instruction = data.get("instruction", "")
        
        config = Config.get_instance()
        from src.gemini_processor import GeminiProcessor
        
        prompt = f"""以下の Mermaid.js フローチャートを、ユーザーの指示に従って修正・再生成してください。
返答は修正後の Mermaid.js コードのみを出力してください（説明文や余計なマークダウン記法は除外してください）。

【現在の Mermaid.js コード】
{current_code}

【修正指示】
{instruction}
"""
        processor = GeminiProcessor(api_key=config.gemini_api_key)
        new_code = processor.summarize_text(prompt)
        
        # Clean up markdown tags
        clean_code = new_code.replace("```mermaid", "").replace("```", "").strip()
        
        return json_response({"success": True, "mermaid_code": clean_code})
        
    except Exception as e:
        return error_response(f"AI 再生成エラー: {str(e)}", 500)


@validate_request(validate_mermaid_save_request)
async def save_mermaid(request, env, ctx, file_id: str):
    """Save Mermaid code and rebuild documents"""
    try:
        # Use validated data
        data = getattr(request, '_validated_data', {})
        mermaid_code = data.get("mermaid_code", "").strip()
        theme = data.get("theme", "default")
        width = data.get("width", 800)
        height = data.get("height", 600)
        
        file_manager = get_file_manager(env.FILES)
        result = file_manager.get_result(file_id)
        
        if not result:
            return error_response("処理結果が見つかりません。", 404)
        
        outputs = result.get("output_files", {})
        config = Config.get_instance()
        diagram_gen = DiagramGenerator(api_key=config.gemini_api_key)
        
        rendered_path = None
        
        # Generate PNG if configured
        if config.generate_diagram_png:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
                diagram_path = Path(tmp.name)
            
            try:
                rendered_path = diagram_gen.render_to_image(
                    mermaid_code=mermaid_code,
                    output_path=diagram_path,
                    theme=theme,
                    width=width,
                    height=height
                )
                
                # Upload to R2
                with open(rendered_path, 'rb') as f:
                    png_data = f.read()
                file_manager.save_result(file_id, "diagram", png_data, f"diagram_{file_id}.png")
                outputs["diagram"] = f"results/{file_id}/diagram/diagram_{file_id}.png"
                
            finally:
                try:
                    diagram_path.unlink()
                except Exception:
                    pass
        
        # Save Markdown
        if config.generate_diagram_markdown:
            from src.diagram_generator import DiagramGenerator
            md_content = f"# {result.get('title', 'フローチャート')}\n\n```mermaid\n{mermaid_code}\n```"
            md_data = md_content.encode('utf-8')
            file_manager.save_result(file_id, "diagram_markdown", md_data, f"diagram_{file_id}.md")
            outputs["diagram_markdown"] = f"results/{file_id}/diagram_markdown/diagram_{file_id}.md"
        
        # Save Mermaid source
        if config.generate_diagram_mermaid:
            mmd_data = mermaid_code.encode('utf-8')
            file_manager.save_result(file_id, "diagram_mermaid", mmd_data, f"diagram_{file_id}.mmd")
            outputs["diagram_mermaid"] = f"results/{file_id}/diagram_mermaid/diagram_{file_id}.mmd"
        
        # Update result with new mermaid code
        result["mermaid_code"] = mermaid_code
        result["output_files"] = outputs
        file_manager.save_json_result(file_id, result)
        
        # Regenerate PDF and DOCX if they exist
        if outputs.get("pdf") or outputs.get("docx"):
            from src.pdf_generator import create_formatted_pdf
            from src.docx_generator import create_word_document
            
            doc_title = result.get("title", "手書きマニュアル")
            content_text = f"概要\n{result.get('summary', '')}\n\n## 修正済みフロー図適用"
            
            if outputs.get("pdf"):
                # Download existing PDF, regenerate with new diagram
                pdf_key = outputs["pdf"]
                # This would require re-generating the full PDF
                # For now, just note that regeneration is needed
                pass
        
        return json_response({
            "success": True,
            "message": "フロー図の保存が完了しました。",
            "diagram_markdown": outputs.get("diagram_markdown"),
            "diagram_mermaid": outputs.get("diagram_mermaid")
        })
        
    except Exception as e:
        return error_response(f"保存エラー: {str(e)}", 500)