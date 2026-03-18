import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()  # required for PyInstaller on Windows
    from ui.app import App
    App().mainloop()
