import multiprocessing

try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    pass  # HEIC support unavailable; install pillow-heif to enable it

if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller on Windows
    from ui.app import App
    App().mainloop()
