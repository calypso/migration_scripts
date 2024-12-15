import subprocess
import os
import requests

# Replace these with your GitHub Enterprise Cloud credentials
GITHUB_ORG = "your_github_org"  # Replace with your GitHub organization name
GITHUB_TOKEN = "your_github_token"  # Replace with your GitHub personal access token

# Replace these with your Bitbucket credentials
BITBUCKET_USERNAME = "your_bitbucket_username"  # Replace with your Bitbucket username
BITBUCKET_APP_PASSWORD = "your_bitbucket_app_password"  # Replace with your Bitbucket app password
BITBUCKET_ORG = "your_bitbucket_org"  # Replace with your Bitbucket organization name
REPO_LIST = "your_repo_list.txt" # Replace with repo list

def migrate_issues(repo_name):
    """Migrate issues from Bitbucket to GitHub."""
    try:
        # Get issues from Bitbucket
        bitbucket_issues_url = f"https://api.bitbucket.org/2.0/repositories/{BITBUCKET_ORG}/{repo_name}/issues"
        response = requests.get(bitbucket_issues_url, auth=(BITBUCKET_USERNAME, BITBUCKET_APP_PASSWORD))
        response.raise_for_status()
        issues = response.json().get("values", [])

        for issue in issues:
            # Prepare the issue data for GitHub
            issue_data = {
                "title": issue.get("title"),
                "body": issue.get("content", {}).get("raw", "") + f"\n\nImported from Bitbucket. Original ID: {issue.get('id')}",
                "labels": ["imported"]
            }

            # Create the issue in GitHub
            github_issues_url = f"https://api.github.com/repos/{GITHUB_ORG}/{repo_name}/issues"
            headers = {"Authorization": f"token {GITHUB_TOKEN}"}
            github_response = requests.post(github_issues_url, json=issue_data, headers=headers)

            if github_response.status_code == 201:
                print(f"Successfully migrated issue: {issue.get('title')}")
            else:
                print(f"Failed to migrate issue: {issue.get('title')} ({github_response.status_code})")
    except Exception as e:
        print(f"Error migrating issues for {repo_name}: {e}")

def configure_git_lfs():
    """Configure Git LFS for handling large files."""
    subprocess.run(["git", "lfs", "install"], check=True)
    print("Git LFS configured.")

def migrate_large_files_to_lfs():
    """Identify and migrate large files to Git LFS."""
    try:
        # Find large files (>100MB)
        result = subprocess.run(
            ["git", "rev-list", "--objects", "--all"],
            stdout=subprocess.PIPE,
            text=True,
            check=True
        )
        large_files = [
            line.split(" ")[1] for line in result.stdout.splitlines()
            if subprocess.run(["git", "cat-file", "-s", line.split(" ")[0]],
                              stdout=subprocess.PIPE, text=True).stdout.strip() > "104857600"
        ]

        if not large_files:
            print("No large files found exceeding 100MB.")
            return

        for large_file in large_files:
            subprocess.run(["git", "lfs", "track", large_file])
            print(f"Tracked {large_file} with Git LFS.")

        # Add .gitattributes
        subprocess.run(["git", "add", ".gitattributes"], check=True)
        subprocess.run(["git", "commit", "-m", "Track large files with Git LFS"], check=True)

    except subprocess.CalledProcessError as e:
        print(f"Error identifying or tracking large files: {e}")


def clone_and_migrate(repo_name):
    """Clone a Bitbucket repository and push it to GitHub."""
    try:
        # Clone the repository from Bitbucket
        bitbucket_url = f"https://{BITBUCKET_USERNAME}:{BITBUCKET_APP_PASSWORD}@bitbucket.org/{BITBUCKET_ORG}/{repo_name}.git"
        subprocess.run(["git", "clone", bitbucket_url], check=True)

        # Change into the repository directory
        os.chdir(repo_name)

        # Configure Git LFS
        configure_git_lfs()

        # Check for large files and track them with LFS
        migrate_large_files_to_lfs()

        # Push the repository to GitHub
        github_url = f"https://{GITHUB_TOKEN}@github.com/{GITHUB_ORG}/{repo_name}.git"
        subprocess.run(["git", "remote", "set-url", "origin", github_url], check=True)
        subprocess.run(["git", "push", "--all"], check=True)  # Push branches
        subprocess.run(["git", "push", "--tags"], check=True)  # Push tags

        print(f"Successfully migrated {repo_name} to GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"Error migrating {repo_name}: {e}")
    finally:
        # Return to the original directory and clean up
        os.chdir("..")
        subprocess.run(["rm", "-rf", repo_name], check=True)

def main():
    # Read the repository names from the file
    with open("{REPO_LIST}", "r") as file:
        repo_names = [line.strip() for line in file if line.strip()]

    print(f"Starting migration of {len(repo_names)} repositories...")

    for repo_name in repo_names:
        print(f"Migrating {repo_name}...")
        clone_and_migrate(repo_name)

        print(f"Migrating issues for {repo_name}...")
        migrate_issues(repo_name)

    print("Migration completed.")

if __name__ == "__main__":
    main()
