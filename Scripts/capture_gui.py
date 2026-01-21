#!/usr/bin/python3
import tkinter as tk
from tkinter import font

class StickyNoteCapture:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Quick Capture")
        
        # Make it look like a sticky note
        self.bg_color = "#FEF9C3"  # Light yellow
        self.text_color = "#1F2937" # Dark gray
        
        self.root.configure(bg=self.bg_color)
        
        # Position slightly above center
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        x = (screen_width - 400) // 2
        y = (screen_height - 400) // 3
        self.root.geometry(f"400x150+{x}+{y}")
        
        # Configure font
        self.custom_font = font.Font(family="Helvetica", size=16)
        
        # Text Area
        self.text_area = tk.Text(
            self.root,
            font=self.custom_font,
            bg=self.bg_color,
            fg=self.text_color,
            insertbackground=self.text_color, # Cursor color
            relief="flat",
            padx=15,
            pady=15,
            wrap="word",
            highlightthickness=0
        )
        self.text_area.pack(fill="both", expand=True)
        self.text_area.focus_set()
        
        # Bindings
        self.text_area.bind("<Command-Return>", self.save_and_exit)
        self.text_area.bind("<KeyRelease>", self.auto_resize)
        self.root.bind("<Escape>", lambda e: self.root.quit())
        
        # Placeholder behavior
        self.placeholder = "Type your thought...\n(Cmd+Enter to save)"
        self.text_area.insert("1.0", self.placeholder)
        self.text_area.config(fg="#9CA3AF")
        self.text_area.bind("<FocusIn>", self.clear_placeholder)
        
        self.result = None

    def clear_placeholder(self, event):
        if self.text_area.get("1.0", "end-1c") == self.placeholder:
            self.text_area.delete("1.0", "end")
            self.text_area.config(fg=self.text_color)

    def auto_resize(self, event=None):
        # Calculate required height
        # Simple heuristic: count lines
        content = self.text_area.get("1.0", "end-1c")
        lines = content.count('\n') + 1
        
        # Approximate pixel height per line (depends on font size)
        line_height = 25 
        padding = 40
        min_height = 150
        max_height = 600
        
        new_height = (lines * line_height) + padding
        
        if new_height < min_height:
            new_height = min_height
        if new_height > max_height:
            new_height = max_height
            
        current_geo = self.root.geometry()
        current_width = current_geo.split('x')[0]
        # Keep x,y position
        x = self.root.winfo_x()
        y = self.root.winfo_y()
        
        self.root.geometry(f"{current_width}x{new_height}+{x}+{y}")

    def save_and_exit(self, event=None):
        content = self.text_area.get("1.0", "end-1c")
        if content and content != self.placeholder:
            self.result = content
            print(content) # Print to stdout
        self.root.destroy()

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    app = StickyNoteCapture()
    app.run()
