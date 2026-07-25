# Path: utils/ui.py
from rich.console import Console

console = Console()

class CLI:
    @staticmethod
    def status(msg: str, spinner: str = "dots"):
        return console.status(f"[bold cyan]{msg}[/bold cyan]", spinner=spinner)
        
    @staticmethod
    def print_header(msg: str):
        console.print(f"\n[bold magenta]=== {msg} ===[/bold magenta]\n")
