import click
import time
import os
import re
import csv
import requests
from datetime import datetime
from docx import Document


# Enhancement: keep log filenames and headers in one place.
# Why necessary: the original code repeated CSV header strings manually, which makes
# future changes error-prone and can easily break report parsing.
QUANTITATIVE_LOG = "writing_stats_quantitative.csv"
QUALITATIVE_LOG = "writing_stats_qualitative.csv"

QUANTITATIVE_HEADER = [
    "timestamp",
    "word_count",
    "delta",
    "section_count",
    "active_section",
]

QUALITATIVE_HEADER = [
    "timestamp",
    "writing_score",
    "went_well",
    "improvements",
]

# Enhancement: compile the word-count regex once.
# Why necessary: monitor runs repeatedly, so recompiling the same regex every
# interval is unnecessary work.
WORD_RE = re.compile(r"\b\w+\b", flags=re.UNICODE)


def ensure_csv(path, header):
    """Create a CSV file with a header if it does not already exist."""
    # Enhancement: centralize CSV creation.
    # Why necessary: both quantitative and qualitative logs need the same safe
    # behavior: create parent folders if needed, write exactly one header, and
    # use UTF-8 so section names and reflections are not corrupted.
    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(header)


def count_words(text):
    """Count word-like tokens in a text string."""
    # Enhancement: put word-count logic in one function.
    # Why necessary: this makes the counting rule explicit and avoids hidden
    # differences if word counting is reused later.
    return len(WORD_RE.findall(text))


def generate_report_logic(log_path):
    """Helper to generate the ASCII report."""
    daily_stats = {}
    if not os.path.exists(log_path):
        click.echo("No log file found to generate report.")
        return

    # Enhancement: read CSV with DictReader validation and UTF-8.
    # Why necessary: the original assumed the file always had timestamp and delta
    # columns. A wrong CSV would crash instead of giving a useful CLI error.
    with open(log_path, mode="r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required_columns = {"timestamp", "delta"}
        if not required_columns.issubset(reader.fieldnames or []):
            raise click.ClickException("This does not look like a Writeous quantitative log.")

        for row in reader:
            timestamp = row.get("timestamp", "").strip()
            delta_raw = row.get("delta", "0").strip()

            if not timestamp:
                continue

            try:
                delta = int(delta_raw)
            except ValueError:
                # Enhancement: skip malformed rows rather than killing the report.
                # Why necessary: long-running logs can contain manual edits or bad
                # rows; one bad row should not make the whole report unusable.
                continue

            if delta > 0:
                date = timestamp.split(" ")[0]
                daily_stats[date] = daily_stats.get(date, 0) + delta

    if not daily_stats:
        click.echo("No positive progress data found yet.")
        return

    click.echo(click.style("\n📈 DAILY PROGRESS OVERVIEW\n", bold=True, underline=True))
    max_val = max(daily_stats.values())
    chart_width = 40

    for date in sorted(daily_stats.keys()):
        words = daily_stats[date]
        bar_len = int((words / max_val) * chart_width) if max_val > 0 else 0
        bar = click.style("█" * bar_len, fg="yellow")
        click.echo(f"{date} | {bar} {words} words")


def get_docx_metrics(filepath):
    """
    Parses a .docx file to return total word count, including revision-tracked
    additions and deletions.
    """
    try:
        doc = Document(filepath)
        sections = {}
        current_section = "Front Matter"
        sections[current_section] = 0
        total_words = 0

        for p in doc.paragraphs:
            # 1. Update Section Context
            style_name = getattr(p.style, "name", "") or ""
            if style_name.startswith("Heading"):
                current_section = p.text.strip() if p.text.strip() else "Untitled Section"
                if current_section not in sections:
                    sections[current_section] = 0
                continue

            # 2. Extract ALL text nodes from the XML (Normal, Inserted, and Deleted)
            # w:t = normal text
            # w:ins//w:t = tracked additions
            # w:delText = tracked deletions
            #
            # Enhancement retained from your enhanced version: read XML text nodes
            # instead of only p.text.
            # Why necessary: python-docx's visible paragraph text can miss some
            # revision-tracked content. For a writing-progress tracker, seeing
            # tracked edits makes the progress signal more useful.
            all_text_nodes = p._element.xpath(".//w:t | .//w:delText")
            paragraph_content = " ".join([node.text for node in all_text_nodes if node.text])

            # Enhancement: count only real word-like tokens.
            # Why necessary: punctuation-only XML fragments and empty artifacts
            # should not inflate the word count.
            words = count_words(paragraph_content)

            sections[current_section] = sections.get(current_section, 0) + words
            total_words += words

        return total_words, sections
    except Exception as e:
        # Enhancement: show the real read error instead of silently returning None.
        # Why necessary: silent failure makes debugging hard when the document is
        # locked, corrupted, or not a valid .docx file.
        click.echo(click.style(f"Could not read document: {e}", fg="red"), err=True)
        return None, None


def find_active_section(current_sections, last_sections):
    """Return the section with the largest positive growth since last check."""
    # Enhancement: isolate active-section calculation.
    # Why necessary: it keeps monitor() readable while preserving the original
    # behavior of reporting the section with the biggest positive delta.
    active_section = "None"
    max_growth = 0

    for sec, count in current_sections.items():
        growth = count - last_sections.get(sec, 0)
        if growth > max_growth:
            max_growth = growth
            active_section = sec

    return active_section, max_growth


def format_delta(delta):
    """Format a word-count delta for terminal output."""
    # Enhancement: show negative deltas in red.
    # Why necessary: negative delta usually means revision/deletion, which is not
    # failure, but it should be visually distinct from no change.
    if delta > 0:
        return click.style(f" (+{delta})", fg="green")
    if delta < 0:
        return click.style(f" ({delta})", fg="red")
    return click.style(" (0)", fg="white")


def goal_status(session_delta, goal):
    """Return session-goal completion text based on new words this session."""
    # Enhancement: calculate goal progress from session delta, not total document words.
    # Why necessary: the original used current_count / goal, so a manuscript that
    # already had many words could show 100% before the user wrote anything.
    if goal <= 0:
        return ""

    positive_delta = max(0, session_delta)
    percent = min(100, int((positive_delta / goal) * 100))
    return f" | Goal: {percent}% ({positive_delta}/{goal})"


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Writeous: a progress tracker for manuscript writing."""
    pass


@main.command("monitor")
@click.argument("doc_path", type=click.Path(exists=True))
@click.argument("output_folder", type=click.Path())
@click.option("--interval", default=60, help="Check interval in seconds.")
@click.option("--goal", default=0, help="Target word count for the session.")
@click.option("--colab", is_flag=True)
@click.option("--name", default="Writer", help="Your name in the Universe")
def monitor(doc_path, output_folder, interval, goal, colab, name):
    """Monitor Docx progress, section growth, and log to CSV."""
    click.clear()
    filename = os.path.basename(doc_path)

    if not filename.lower().endswith(".docx"):
        click.echo(click.style("⚠️  Error: Section tracking currently only supports .docx files.", fg="red"))
        return

    # Enhancement: validate interval and goal early.
    # Why necessary: interval <= 0 creates a broken monitoring loop, and negative
    # goals make no practical sense for a writing target.
    if interval <= 0:
        raise click.ClickException("--interval must be greater than 0.")

    if goal < 0:
        raise click.ClickException("--goal cannot be negative.")

    click.echo(click.style(f"🕯Lantern Lit: Monitoring {filename}", fg="yellow", bold=True))
    if colab:
        click.echo(click.style(f">>> Colab mode on! Miauw {name} 😺<<<\nView at https://writeous.stijndenissen.me/universe", fg='yellow', bold=True))

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    log_file_quant = os.path.join(output_folder, QUANTITATIVE_LOG)
    ensure_csv(log_file_quant, QUANTITATIVE_HEADER)

    last_count, last_sections = get_docx_metrics(doc_path)
    if last_count is None:
        raise click.ClickException("Could not start monitoring because the document could not be read.")

    # Enhancement: store the initial count separately.
    # Why necessary: this allows the goal to measure new writing during this
    # session instead of comparing the whole manuscript against today's goal.
    initial_count = last_count

    click.echo(f"Starting words: {initial_count}")
    if goal > 0:
        click.echo(f"Session goal: {goal} new words")
    click.echo("Press Ctrl+C to end the session.\n")

    try:
        while True:
            current_count, current_sections = get_docx_metrics(doc_path)

            if current_count is not None:
                delta = current_count - last_count
                session_delta = current_count - initial_count

                # HEARTBEAT LOGIC
                # Preserved from the original CLI.
                # Why necessary: the user asked for the CLI to act exactly like
                # the original; removing this would break --colab behavior.
                if colab and delta != 0:
                    # We send a '1' if there is ANY change (add or delete)
                    try:
                        requests.post(
                            "https://writeous.stijndenissen.me/heartbeat",
                            json={"pulse": 1, "writer": name},
                            timeout=2,
                        )
                        click.echo(click.style("   ✨ Heartbeat sent to Universe", fg="magenta"))
                    except requests.RequestException:
                        # Enhancement: catch only request-related errors.
                        # Why necessary: bare except hides real programming bugs.
                        pass  # Silently fail if offline, same user-facing behavior as original.

                section_count = len(current_sections)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                active_section, section_growth = find_active_section(current_sections, last_sections)

                # Log to CSV
                with open(log_file_quant, "a", newline="", encoding="utf-8") as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, current_count, delta, section_count, active_section])

                # Terminal Dashboard
                status = f"[{timestamp[11:]}] Words: {current_count}"
                diff = format_delta(delta)
                goal_txt = goal_status(session_delta, goal)

                click.echo(status + diff + f" | Sections: {section_count} | \u0394Session:{format_delta(session_delta)}" + goal_txt)

                if section_growth > 0:
                    click.echo(click.style(f"   → Focus: {active_section} (+{section_growth})", fg="cyan"))

                last_count = current_count
                last_sections = current_sections

            time.sleep(interval)

    except KeyboardInterrupt:
        # Qualitative assessment
        log_file_qual = os.path.join(output_folder, QUALITATIVE_LOG)
        ensure_csv(log_file_qual, QUALITATIVE_HEADER)

        # New row
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Enhancement: use click.prompt instead of raw input().
        # Why necessary: click.prompt is consistent with Click CLIs and behaves
        # better with defaults, terminal handling, and future validation.
        writing_score = click.prompt("How would you rate your writing day today (0-10)?", default="", show_default=False)
        went_well = click.prompt("What went well?", default="", show_default=False)
        improvements = click.prompt("What would you like to improve?", default="", show_default=False)

        # Log
        with open(log_file_qual, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, writing_score, went_well, improvements])

        click.echo(click.style("\n🌙 Session ended. You showed up for writing ❤️", fg="red"))
        click.echo(click.style(f">> Your writing score: {writing_score}", fg="green"))
        click.echo(click.style(f">> Went well: {went_well}", fg="green"))
        click.echo(click.style(f">> Can be improved: {improvements}", fg="green"))

        generate_report_logic(log_file_quant)


@main.command("report")
@click.argument("log_path", type=click.Path(exists=True))
def report(log_path):
    """Generate a daily progress report from the CSV log."""
    generate_report_logic(log_path)


if __name__ == "__main__":
    main()
