# TODO: WHAT HAPPENS WHEN THERE IS NO COMMIT?
from datetime import datetime
from invoke import task
from pathlib import Path
import pandas as pd

from tasks.helpers import (
    authenticate, 
    parse_date,
    get_student_repos,
    get_org,
    choose_from_options,
    get_project_repo,
    is_github_classroom_child,
)
import tasks.settings as s

@task 
def check(c):
    "Check settings and configurations"
    errors = []
    try:
        import tasks.secrets as secrets
        if not hasattr(secrets, "GITHUB_ACCESS_TOKEN"):
            errors.append("tasks/secrets.py must define GITHUB_ACCESS_TOKEN")
    except ImportError:
        errors.append("tasks/secrets.py does not exist. It must define GITHUB_ACCESS_TOKEN")
    for f, cols in [
        ["ROSTER_FILE", ["login", "name", "section"]], 
        ["PROJECT_FILE", ["project_name", "repo"]],
    ]:
        if hasattr(s, f):
            if not Path(getattr(s, f)).exists():
                msg = "{} does not exist. It must have columns: {}."
                errors.append(msg.format(s.ROSTER_FILE, ", ".join(cols)))
            try:
                df = pd.read_csv(getattr(s, f))
                for col in cols:
                    if not hasattr(df, col):
                        errors.append("{} must contain a column for {}".format(f, col))
            except:
                errors.append("error reading {}".format(f))
        else:
            errors.append("tasks/settings.py must define {}".format(f))
    if len(errors):
        for err in errors:
            print(" - {}".format(err))
    else:
        print("ok")

@task(help={"section": "Filter by student section"})
def roster(c, section=None):
    "Show the roster"
    roster = pd.read_csv(s.ROSTER_FILE)
    if section:
        roster = roster[roster.section == section]
    print(roster)

latest_commit_help={
    "project": "Project index, or part of project name, or part of project repo name",
    "cached": "Use cached copy of students' project repo names",
    "section": "Filter by section",
    "outfile": "Save results to file instead of displaying",
    "order": "Column by which to sort results",
    "repo": "Display repo names",
    "hash": "Display commit hashes",
    "stats": "Display commit stats (addition, deletion line counts)",
    "url": "Display html url for commit",
    "message": "Display commit message",
    "message_length": "Display commit message length",
}
@task(help=latest_commit_help)
def latest_commit(c, 
    project, 
    cached=True,
    section=None, 
    outfile=None, 
    order='date',
    repo=False,
    hash=False, 
    stats=False,
    url=False,
    message=False,
    message_length=False,
):
    "Show each student's most recent commit"
    g = authenticate()
    project_repo = get_project_repo(project)
    roster = pd.read_csv(s.ROSTER_FILE)
    if section:
        roster = roster[roster.section == section]
    student_repos = get_student_repos(project_repo, roster.login.values, cached=cached)
    student_users = {login:g.get_user(login) for login in roster.login}
    latest_commits = []
        
    for login in roster.login:
        query_params = {}
        if len(student_repos.get(login, [])) > 0:
            repo_heads = [(r.get_branch('master').commit, r) for r in student_repos[login]]
            d, c, r = max((c.commit.author.date, c, r) for c, r in repo_heads)
            latest_commits.append((d, c, r))
        else:
            latest_commits.append((None, None, None))
    roster['date'] = [d if d else None for d, c, r in latest_commits]
    if repo:
        roster['repo'] = [r.full_name if r else None for d, c, r in latest_commits]
    if hash:
        roster['hash'] = [c.sha if c else None for d, c, r in latest_commits]
    if stats:
        roster['additions'] = [c.stats.additions if c else None for d, c, r in latest_commits]
        roster['deletions'] = [c.stats.deletions if c else None for d, c, r in latest_commits]
    if url:
        roster['commit_url'] = [c.html_url if c else None for d, c, r in latest_commits]
    if message:
        roster['message'] = [c.commit.message if c else None for d, c, r in latest_commits]
    if message_length:
        roster['message_length'] = [len(c.commit.message) if c else None for d, c, r in latest_commits]

    roster = roster.sort_values(order)
    if outfile:
        roster.to_csv(outfile)
    else:
        print("")
        print(roster)
        if message:
            print("\nCommit Messages")
            for ix, row in roster.iterrows():
                print("-" * 80)
                print("{} ({})\n".format(row.name, row.login))
                print(row.message)

@task
def clear_cache(c):
    "Delete the student project repo names cache file, if it exists"
    if Path(s.STUDENT_PROJECT_REPO_CACHE).exists():
        Path(s.STUDENT_PROJECT_REPO_CACHE).unlink()
