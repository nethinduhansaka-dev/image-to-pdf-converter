import os
import tkinter as tk
from tkinter import filedialog, ttk, messagebox
from PIL import Image, ImageTk
import threading
from typing import List, Optional
import traceback
from tkinterdnd2 import DND_FILES, TkinterDnD

class ScrollableFrame(ttk.Frame):
    def __init__(self, container, *args, **kwargs):
        super().__init__(container, *args, **kwargs)
        self.canvas = tk.Canvas(self)
        scrollbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(xscrollcommand=scrollbar.set)

        self.canvas.pack(side="top", fill="both", expand=True)
        scrollbar.pack(side="bottom", fill="x")

class ImageThumbnail(ttk.Frame):
    def __init__(self, parent, image_path: str, index: int, on_select, on_rotate, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.image_path = image_path
        self.index = index
        self.on_select = on_select
        self.selected = False

        # Create thumbnail
        image = Image.open(image_path)
        image.thumbnail((100, 100), Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(image)

        # Thumbnail frame
        self.thumbnail_frame = ttk.Frame(self)
        self.thumbnail_frame.pack(padx=5, pady=5)

        # Image label
        self.label = ttk.Label(self.thumbnail_frame, image=self.photo)
        self.label.pack()

        # Rotation buttons
        rotation_frame = ttk.Frame(self.thumbnail_frame)
        rotation_frame.pack(fill="x")
        
        ttk.Button(rotation_frame, text="↶", width=3,
                  command=lambda: on_rotate(self.index, -90)).pack(side="left", padx=2)
        ttk.Button(rotation_frame, text="↷", width=3,
                  command=lambda: on_rotate(self.index, 90)).pack(side="right", padx=2)

        # Bind click event
        self.label.bind("<Button-1>", self.toggle_select)
        
        # Filename label (truncated)
        filename = os.path.basename(image_path)
        if len(filename) > 15:
            filename = filename[:12] + "..."
        ttk.Label(self.thumbnail_frame, text=filename).pack()

    def toggle_select(self, event=None):
        self.selected = not self.selected
        self.thumbnail_frame.configure(style="Selected.TFrame" if self.selected else "TFrame")
        self.on_select(self.index)

class ImageToPdfConverter(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        
        # Initialize window properties
        self.title("Enhanced Image to PDF Converter")
        self.geometry("1000x800")
        self.minsize(800, 600)
        self.configure(bg="#f0f0f0")

        # Initialize variables
        self.images: List[str] = []
        self.rotations: List[int] = []
        self.selected_indices: List[int] = []
        self.current_preview_index = 0
        
        # Create main layout components
        self._create_layout()
        self._setup_drag_drop()
        self._apply_styles()

    def _create_layout(self):
        # Main container
        self.main_frame = ttk.Frame(self, padding=(20, 20))
        self.main_frame.pack(fill="both", expand=True)

        # Top section: Thumbnails
        self.thumbnails_label = ttk.Label(self.main_frame, text="Image Thumbnails:")
        self.thumbnails_label.pack(anchor="w", pady=(0, 5))

        self.thumbnails_frame = ScrollableFrame(self.main_frame)
        self.thumbnails_frame.pack(fill="x", pady=(0, 20))

        # Middle section: Preview
        preview_container = ttk.LabelFrame(self.main_frame, text="Preview", padding=(10, 10))
        preview_container.pack(fill="both", expand=True, pady=(0, 20))

        # Preview controls
        controls_frame = ttk.Frame(preview_container)
        controls_frame.pack(fill="x", pady=(0, 10))

        self.prev_button = ttk.Button(controls_frame, text="Previous", command=self.prev_image, state="disabled")
        self.prev_button.pack(side="left", padx=5)

        self.next_button = ttk.Button(controls_frame, text="Next", command=self.next_image, state="disabled")
        self.next_button.pack(side="left", padx=5)

        self.preview_label = ttk.Label(controls_frame, text="No images selected")
        self.preview_label.pack(side="left", padx=20)

        # Preview canvas
        self.preview_canvas = tk.Canvas(preview_container, bg="white")
        self.preview_canvas.pack(fill="both", expand=True)

        # Bottom section: Controls
        controls_container = ttk.Frame(self.main_frame)
        controls_container.pack(fill="x", pady=(0, 20))

        # Left controls
        left_controls = ttk.Frame(controls_container)
        left_controls.pack(side="left")

        self.add_button = ttk.Button(left_controls, text="Add Images", command=self.select_images)
        self.add_button.pack(side="left", padx=5)

        self.remove_button = ttk.Button(left_controls, text="Remove Selected", 
                                      command=self.remove_selected, state="disabled")
        self.remove_button.pack(side="left", padx=5)

        self.clear_button = ttk.Button(left_controls, text="Clear All", 
                                     command=self.clear_images, state="disabled")
        self.clear_button.pack(side="left", padx=5)

        # Right controls
        right_controls = ttk.Frame(controls_container)
        right_controls.pack(side="right")

        self.convert_button = ttk.Button(right_controls, text="Convert to PDF", 
                                       command=self.convert_to_pdf, style="Accent.TButton", 
                                       state="disabled")
        self.convert_button.pack(side="right", padx=5)

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(self.main_frame, variable=self.progress_var, 
                                          maximum=100, mode='determinate')
        self.progress_bar.pack(fill="x", pady=(0, 10))

        # Status bar
        self.status_var = tk.StringVar(value="Drop images here or use 'Add Images' button")
        self.status_bar = ttk.Label(self.main_frame, textvariable=self.status_var, 
                                  relief="sunken", anchor="w")
        self.status_bar.pack(fill="x")

    def _setup_drag_drop(self):
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.handle_drop)
        self.preview_canvas.drop_target_register(DND_FILES)
        self.preview_canvas.dnd_bind('<<Drop>>', self.handle_drop)

    def _apply_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")
        
        style.configure("TFrame", background="#f0f0f0")
        style.configure("Selected.TFrame", background="#e1f5fe")
        style.configure("TLabel", background="#f0f0f0", font=("Arial", 10))
        style.configure("TButton", padding=5, font=("Arial", 10))
        
        style.configure("Accent.TButton",
                       background="#007bff",
                       foreground="white",
                       padding=10,
                       font=("Arial", 10, "bold"))
        
        style.map("Accent.TButton",
                 background=[("active", "#0056b3"),
                            ("disabled", "#cccccc")],
                 foreground=[("disabled", "#666666")])
        
        style.configure("Horizontal.TProgressbar",
                       background="#007bff",
                       troughcolor="#f0f0f0",
                       bordercolor="#cccccc",
                       lightcolor="#ffffff",
                       darkcolor="#0056b3")

    def handle_drop(self, event):
        raw_paths = event.data
        if isinstance(raw_paths, str):
            paths = [p.strip('{}').strip('"') for p in raw_paths.split()]
            valid_files = []
            
            for path in paths:
                if self.is_valid_image(path):
                    valid_files.append(path)
                else:
                    messagebox.showwarning(
                        "Invalid File",
                        f"Skipping invalid file: {os.path.basename(path)}\n"
                        "Only image files (JPG, PNG, BMP, TIFF) are supported."
                    )

            if valid_files:
                self.add_images(valid_files)

    def is_valid_image(self, file_path: str) -> bool:
        valid_extensions = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff'}
        return os.path.splitext(file_path.lower())[1] in valid_extensions

    def select_images(self):
        filetypes = [("Image files", "*.jpg *.jpeg *.png *.bmp *.tiff")]
        files = filedialog.askopenfilenames(title="Select Images", filetypes=filetypes)
        if files:
            self.add_images(files)

    def add_images(self, new_images: List[str]):
        try:
            for img_path in new_images:
                if img_path not in self.images:
                    self.images.append(img_path)
                    self.rotations.append(0)
            
            self.update_thumbnails()
            self.update_preview()
            self.update_controls()
            self.status_var.set(f"Added {len(new_images)} image(s)")
        except Exception as e:
            self.show_error("Error adding images", str(e))

    def update_thumbnails(self):
        # Clear existing thumbnails
        for widget in self.thumbnails_frame.scrollable_frame.winfo_children():
            widget.destroy()

        # Create new thumbnails
        for i, img_path in enumerate(self.images):
            thumbnail = ImageThumbnail(
                self.thumbnails_frame.scrollable_frame,
                img_path,
                i,
                self.handle_thumbnail_select,
                self.rotate_image
            )
            thumbnail.pack(side="left", padx=5, pady=5)

    def handle_thumbnail_select(self, index: int):
        if index in self.selected_indices:
            self.selected_indices.remove(index)
        else:
            self.selected_indices.append(index)
        
        self.remove_button.configure(state="normal" if self.selected_indices else "disabled")
        self.current_preview_index = index
        self.update_preview()

    def rotate_image(self, index: int, angle: int):
        self.rotations[index] = (self.rotations[index] + angle) % 360
        self.update_preview()
        self.update_thumbnails()

    def update_preview(self):
        self.preview_canvas.delete("all")
        
        if not self.images:
            self.preview_label.configure(text="No images selected")
            return

        try:
            self.preview_label.configure(
                text=f"Image {self.current_preview_index + 1} of {len(self.images)}: "
                f"{os.path.basename(self.images[self.current_preview_index])}"
            )

            image = Image.open(self.images[self.current_preview_index])
            if self.rotations[self.current_preview_index] != 0:
                image = image.rotate(
                    self.rotations[self.current_preview_index],
                    expand=True
                )

            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            
            img_width, img_height = image.size
            scale = min(
                canvas_width / img_width,
                canvas_height / img_height
            )

            new_width = int(img_width * scale)
            new_height = int(img_height * scale)

            image = image.resize(
                (new_width, new_height),
                Image.Resampling.LANCZOS
            )
            
            self.preview_photo = ImageTk.PhotoImage(image)
            
            x = (canvas_width - new_width) // 2
            y = (canvas_height - new_height) // 2
            
            self.preview_canvas.create_image(
                x, y,
                anchor="nw",
                image=self.preview_photo
            )

        except Exception as e:
            self.show_error("Error updating preview", str(e))

    def prev_image(self):
        if self.current_preview_index > 0:
            self.current_preview_index -= 1
            self.update_preview()
            self.update_navigation_buttons()

    def next_image(self):
        if self.current_preview_index < len(self.images) - 1:
            self.current_preview_index += 1
            self.update_preview()
            self.update_navigation_buttons()

    def update_navigation_buttons(self):
        self.prev_button.configure(state="normal" if self.current_preview_index > 0 else "disabled")
        self.next_button.configure(
            state="normal" if self.current_preview_index < len(self.images) - 1 else "disabled"
        )

    def update_controls(self):
        has_images = bool(self.images)
        self.clear_button.configure(state="normal" if has_images else "disabled")
        self.convert_button.configure(state="normal" if has_images else "disabled")
        self.update_navigation_buttons()

    def remove_selected(self):
        if not self.selected_indices:
            return

        for index in sorted(self.selected_indices, reverse=True):
            self.images.pop(index)
            self.rotations.pop(index)

        self.selected_indices.clear()
        self.current_preview_index = 0
        self.update_thumbnails()
        self.update_preview()
        self.update_controls()
        self.status_var.set("Selected images removed")

    def clear_images(self):
        self.images.clear()
        self.rotations.clear()
        self.selected_indices.clear()
        self.current_preview_index = 0
        self.update_thumbnails()
        self.update_preview()
        self.update_controls()

    def convert_to_pdf(self):
        if not self.images:
            messagebox.showwarning("No Images", "Please add some images first.")
            return

        pdf_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf")],
            initialdir=os.path.expanduser("~")
        )

        if not pdf_path:
            return

        # Disable controls during conversion
        self.toggle_controls(False)
        self.progress_var.set(0)
        self.status_var.set("Converting...")

        # Start conversion in a separate thread
        thread = threading.Thread(target=self._convert_to_pdf, args=(pdf_path,))
        thread.start()

    def _convert_to_pdf(self, pdf_path: str):
        try:
            # Prepare images
            image_list = []
            total_images = len(self.images)

            for i, (img_path, rotation) in enumerate(zip(self.images, self.rotations)):
                # Update progress
                progress = (i / total_images) * 100
                self.status_var.set(f"Processing image {i+1} of {total_images}")
                self.progress_var.set(progress)

                # Open and rotate image if needed
                image = Image.open(img_path).convert('RGB')
                if rotation != 0:
                    image = image.rotate(rotation, expand=True)
                image_list.append(image)

            # Save PDF
            image_list[0].save(
                pdf_path,
                save_all=True,
                append_images=image_list[1:]
            )

            self.status_var.set("PDF created successfully!")
            self.progress_var.set(100)
            
            # Ask user if they want to open the PDF
            if messagebox.askyesno("Success", "PDF created successfully! Would you like to open it?"):
                self.open_file(pdf_path)

        except Exception as e:
            self.show_error("Error during conversion", str(e))
        finally:
            # Re-enable controls
            self.toggle_controls(True)

    def toggle_controls(self, enabled: bool):
        """Enable or disable all controls during processing."""
        state = "normal" if enabled else "disabled"
        self.add_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.clear_button.configure(state=state)
        self.convert_button.configure(state=state)
        self.prev_button.configure(state=state)
        self.next_button.configure(state=state)

    def show_error(self, title: str, message: str):
        """Show error message and log the error."""
        messagebox.showerror(title, message)
        print(f"Error: {title}\n{message}")
        print(traceback.format_exc())
        self.status_var.set("Error occurred. Please try again.")

    def open_file(self, path: str):
        """Open the created PDF file using the default system application."""
        try:
            import platform
            import subprocess
            
            if platform.system() == 'Darwin':       # macOS
                subprocess.run(['open', path])
            elif platform.system() == 'Windows':     # Windows
                os.startfile(path)
            else:                                   # Linux variants
                subprocess.run(['xdg-open', path])
        except Exception as e:
            self.show_error("Error opening PDF", str(e))

    def apply_styles(self):
        """Apply custom styles to the application."""
        style = ttk.Style(self)
        style.theme_use("clam")

        # Configure frame styles
        style.configure("TFrame", background="#f0f0f0")
        style.configure("Selected.TFrame", background="#e1f5fe")
        
        # Configure label styles
        style.configure("TLabel", background="#f0f0f0", font=("Arial", 10))
        
        # Configure button styles
        style.configure("TButton", 
                       padding=5,
                       font=("Arial", 10))
        
        # Configure accent button style
        style.configure("Accent.TButton",
                       background="#007bff",
                       foreground="white",
                       padding=10,
                       font=("Arial", 10, "bold"))
        
        style.map("Accent.TButton",
                 background=[("active", "#0056b3"),
                            ("disabled", "#cccccc")],
                 foreground=[("disabled", "#666666")])
        
        # Configure progress bar style
        style.configure("Horizontal.TProgressbar",
                       background="#007bff",
                       troughcolor="#f0f0f0",
                       bordercolor="#cccccc",
                       lightcolor="#ffffff",
                       darkcolor="#0056b3")

if __name__ == "__main__":
    app = ImageToPdfConverter()
    app.mainloop()