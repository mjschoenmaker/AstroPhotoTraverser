import customtkinter as ctk
from tkinter import filedialog, messagebox
import os
import time
from threading import Thread

import config

from core import AstroScannerCore


class AstroScannerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Bind the Escape key to allow users to stop the scan
        self.bind('<Escape>', self.request_stop)
        self.core = None  # Will hold the AstroScannerCore instance   

        # Window Setup
        self.title("Astro-Inventory Manager")
        self.geometry("700x500")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # UI Layout
        self.grid_columnconfigure(0, weight=1)

        self.label = ctk.CTkLabel(self, text="Astrophotography Drive Scanner", font=("Arial", 24, "bold"))
        self.label.pack(pady=20)

        self.desc = ctk.CTkLabel(self, text="Select the root folder containing your #DSO targets.")
        self.desc.pack(pady=5)

        self.dir_button = ctk.CTkButton(self, text="Browse Hard Drive", command=self.select_dir)
        self.dir_button.pack(pady=10)

        self.path_display = ctk.CTkLabel(self, text="No folder selected", text_color="gray")
        self.path_display.pack(pady=5)

        # --- Hidden UI Elements (Progress) ---
        self.progress_label = ctk.CTkLabel(self, text="Initializing...")
        self.progress_bar = ctk.CTkProgressBar(self, width=400)
        self.progress_bar.set(0)
        
        self.scan_button = ctk.CTkButton(self, text="Start Scan & Create CSV", 
                                          command=self.start_scan_thread, state="disabled",
                                          fg_color="#2ecc71", hover_color="#27ae60")
        self.scan_button.pack(pady=20)

        self.status_box = ctk.CTkTextbox(self, width=600, height=200)
        self.status_box.pack(pady=10)

        self.selected_path = ""

    def request_stop(self, event=None):
        if self.core:
            self.log("Stop requested. Attempting to halt the scan...")
            self.core.stop_requested = True

    def log(self, message):
        def _append():
            try:
                self.status_box.insert("end", f"{message}\n")
                self.status_box.see("end")
            except Exception:
                pass
        # Schedule UI update on main thread
        try:
            self.after(0, _append)
        except Exception:
            _append()

    def update_progress(self, current, total):
        """Updates the progress bar from 0.0 to 1.0"""
        if total > 0:
            fraction = current / total
            percentage = int(fraction * 100)
            # .after(0, ...) ensures the UI update happens on the main thread
            self.after(0, lambda: self.progress_bar.set(fraction))
            self.after(0, lambda: self.progress_label.configure(text=f"Progress: {percentage}% ({current}/{total})"))

    def select_dir(self):
        self.selected_path = filedialog.askdirectory()
        if self.selected_path:
            self.path_display.configure(text=self.selected_path, text_color="white")
            self.scan_button.configure(state="normal")
            self.log(f"Target set to: {self.selected_path}")
            
            # hide the progress elements until scan starts
            self.progress_label.pack_forget()
            self.progress_bar.pack_forget()
            
            # empty the status box
            self.status_box.delete("1.0", "end")

    def start_scan_thread(self):
        # empty the status box
        self.status_box.delete("1.0", "end")        
        # 1. Show the progress elements before starting
        self.progress_label.configure(text="Initializing...")
        self.progress_label.pack(pady=(10, 0), after=self.scan_button)
        self.progress_bar.pack(pady=(5, 10), after=self.progress_label)
        self.progress_bar.set(0)
        
        if not hasattr(self, 'selected_path') or not self.selected_path:
            self.after(0, lambda: messagebox.showwarning("Warning", "Please select a folder first!"))
            return
    
        # Start the background thread
        thread = Thread(target=self.run_logic, daemon=True)
        thread.start()

    def run_logic(self):
        import sys
        with open('debug.log', 'a') as f:
            f.write(f"Python executable: {sys.executable}\n")

        # 1. Update UI state to 'Initializing' mode
        self.after(0, lambda: self.scan_button.configure(state="disabled"))
        self.log("Initializing scan...")

        # 2. Instantiate the logic engine with callbacks 
        # This allows the logic to 'talk' to the UI without being 'part' of it
        self.core = AstroScannerCore( # Store reference
            log_callback=self.log,
            progress_callback=self.update_progress
        )

        try:
            # --- Capture Start Time ---
            start_time = time.time()

            # 3. Execute logic
            data = self.core.scan_folder(self.selected_path)

            counts = self.core.extractor_counts
            breakdown = ",".join([f"{count} {name}" for name, count in counts.items()])

            # --- Calculate Duration ---
            end_time = time.time()
            duration = end_time - start_time

            if self.core.stop_requested:
                self.log("Scan was stopped by the user.")
                self.after(0, lambda: messagebox.showinfo("Scan Stopped", "The scan was stopped. Partial results may not be saved."))
                return

            if not data:
                self.after(0, lambda: messagebox.showwarning("No Data", "No compatible files were found."))
                return

            # 4. Save results        
            output_file = os.path.join(os.getcwd(), "astro_inventory.csv")
            self.core.save_to_csv(data, output_file)
            
            # 5. Notify UI of completion
            completion_msg = (
                f"SUCCESS: {len(data)} files indexed in {duration:.2f} seconds "
                f"({breakdown} files opened)"
            )
            self.log(completion_msg)
            self.after(0, lambda: messagebox.showinfo("Done", f"Scan complete!\nSaved to: {output_file}"))
        
        except Exception as e:
            # 6. Error handling
            self.log(f"ERROR: {str(e)}")
            self.after(0, lambda: messagebox.showerror("Error", f"An error occurred: {e}"))

            # 7. Ensure scan button is re-enabled even if error occurs
        finally:
            self.after(0, lambda: self.scan_button.configure(state="normal"))
