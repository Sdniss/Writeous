import click
import time
import os
import csv
from datetime import datetime
from docx import Document


def get_docx_metrics(filepath):
    """
    Parses a .docx file to return:
    1. Total word count
    2. Total number of sections (Heading styles)
    3. The name of the section currently being expanded (most words added)
    4. A dictionary of word counts per section
    """
    try:
        doc = Document(filepath)
        sections = {}
        current_section = "Front Matter"
        total_words = 0

        for p in doc.paragraphs:
            # Check for Heading styles
            if p.style.name.startswith('Heading'):
                current_section = p.text.strip() if p.text.strip() else "Untitled Section"
                #if current_section not in sections:
                sections[current_section] = 0
            else:
                words = len(p.text.split())
                sections[current_section] = sections.get(current_section, 0) + words
                total_words += words

        return total_words, sections
    except Exception:
        return None, None


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Writeous: a progress tracker for manuscript writing."""
    pass


@main.command("monitor")
@click.argument('doc_path', type=click.Path(exists=True))
@click.argument('output_folder', type=click.Path())
@click.option('--interval', default=60, help='Check interval in seconds.')
@click.option('--goal', default=0, help='Target word count for the session.')
def monitor(doc_path, output_folder, interval, goal):
    """Monitor Docx progress, section growth, and log to CSV."""
    click.clear()
    filename = os.path.basename(doc_path)

    if not filename.lower().endswith('.docx'):
        click.echo(click.style("⚠️  Error: Section tracking currently only supports .docx files.", fg='red'))
        return

    click.echo(click.style(f"🕯️  Lantern Lit: Monitoring {filename}", fg='yellow', bold=True))

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    log_file = os.path.join(output_folder, "writing_stats.csv")

    # New CSV Header: added section_count and active_section
    if not os.path.exists(log_file):
        with open(log_file, 'w', newline='') as f:
            f.write("timestamp,word_count,delta,section_count,active_section\n")

    last_count, last_sections = get_docx_metrics(doc_path)

    try:
        while True:
            current_count, current_sections = get_docx_metrics(doc_path)

            if current_count is not None:
                delta = current_count - last_count
                section_count = len(current_sections)
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                # Identify the active section (where delta > 0)
                active_section = "None"
                max_growth = 0
                for sec, count in current_sections.items():
                    growth = count - last_sections.get(sec, 0)
                    if growth > max_growth:
                        max_growth = growth
                        active_section = sec

                # Log to CSV
                with open(log_file, 'a', newline='') as f:
                    writer = csv.writer(f)
                    writer.writerow([timestamp, current_count, delta, section_count, active_section])

                # Terminal Dashboard
                status = f"[{timestamp[11:]}] Total: {current_count}"
                diff = click.style(f" (+{delta})" if delta > 0 else f" ({delta})", fg='green' if delta > 0 else 'white')

                goal_txt = ""
                if goal > 0:
                    percent = min(100, int((current_count / goal) * 100))
                    goal_txt = f" | Goal: {percent}%"

                click.echo(status + diff + goal_txt + f" | Sections: {section_count}")

                if delta > 0:
                    click.echo(click.style(f"   → Focus: {active_section}", fg='cyan'))

                last_count = current_count
                last_sections = current_sections

            time.sleep(interval)

    except KeyboardInterrupt:
        click.echo(click.style("\n🌙 Session ended.", fg='red'))


@main.command("report")
@click.argument('log_path', type=click.Path(exists=True))
def report(log_path):
    """Generate a daily progress report from the CSV log."""
    daily_stats = {}

    # Check if we have the new or old CSV format
    with open(log_path, mode='r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = row['timestamp'].split(' ')[0]
            delta = int(row['delta'])
            if delta > 0:
                daily_stats[date] = daily_stats.get(date, 0) + delta

    if not daily_stats:
        click.echo("No progress data found yet.")
        return

    click.echo(click.style("\n📈 DAILY PROGRESS OVERVIEW\n", bold=True, underline=True))
    max_val = max(daily_stats.values())
    chart_width = 40

    for date in sorted(daily_stats.keys()):
        words = daily_stats[date]
        bar_len = int((words / max_val) * chart_width) if max_val > 0 else 0
        bar = click.style("█" * bar_len, fg='yellow')
        click.echo(f"{date} | {bar} {words} words")


if __name__ == '__main__':
    main()