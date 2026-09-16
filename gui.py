import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from report_parser import parse_jsonl
from processor import process_reports
from markdown_writer import build_markdown


class App:
    def __init__(self, root):
        self._root = root
        root.title("Field Service Report Summarizer")
        root.minsize(700, 500)

        self._file_path = tk.StringVar()
        self._progress_text = tk.StringVar(value="")
        self._results = []
        self._markdown = ""

        self._build_ui()

    def _build_ui(self):
        pad = {"padx": 8, "pady": 4}

        # --- File picker row ---
        file_frame = ttk.Frame(self._root)
        file_frame.pack(fill="x", **pad)

        ttk.Label(file_frame, text="Input file:").pack(side="left")
        ttk.Entry(file_frame, textvariable=self._file_path, state="readonly").pack(
            side="left", fill="x", expand=True, padx=(4, 4)
        )
        ttk.Button(file_frame, text="Browse…", command=self._browse).pack(side="left")

        # --- Action buttons row ---
        btn_frame = ttk.Frame(self._root)
        btn_frame.pack(fill="x", **pad)

        self._generate_btn = ttk.Button(
            btn_frame, text="Generate Summaries", command=self._on_generate
        )
        self._generate_btn.pack(side="left")

        self._save_btn = ttk.Button(
            btn_frame, text="Save Markdown…", command=self._on_save, state="disabled"
        )
        self._save_btn.pack(side="left", padx=(8, 0))

        # --- Progress row ---
        progress_frame = ttk.Frame(self._root)
        progress_frame.pack(fill="x", **pad)

        self._progress_bar = ttk.Progressbar(progress_frame, mode="determinate")
        self._progress_bar.pack(side="left", fill="x", expand=True)

        ttk.Label(progress_frame, textvariable=self._progress_text).pack(
            side="left", padx=(8, 0)
        )

        # --- Results list ---
        columns = ("report_id", "asset", "status")
        self._tree = ttk.Treeview(
            self._root, columns=columns, show="headings", selectmode="browse"
        )
        self._tree.heading("report_id", text="Report ID")
        self._tree.heading("asset", text="Asset")
        self._tree.heading("status", text="Status")
        self._tree.column("report_id", width=120, minwidth=80)
        self._tree.column("asset", width=200, minwidth=100)
        self._tree.column("status", width=80, minwidth=60)

        scrollbar = ttk.Scrollbar(self._root, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=scrollbar.set)

        self._tree.pack(fill="both", expand=True, padx=8, pady=(4, 0))
        scrollbar.pack(side="right", fill="y")

        # --- Status reason display ---
        self._reason_var = tk.StringVar(value="")
        reason_label = ttk.Label(
            self._root, textvariable=self._reason_var, wraplength=650, foreground="gray"
        )
        reason_label.pack(fill="x", padx=8, pady=(0, 8))

        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # --- Tag colours for status ---
        self._tree.tag_configure("ok", foreground="green")
        self._tree.tag_configure("review", foreground="orange")

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select JSONL file",
            filetypes=[("JSONL files", "*.jsonl"), ("All files", "*.*")],
        )
        if path:
            self._file_path.set(path)

    def _on_generate(self):
        path = self._file_path.get()
        if not path:
            messagebox.showwarning("No file", "Please select a JSONL file first.")
            return

        if not os.environ.get("GROQ_API_KEY"):
            messagebox.showerror(
                "API key missing",
                "GROQ_API_KEY environment variable is not set.\n\n"
                "Set it before running the tool.",
            )
            return

        self._generate_btn.configure(state="disabled")
        self._save_btn.configure(state="disabled")
        self._tree.delete(*self._tree.get_children())
        self._reason_var.set("")
        self._progress_bar["value"] = 0
        self._progress_text.set("Parsing…")

        thread = threading.Thread(target=self._run_pipeline, args=(path,), daemon=True)
        thread.start()

    def _run_pipeline(self, path):
        reports, warnings = parse_jsonl(path)

        for w in warnings:
            self._root.after(0, self._add_warning_row, w)

        if not reports:
            self._root.after(0, self._pipeline_done, [])
            return

        total = len(reports)
        self._root.after(0, self._init_progress, total)

        def on_progress(current, total):
            self._root.after(0, self._update_progress, current, total)

        results = process_reports(reports, progress_callback=on_progress)
        self._root.after(0, self._pipeline_done, results)

    def _init_progress(self, total):
        self._progress_bar["maximum"] = total
        self._progress_bar["value"] = 0
        self._progress_text.set(f"Processing 0/{total}…")

    def _update_progress(self, current, total):
        self._progress_bar["value"] = current
        self._progress_text.set(f"Processing {current}/{total}…")

    def _add_warning_row(self, warning):
        self._tree.insert("", "end", values=("⚠ Parse warning", warning, "—"))

    def _pipeline_done(self, results):
        self._results = results
        self._markdown = build_markdown(results) if results else ""

        for r in results:
            tag = "ok" if r["status"] == "OK" else "review"
            self._tree.insert(
                "", "end",
                values=(r["report_id"], r["asset"], r["status"]),
                tags=(tag,),
            )

        total = len(results)
        self._progress_text.set(f"Done — {total} report{'s' if total != 1 else ''}")
        self._progress_bar["value"] = self._progress_bar["maximum"]
        self._generate_btn.configure(state="normal")
        if results:
            self._save_btn.configure(state="normal")

    def _on_select(self, _event):
        selection = self._tree.selection()
        if not selection:
            self._reason_var.set("")
            return
        item = self._tree.item(selection[0])
        report_id = item["values"][0]
        match = next((r for r in self._results if r["report_id"] == report_id), None)
        if match and match["status_reason"]:
            self._reason_var.set(f"Reason: {match['status_reason']}")
        else:
            self._reason_var.set("")

    def _on_save(self):
        if not self._markdown:
            return
        path = filedialog.asksaveasfilename(
            title="Save summary",
            defaultextension=".md",
            filetypes=[("Markdown files", "*.md"), ("All files", "*.*")],
        )
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._markdown)
            messagebox.showinfo("Saved", f"Summaries saved to:\n{path}")
