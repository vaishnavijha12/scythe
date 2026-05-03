"""
    User interface helpers for rendering scan/clean output.
"""
from pathlib import Path
from typing import List, Optional, Dict, Any
from collections import defaultdict

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.rule import Rule
from rich.tree import Tree
from rich import box
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from scythe.models.models import ScanResult, Project
from scythe.logger.logger import get_logger

console = Console()
logger = get_logger()


def display_run_header(
        command: str,
        path: Path,
        filters: Optional[Dict[str, Any]] = None,
) -> None:
    """
        Render the top-of-run context block.

        `command` is the verb being run ("scan", "clean"). `path` is the
        resolved target. `filters` is a mapping of label -> value rendered
        as a single dim line; entries with falsy values are omitted.
    """
    console.print()
    console.print(f"[bold cyan]scythe {command}[/bold cyan] [white]{path}[/white]")

    if filters:
        chips = [f"{label}: {value}" for label, value in filters.items() if value]
        if chips:
            console.print(f"[dim]{'  ·  '.join(chips)}[/dim]")
    console.print(Rule(style="dim"))


def display_scan_headline(result: ScanResult) -> None:
    """Single-line headline summarizing the scan result."""
    if result.total_projects == 0:
        console.print()
        console.print("[yellow]No projects found.[/yellow]")
        return

    total_artifacts = sum(p.artifact_count for p in result.projects)
    console.print()
    console.print(
        f"[bold green]Found {result.total_projects} project(s)[/bold green] "
        f"[dim]·[/dim] "
        f"[bold]{result.total_artifact_size_formatted}[/bold] reclaimable "
        f"[dim]across {total_artifacts} artifact(s)[/dim]"
    )
    console.print()


def display_scan_footer(result: ScanResult) -> None:
    """Single-line stats footer for scan."""
    parts = [
        f"{result.directories_scanned} dirs",
        f"{result.files_scanned} files",
        f"{result.scan_duration:.2f}s",
    ]
    if result.errors:
        parts.append(f"[red]{len(result.errors)} error(s)[/red]")
    console.print()
    console.print(f"[dim]{'  ·  '.join(parts)}[/dim]")


def display_scan_result(
        result: ScanResult,
        scan_path: Path,
        show_artifacts: bool = True,
        format: str = "table"
) -> None :
    """
        Render the scan result body (headline + table/tree/compact + footer).
    """
    display_scan_headline(result)

    if result.total_projects == 0:
        return

    if format == "tree" :
        display_tree_view(result, scan_path)
    elif format == "compact" :
        display_compact_view(result, scan_path)
    else: display_table_view(result, scan_path)

    display_scan_footer(result)

def display_table_view(result: ScanResult, scan_path: Path) -> None:
    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), show_edge=False)
    table.add_column("Type", style="cyan", no_wrap=True)
    table.add_column("Path", style="white")
    table.add_column("Artifacts", style="yellow", justify="right")
    table.add_column("Size", style="green", justify="right")
    table.add_column("Last modified", style="dim", no_wrap=True)

    for project in result.projects :
        try:
            relative_path = project.path.relative_to(scan_path)
        except ValueError :
            relative_path = project.path

        artifact_count = len(project.artifacts)
        artifact_display = f"{artifact_count}" if artifact_count  > 0 else "[dim]—[/dim]"

        size_display = project.total_size_formatted if project.total_artifact_size > 0 else "[dim]—[/dim]"

        last_modified = "N/A"

        if project.artifacts :
            most_recent = max(project.artifacts, key=lambda a: a.last_modified)
            days_ago = (result.scan_date - most_recent.last_modified).days

            if days_ago == 0 :
                last_modified = "Today"
            elif days_ago == 1 :
                last_modified = "Yesterday"
            elif days_ago < 7 :
                last_modified = f"{days_ago} days ago"
            elif days_ago < 30 :
                last_modified = f"{days_ago // 7} weeks ago"
            else :
                last_modified = f"{days_ago // 30} months ago"

        table.add_row(
            project.project_type.display_name,
            str(relative_path),
            artifact_display,
            size_display,
            last_modified
        )
    console.print(table)


def display_tree_view(result: ScanResult, scan_path: Path) -> None:
    tree = Tree(
        f"[bold cyan]{scan_path.name}[/bold cyan]",
        guide_style="dim"
    )

    project_by_type = defaultdict(list)

    for project in result.projects :
        project_by_type[project.project_type].append(project)

    for project_type, projects in project_by_type.items() :
        type_branch = tree.add(
            f"[cyan]{project_type.display_name}[/cyan] ({len(projects)} projects)"
        )

        for project in projects :
            try:
                relative_path = project.path.relative_to(scan_path)
            except ValueError :
                relative_path = project.path

            project_info = f"[white]{relative_path}[/white]"

            if project.artifacts :
                project_info += f" [yellow]({len(project.artifacts)} artifacts, {project.total_size_formatted})[/yellow]"
            project_branch = type_branch.add(project_info)

            for artifact in project.artifacts[:5] :
                project_branch.add(
                    f"[dim] {artifact.artifact_type}[/dim] [green]{artifact.size_formatted}"
                )

            if len(project.artifacts) > 5 :
                project_branch.add(f"[dim] ... and {len(project.artifacts) - 5} more artifacts [/dim]")

    console.print(tree)


def display_compact_view(result: ScanResult, scan_path: Path) -> None:
    console.print("[bold cyan]Projects detected:[/bold cyan]")
    console.print()

    for i, project in enumerate(result.projects, 1) :
        try:
            relative_path = project.path.relative_to(scan_path)

        except ValueError :
            relative_path = project.path

        artifact_info = ""

        if project.artifacts :
            artifact_info = f" • [yellow]{len(project.artifacts)} artifact(s)[/yellow] • [green]{project.total_size_formatted}[/green]"

        console.print(
            f"{i:2d}. [cyan]{project.project_type.display_name:12}[/cyan] "
            f"[white]{relative_path}[/white]"
            f"{artifact_info}"
        )


def display_errors(errors: List[str], max_display: int = 5 ) -> None:
    console.print()
    console.print("[bold red]Errors:[/bold red]")

    for error in errors :
        console.print(f"  [red]•[/red] {error}")

    if len(errors) > max_display:
        console.print(f"  [dim]... and {len(errors) - max_display} more[/dim]")


def interactive_select_project(
        projects: List[Project],
        scan_path: Path,
) -> List[Project] :
    """
        Interactive mode to select project to clean
        return: a List of projects
    """

    if not projects :
        console.print("[yellow]Nothing to select.[/yellow]")
        return []

    console.print()
    console.print("[bold cyan]Interactive mode — select projects to clean[/bold cyan]")
    console.print("[dim]Enter project numbers (e.g. 1,3-5) or 'all'.[/dim]")

    table = Table(box=box.SIMPLE_HEAD, padding=(0, 2), show_edge=False)
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Type", style="cyan")
    table.add_column("Path", style="white")
    table.add_column("Artifacts", style="yellow", justify="right")
    table.add_column("Size", style="green", justify="right")

    for i, project in enumerate(projects, 1) :
        try:
            relative_path = project.path.relative_to(scan_path)

        except ValueError :
            relative_path = project.path

        table.add_row(
            str(i),
            project.project_type.display_name,
            str(relative_path),
            str(len(project.artifacts)),
            project.total_size_formatted
        )

    console.print(table)
    console.print()

    #Ask for selection

    while True :
        selection = Prompt.ask(
            "[bold cyan]Selection[/bold cyan]",
            default="all"
        )

        try:
            selected_indices = parse_selection(selection, len(projects))
            selected_projects = [projects[i] for i in selected_indices]

            total_size = sum(p.total_artifact_size for p in selected_projects)
            from scythe.utils.utils import format_size

            console.print()
            console.print(
                f"[yellow]→ {len(selected_projects)} project(s) selected "
                f"({format_size(total_size)} to free)[/yellow]"
            )

            return selected_projects
        except ValueError as e :
            console.print(f"[red]Invalid selection: {e}[/red]")
            continue


def parse_selection(selection: str, max_index: int)  -> List[int]:
    selection = selection.strip().lower()

    if selection == "all" :
        return list(range(max_index))

    indices = set()

    for part in selection.split(',') :
        part = part.strip()

        if '-' in part :
            start, end = part.split('-', 1)
            start_idx = int(start.strip()) - 1
            end_idx = int(end.strip()) - 1

            if start_idx < 0 or end_idx >= max_index or start_idx > end_idx:
                raise ValueError(f"Invalid range: {part}")

            indices.update(range(start_idx, end_idx + 1))

        else :
            idx = int(part) - 1
            if idx < 0 or idx >= max_index:
                raise ValueError(f"Out of index: {part}")
            indices.add(idx)

    return sorted(list(indices))


def confirm_action(
        action: str,
        details: str = "",
        default: bool = True
)-> bool:

    """
        Confirm an action before the action
    """

    console.print()
    console.print()
    if details:
        console.print(f"[yellow]{details}[/yellow]")

    return Confirm.ask(
        f"[bold cyan]{action}[/bold cyan]",
        default=default
    )


def display_clean_plan(
        projects: List[Project],
        total_size_formatted: str,
        total_artifacts: int,
        trash: bool,
        dry_run: bool,
) -> None:
    """Headline before the user confirms a clean run."""
    if dry_run:
        mode = "[yellow]DRY-RUN[/yellow]"
    elif trash:
        mode = "[cyan]recoverable via [bold]scythe restore[/bold][/cyan]"
    else:
        mode = "[red]permanent[/red]"

    console.print()
    console.print(
        f"[bold]{len(projects)} project(s)[/bold] [dim]·[/dim] "
        f"[bold]{total_size_formatted}[/bold] to free "
        f"[dim]across {total_artifacts} artifact(s) · {mode}[/dim]"
    )
    console.print()


def display_clean_footer(
        artifacts_deleted: int,
        artifacts_total: int,
        space_freed_formatted: str,
        duration: float,
        dry_run: bool,
        trashed: bool,
        skipped: int = 0,
        errors: int = 0,
) -> None:
    """One-line recap after a clean run."""
    if dry_run:
        verb = "[bold green]Would free[/bold green]"
    elif trashed:
        verb = "[bold green]Trashed[/bold green]"
    else:
        verb = "[bold green]Freed[/bold green]"

    parts = [
        f"{verb} [bold]{space_freed_formatted}[/bold]",
        f"{artifacts_deleted}/{artifacts_total} artifacts",
        f"{duration:.2f}s",
    ]
    if skipped:
        parts.append(f"[yellow]{skipped} skipped[/yellow]")
    if errors:
        parts.append(f"[red]{errors} error(s)[/red]")

    console.print()
    console.print('  [dim]·[/dim]  '.join(parts))


def display_summary_panel(
        title: str,
        content: str,
        style: str = "cyan"
)-> None:
    console.print()
    console.print(
        Panel(
            content,
            title=f"[bold]{title}[/bold]",
            border_style=style,
            padding=(1, 2)
        )
    )


def progress_bar(description: str = "Processing ...") -> Progress:

    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        console=console
    )
