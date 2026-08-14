"""
Tkinter GUI Application
Provides a graphical interface for the manual processor
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
from pathlib import Path
import os
from typing import Optional, List

from config.config import Config
from src.processor.processor import DocumentProcessor
from src.logger import get_logger
from src.progress_manager import ProgressTracker, ProgressStatus, CancellationToken, OperationCancelledError

logger = get_logger("gui")


class ManualProcessorGUI(tk.Tk):
    """Main GUI application window"""
    
    def __init__(self):
        super().__init__()
        self.title("手書きマニュアル処理システム")
        self.geometry("820x640")
        self.resizable(True, True)
        
        # Initialize components
        self.config = Config.get_instance()
        self.processor = None
        self.is_processing = False
        self.cancel_token: Optional[CancellationToken] = None
        
        # Setup UI
        self.setup_ui()
        self.center_window()
        
    def setup_ui(self):
        """Setup the user interface"""
        # Create main frame
        main_frame = ttk.Frame(self, padding="20")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        # Configure grid weights
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="手書きマニュアル処理システム", 
            font=("Arial", 16, "bold")
        )
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # File selection section
        ttk.Label(main_frame, text="対象ファイル/フォルダ:").grid(row=1, column=0, sticky=tk.W, pady=5)
        
        self.file_path_var = tk.StringVar()
        file_entry = ttk.Entry(
            main_frame, 
            textvariable=self.file_path_var, 
            width=40
        )
        file_entry.grid(row=1, column=1, sticky=(tk.W, tk.E), padx=(10, 5), pady=5)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=1, column=2, padx=(5, 0), pady=5)
        
        browse_files_btn = ttk.Button(
            btn_frame, 
            text="ファイル選択...", 
            command=self.browse_files
        )
        browse_files_btn.pack(side=tk.LEFT, padx=2)
        
        browse_folder_btn = ttk.Button(
            btn_frame, 
            text="フォルダ選択...", 
            command=self.browse_folder
        )
        browse_folder_btn.pack(side=tk.LEFT, padx=2)
        
        # API Key section
        ttk.Label(main_frame, text="APIキー:").grid(row=2, column=0, sticky=tk.W, pady=(20, 5))
        
        self.api_key_var = tk.StringVar()
        api_key_from_env = os.environ.get("GOOGLE_API_KEY", "")
        self.api_key_var.set(api_key_from_env)
        
        self.api_entry = ttk.Entry(
            main_frame, 
            textvariable=self.api_key_var, 
            width=40,
            show="*"
        )
        self.api_entry.grid(row=2, column=1, sticky=(tk.W, tk.E), padx=(10, 5), pady=(20, 5))
        
        self.show_key_var = tk.BooleanVar()
        show_check = ttk.Checkbutton(
            main_frame,
            text="APIキーを表示",
            variable=self.show_key_var,
            command=self.toggle_api_key_visibility
        )
        show_check.grid(row=2, column=2, sticky=tk.W, padx=(5, 0), pady=(20, 5))
        
        # Options section
        options_frame = ttk.Frame(main_frame)
        options_frame.grid(row=3, column=0, columnspan=3, pady=(0, 10), sticky=tk.W)
        
        self.compact_layout_var = tk.BooleanVar()
        compact_check = ttk.Checkbutton(
            options_frame,
            text="コンパクトレイアウト（余白削減・文字拡大）",
            variable=self.compact_layout_var
        )
        compact_check.pack(side=tk.LEFT, padx=(0, 15))
        
        self.use_emojis_var = tk.BooleanVar()
        emoji_check = ttk.Checkbutton(
            options_frame,
            text="絵文字を挿入",
            variable=self.use_emojis_var
        )
        emoji_check.pack(side=tk.LEFT, padx=(0, 15))

        self.generate_diagram_var = tk.BooleanVar(value=True)
        diagram_check = ttk.Checkbutton(
            options_frame,
            text="フローチャートを生成",
            variable=self.generate_diagram_var
        )
        diagram_check.pack(side=tk.LEFT, padx=(0, 15))
        
        # Buttons frame
        action_btn_frame = ttk.Frame(main_frame)
        action_btn_frame.grid(row=4, column=0, columnspan=3, pady=10)

        # Process button
        self.process_btn = ttk.Button(
            action_btn_frame,
            text="処理開始",
            command=self.start_processing,
            style="Accent.TButton"
        )
        self.process_btn.pack(side=tk.LEFT, padx=5)

        # Cancel button
        self.cancel_btn = ttk.Button(
            action_btn_frame,
            text="キャンセル",
            command=self.cancel_processing,
            state="disabled"
        )
        self.cancel_btn.pack(side=tk.LEFT, padx=5)

        # Open output folder button
        self.open_folder_btn = ttk.Button(
            action_btn_frame,
            text="出力フォルダを開く",
            command=self.open_output_folder
        )
        self.open_folder_btn.pack(side=tk.LEFT, padx=5)
        
        # Progress bar (determinate)
        self.progress = ttk.Progressbar(
            main_frame,
            mode='determinate'
        )
        self.progress.grid(row=5, column=0, columnspan=3, sticky=(tk.W, tk.E), pady=(0, 10))
        
        # Status text area
        ttk.Label(main_frame, text="ステータス:").grid(row=6, column=0, sticky=tk.NW, pady=(10, 5))
        
        self.status_text = tk.Text(
            main_frame,
            height=12,
            width=70,
            wrap=tk.WORD
        )
        self.status_text.grid(row=7, column=0, columnspan=3, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10))
        
        # Configure text colors
        self.status_text.tag_config("error", foreground="#d9534f")
        self.status_text.tag_config("success", foreground="#28a745")
        self.status_text.tag_config("warning", foreground="#f0ad4e")
        self.status_text.tag_config("info", foreground="#0275d8")
        
        scrollbar = ttk.Scrollbar(
            main_frame,
            orient=tk.VERTICAL,
            command=self.status_text.yview
        )
        scrollbar.grid(row=7, column=3, sticky=(tk.N, tk.S), pady=(0, 10))
        self.status_text.configure(yscrollcommand=scrollbar.set)
        
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(7, weight=1)
        
        style = ttk.Style()
        style.configure("Accent.TButton", foreground="white", background="#0078d4")
    
    def open_output_folder(self):
        """出力フォルダをエクスプローラーで開く"""
        import subprocess
        output_dir = self.config.output_directory
        output_dir.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{output_dir}"')

    def center_window(self):
        """Center the window on screen"""
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f'{width}x{height}+{x}+{y}')
    
    def browse_files(self):
        """Open file dialog to select multiple PDF files"""
        file_paths = filedialog.askopenfilenames(
            title="PDFファイルを選択（複数選択可）",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if file_paths:
            self.file_path_var.set("; ".join(file_paths))
            self.log_message(f"ファイル選択 ({len(file_paths)}件): {', '.join(Path(p).name for p in file_paths)}", tag="info")
            
    def browse_folder(self):
        """Open directory dialog to select folder containing PDFs"""
        folder_path = filedialog.askdirectory(title="PDFが含まれるフォルダを選択")
        if folder_path:
            self.file_path_var.set(folder_path)
            self.log_message(f"フォルダ選択: {folder_path}", tag="info")
    
    def toggle_api_key_visibility(self):
        """Toggle API key visibility"""
        self.api_entry.configure(show="" if self.show_key_var.get() else "*")
    
    def log_message(self, message: str, tag: Optional[str] = None):
        """Add a message to the status text area"""
        if tag:
            self.status_text.insert(tk.END, f"{message}\n", tag)
        else:
            self.status_text.insert(tk.END, f"{message}\n")
        self.status_text.see(tk.END)
        self.update_idletasks()
    
    def cancel_processing(self):
        """Cancel ongoing batch processing"""
        if self.cancel_token and self.is_processing:
            self.cancel_token.cancel()
            self.log_message("⚠️ キャンセルを要求しました... 現在の処理が終わり次第中断します", tag="warning")
            self.cancel_btn.configure(state="disabled")

    def start_processing(self):
        """Start the processing workflow for single, multiple, or directory PDF inputs"""
        input_str = self.file_path_var.get().strip()
        if not input_str:
            messagebox.showerror("エラー", "ファイルまたはフォルダを選択してください")
            return
        
        # Collect target PDF files
        pdf_files = []
        paths = [p.strip() for p in input_str.split(";") if p.strip()]
        
        for p_str in paths:
            p = Path(p_str)
            if p.is_dir():
                pdf_files.extend(list(p.rglob("*.pdf")))
            elif p.is_file() and p.suffix.lower() == ".pdf":
                pdf_files.append(p)
                
        if not pdf_files:
            messagebox.showerror("エラー", "処理対象のPDFファイルが見つかりませんでした")
            return
            
        api_key = self.api_key_var.get().strip()
        if not api_key:
            messagebox.showerror("エラー", "APIキーを入力してください")
            return
        
        os.environ["GOOGLE_API_KEY"] = api_key
        if "GEMINI_API_KEY" not in os.environ:
            os.environ["GEMINI_API_KEY"] = api_key
        
        self.process_btn.configure(state="disabled")
        self.cancel_btn.configure(state="normal")
        self.progress['value'] = 0
        self.is_processing = True
        self.cancel_token = CancellationToken()
        
        self.log_message(f"--- 全 {len(pdf_files)} 件のPDFファイルの処理を開始します ---", tag="info")
        
        thread = threading.Thread(target=self.process_batch, args=(pdf_files, self.cancel_token))
        thread.daemon = True
        thread.start()
    
    def _update_progress(self, file_index: int, total_files: int, step_percent: float = 0.0):
        """プログレスバーを更新"""
        # Overall progress: completed files + current file progress
        file_weight = 100.0 / max(1, total_files)
        total_percent = ((file_index - 1) * file_weight) + (step_percent * file_weight / 100.0)
        self.progress['value'] = min(100.0, total_percent)
        self.title(f"手書きマニュアル処理システム - {file_index}/{total_files} ({total_percent:.0f}%)")
        self.update_idletasks()

    def process_batch(self, pdf_files: list, cancel_token: CancellationToken):
        """Process batch of PDF files in background thread"""
        results = []
        compact = self.compact_layout_var.get()
        use_emojis = self.use_emojis_var.get()
        self.config.generate_diagram = self.generate_diagram_var.get()
        total_files = len(pdf_files)

        def on_step_progress(status: ProgressStatus):
            self.after(0, self._update_progress, current_idx, total_files, status.percentage)
            self.after(0, self.log_message, f"   └ [{status.stage}] {status.message}")

        current_idx = 1
        try:
            self.processor = DocumentProcessor()
            for idx, pdf_path in enumerate(pdf_files, 1):
                current_idx = idx
                if cancel_token.is_cancelled:
                    self.after(0, self.log_message, f"🛑 処理がキャンセルされました（{idx-1}/{total_files}件完了）", "warning")
                    break

                self.after(0, self.log_message, f"[{idx}/{total_files}] 処理中: {pdf_path.name}", "info")
                self.after(0, self._update_progress, idx, total_files, 0.0)
                
                tracker = ProgressTracker(callback=on_step_progress)
                res = self.processor.process_pdf(
                    pdf_path,
                    compact_layout=compact,
                    use_emojis=use_emojis,
                    progress_tracker=tracker,
                    cancel_token=cancel_token
                )
                results.append(res)
                self.after(0, self._update_progress, idx, total_files, 100.0)

                if res.get("success"):
                    diagram_status = "📊 フロー図あり" if res.get("diagram_path") else ""
                    self.after(0, self.log_message, f"  ✅ 完了! タイトル: 【{res.get('title', '無題')}】 {diagram_status}", "success")
                else:
                    self.after(0, self.log_message, f"  ❌ 失敗: {res.get('error', '不明なエラー')}", "error")
                    
            self.after(0, self.batch_complete, results, cancel_token.is_cancelled)
        except OperationCancelledError:
            self.after(0, self.log_message, "🛑 ユーザーにより処理がキャンセルされました。", "warning")
            self.after(0, self.batch_complete, results, True)
        except Exception as e:
            logger.error(f"Batch processing error: {e}")
            self.after(0, self.processing_error, str(e))
            
    def batch_complete(self, results: list, was_cancelled: bool = False):
        """Handle batch completion"""
        self.progress.stop()
        self.process_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.is_processing = False
        
        success_count = sum(1 for r in results if r.get("success"))
        total_count = len(results)
        
        if was_cancelled:
            self.log_message(f"⚠️ 処理中断: {total_count}件中 {success_count}件完了後にキャンセルされました。", "warning")
            messagebox.showwarning(
                "処理中断",
                f"処理がキャンセルされました。\n\n■ 完了件数: {success_count} 件\n\n出力フォルダ（output/）を確認してください。"
            )
        else:
            self.progress['value'] = 100
            self.log_message(f"✅ バッチ処理完了: 全{total_count}件中 {success_count}件が正常終了しました！", "success")
            messagebox.showinfo(
                "処理完了",
                f"バッチ処理が完了しました！\n\n■ 成功: {success_count} / {total_count} 件\n\n出力フォルダ（output/）を確認してください。"
            )
    
    def processing_error(self, error_msg: str):
        """Handle processing error"""
        self.progress.stop()
        self.process_btn.configure(state="normal")
        self.cancel_btn.configure(state="disabled")
        self.is_processing = False
        
        self.log_message(f"❌ エラーが発生しました: {error_msg}", "error")
        messagebox.showerror("エラー", f"処理中にエラーが発生しました:\n{error_msg}")


from src.error_handler import set_gui_error_callback

def main():
    """Main entry point for GUI application"""
    def gui_error_handler(message: str, error: Exception):
        try:
            messagebox.showerror("エラー", message)
        except Exception:
            pass

    set_gui_error_callback(gui_error_handler)
    app = ManualProcessorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()