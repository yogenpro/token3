"""Resolve a main-only Pages snapshot; automatic releases must be data-only.

The controller runs trusted default-branch code. No artifact, log or provider
response can supply executable code or a release SHA. Manual releases stay
pinned to their dispatch SHA; automatic releases use the collector's pushed SHA.
"""
import json
import os
import re
import subprocess

SHA = re.compile(r"[a-f0-9]{40}")


def api(path):
    result = subprocess.run(["gh", "api", path], text=True, capture_output=True, timeout=30)
    if result.returncode:
        raise RuntimeError("Unable to verify GitHub publication metadata")
    return json.loads(result.stdout)


def git(*args):
    result = subprocess.run(["git", *args], text=True, capture_output=True, timeout=10)
    if result.returncode:
        raise RuntimeError("Unable to verify publication commit ancestry")
    return result.stdout


def latest_successful_deployment(repository):
    # Bound API work and fail closed rather than assuming an unknown baseline.
    for page in range(1, 6):
        deployments = api(f"repos/{repository}/deployments?environment=github-pages&per_page=100&page={page}")
        if not isinstance(deployments, list):
            raise ValueError("Invalid deployment history")
        for deployment in deployments:
            if deployment.get("environment") != "github-pages":
                continue
            number = deployment.get("id")
            if isinstance(number, bool) or not isinstance(number, int) or number <= 0:
                raise ValueError("Invalid deployment identity")
            statuses = api(f"repos/{repository}/deployments/{number}/statuses?per_page=100")
            if not isinstance(statuses, list):
                raise ValueError("Invalid deployment status history")
            # A successful older deployment may subsequently be marked inactive.
            if any(s.get("state") == "success" for s in statuses):
                sha = deployment.get("sha", "")
                if not SHA.fullmatch(sha):
                    raise ValueError("Invalid published commit identity")
                return sha
        if len(deployments) < 100:
            break
    return None


def resolve(repository, branch, dispatch_sha, collection_sha=""):
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository) or branch != "refs/heads/main":
        raise ValueError("Publication is restricted to the repository's main branch")
    if not SHA.fullmatch(dispatch_sha):
        raise ValueError("Invalid dispatch commit")
    if not collection_sha:
        return dict(publish=True, sha=dispatch_sha, mode="manual", reason="Explicit manual dispatch")
    if not SHA.fullmatch(collection_sha):
        raise ValueError("Invalid collection commit")
    tip = api(f"repos/{repository}/git/ref/heads/main")["object"]["sha"]
    if tip != collection_sha:
        return dict(publish=False, reason="Main advanced after collection; no older snapshot will be published")
    baseline = latest_successful_deployment(repository)
    if baseline is None:
        return dict(publish=False, reason="A reviewed manual release is required before automatic data publication")
    # A newer deployment or unrelated history must never be rolled back.
    if subprocess.run(["git", "merge-base", "--is-ancestor", baseline, collection_sha], capture_output=True, timeout=10).returncode:
        return dict(publish=False, reason="Published baseline is not an ancestor of this collection")
    paths = [p for p in git("diff", "--no-ext-diff", "--name-only", "-z", baseline, collection_sha, "--").split("\0") if p]
    if any(not path.startswith("data/") for path in paths):
        return dict(publish=False, reason="Unpublished code, configuration or documentation changes require a reviewed manual release")
    return dict(publish=True, sha=collection_sha, mode="automatic", reason="Data-only update from successful strict collection")


def main():
    result = resolve(os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_REF"],
                     os.environ["GITHUB_SHA"], os.environ.get("COLLECTION_SHA", ""))
    print(result["reason"])
    with open(os.environ["GITHUB_OUTPUT"], "a") as out:
        out.write("publish={}\nsha={}\nmode={}\n".format(str(result["publish"]).lower(), result.get("sha", ""), result.get("mode", "")))
    with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as out:
        out.write("### Pages publication\n\n" + result["reason"] + "\n")


if __name__ == "__main__":
    main()
