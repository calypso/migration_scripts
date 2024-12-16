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

# Path to the file containing repository names
REPOSITORIES_FILE = "recent_repositories.txt"

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
        large_files = []
        # Walk through the repository's working directory
        print("Scanning files in the repository for large files...")
        for root, _, files in os.walk("."):
            for file in files:
                file_path = os.path.join(root, file)
                # Exclude files in the .git directory
                if ".git" in file_path:
                    continue
                if os.path.isfile(file_path):  # Check if it's a file
                    file_size = os.path.getsize(file_path)
                    print(f"Checked file: {file_path} ({file_size / (1024 * 1024):.2f} MB)")
                    if file_size > 104857600:  # 100MB
                        large_files.append(file_path)
                        print(f"Identified large file: {file_path} ({file_size / (1024 * 1024):.2f} MB)")

        if not large_files:
            print("No large files found exceeding 100MB.")
            return

        for large_file in large_files:
            print(f"Tracking large file with Git LFS: {large_file}")
            subprocess.run(["git", "lfs", "track", large_file], check=True)
            subprocess.run(["git", "add", large_file], check=True)
            print(f"Added large file to Git: {large_file}")

        # Ensure .gitattributes is committed
        print("Adding .gitattributes to Git...")
        subprocess.run(["git", "add", ".gitattributes"], check=True)
        subprocess.run(["git", "commit", "-m", "Track large files with Git LFS"], check=True)
        print("Committed .gitattributes and large files.")

    except subprocess.CalledProcessError as e:
        print(f"Error identifying or tracking large files: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

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
    with open(REPOSITORIES_FILE, "r") as file:
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
