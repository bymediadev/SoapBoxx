#!/usr/bin/env python3
"""
Batch Processor for SoapBoxx
Handles processing multiple audio files at once
"""

import os
import threading
from pathlib import Path
from typing import Callable, Dict, List

from PyQt6.QtCore import QObject, QThread, pyqtSignal
from PyQt6.QtWidgets import QFileDialog, QMessageBox, QProgressDialog


class BatchProcessor(QObject):
    """Handles batch processing of audio files"""

    progress_updated = pyqtSignal(int, int)  # current, total
    file_processed = pyqtSignal(str, str)  # filename, status
    batch_completed = pyqtSignal(dict)  # results summary
    batch_failed = pyqtSignal(str)  # error message

    def __init__(self, parent=None):
        super().__init__(parent)
        self.processing = False
        self.results = {}
        self.supported_formats = [".wav", ".mp3", ".m4a", ".flac", ".aac"]

    def select_files(self) -> List[str]:
        """Select multiple audio files for processing"""
        files, _ = QFileDialog.getOpenFileNames(
            None,
            "Select Audio Files",
            "",
            "Audio Files (*.wav *.mp3 *.m4a *.flac *.aac);;All Files (*)",
        )
        return files

    def select_directory(self) -> str:
        """Select directory containing audio files"""
        directory = QFileDialog.getExistingDirectory(
            None, "Select Directory with Audio Files"
        )
        return directory

    def get_audio_files_from_directory(self, directory: str) -> List[str]:
        """Get all audio files from a directory"""
        audio_files = []
        directory_path = Path(directory)

        if not directory_path.exists():
            return audio_files

        for file_path in directory_path.rglob("*"):
            if (
                file_path.is_file()
                and file_path.suffix.lower() in self.supported_formats
            ):
                audio_files.append(str(file_path))

        return audio_files

    def process_files(self, files: List[str], processor_func: Callable = None):
        """Process multiple files in batch"""
        if self.processing:
            self.batch_failed.emit("Already processing files")
            return

        if not files:
            self.batch_failed.emit("No files selected")
            return

        self.processing = True
        self.results = {}

        # Start processing in background thread
        thread = threading.Thread(
            target=self._process_files_thread, args=(files, processor_func)
        )
        thread.daemon = True
        thread.start()

    def _process_files_thread(self, files: List[str], processor_func: Callable = None):
        """Process files in background thread"""
        try:
            total_files = len(files)
            processed = 0

            for file_path in files:
                if not self.processing:
                    break

                try:
                    # Process the file
                    if processor_func:
                        result = processor_func(file_path)
                    else:
                        result = self._default_processor(file_path)

                    self.results[file_path] = {"status": "success", "result": result}

                    processed += 1
                    self.progress_updated.emit(processed, total_files)
                    self.file_processed.emit(file_path, "success")

                except Exception as e:
                    self.results[file_path] = {"status": "error", "error": str(e)}
                    self.file_processed.emit(file_path, f"error: {str(e)}")
                    processed += 1
                    self.progress_updated.emit(processed, total_files)

            # Emit completion signal
            if self.processing:
                self.batch_completed.emit(self.results)

        except Exception as e:
            self.batch_failed.emit(f"Batch processing failed: {str(e)}")
        finally:
            self.processing = False

    def _default_processor(self, file_path: str) -> Dict:
        """Default file processor"""
        # This would integrate with the existing SoapBoxx components
        # For now, return basic file info
        file_info = {
            "filename": os.path.basename(file_path),
            "size": os.path.getsize(file_path),
            "path": file_path,
        }
        return file_info

    def stop_processing(self):
        """Stop batch processing"""
        self.processing = False

    def get_results(self) -> Dict:
        """Get processing results"""
        return self.results.copy()


class BatchProcessorDialog:
    """Dialog for batch processing options"""

    def __init__(self, parent=None):
        self.parent = parent
        self.processor = BatchProcessor()

    def show_batch_options(self):
        """Show batch processing options dialog"""
        from PyQt6.QtWidgets import (QDialog, QHBoxLayout, QLabel,
                                     QProgressBar, QPushButton, QVBoxLayout)

        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Batch Processing")
        dialog.setModal(True)
        dialog.resize(400, 200)

        layout = QVBoxLayout()

        # File selection
        file_layout = QHBoxLayout()
        select_files_btn = QPushButton("Select Files")
        select_dir_btn = QPushButton("Select Directory")

        select_files_btn.clicked.connect(self._select_files)
        select_dir_btn.clicked.connect(self._select_directory)

        file_layout.addWidget(select_files_btn)
        file_layout.addWidget(select_dir_btn)

        # Progress
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)

        # Status
        self.status_label = QLabel("Select files to process")

        layout.addLayout(file_layout)
        layout.addWidget(self.progress_bar)
        layout.addWidget(self.status_label)

        dialog.setLayout(layout)

        # Connect signals
        self.processor.progress_updated.connect(self._update_progress)
        self.processor.file_processed.connect(self._file_processed)
        self.processor.batch_completed.connect(self._batch_completed)
        self.processor.batch_failed.connect(self._batch_failed)

        return dialog

    def _select_files(self):
        """Select multiple files"""
        files = self.processor.select_files()
        if files:
            self.processor.process_files(files)
            self.progress_bar.setVisible(True)
            self.status_label.setText(f"Processing {len(files)} files...")

    def _select_directory(self):
        """Select directory"""
        directory = self.processor.select_directory()
        if directory:
            files = self.processor.get_audio_files_from_directory(directory)
            if files:
                self.processor.process_files(files)
                self.progress_bar.setVisible(True)
                self.status_label.setText(f"Processing {len(files)} files...")
            else:
                QMessageBox.information(
                    self.parent, "No Files", "No audio files found in directory"
                )

    def _update_progress(self, current: int, total: int):
        """Update progress bar"""
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        self.status_label.setText(f"Processing {current}/{total} files...")

    def _file_processed(self, filename: str, status: str):
        """File processed callback"""
        print(f"Processed {filename}: {status}")

    def _batch_completed(self, results: Dict):
        """Batch completed callback"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Batch processing completed!")

        # Show results summary
        success_count = sum(1 for r in results.values() if r["status"] == "success")
        error_count = len(results) - success_count

        QMessageBox.information(
            self.parent,
            "Batch Processing Complete",
            f"Processed {len(results)} files\n"
            f"Success: {success_count}\n"
            f"Errors: {error_count}",
        )

    def _batch_failed(self, error: str):
        """Batch failed callback"""
        self.progress_bar.setVisible(False)
        self.status_label.setText("Batch processing failed!")
        QMessageBox.critical(self.parent, "Batch Processing Failed", error)
