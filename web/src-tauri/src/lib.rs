use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::path::{Path, PathBuf};
use std::process::{Command, Output};
use tauri_plugin_shell::ShellExt;

#[derive(Debug, Deserialize)]
#[serde(rename_all = "camelCase")]
struct AnalyzeRequest {
    repository: String,
    session: Option<String>,
    agent: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct GitRemote {
    name: String,
    url: String,
    provider: String,
    transport: String,
}

#[derive(Debug, Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct RepositoryStatus {
    repository: String,
    branch: Option<String>,
    head: Option<String>,
    dirty: bool,
    changed_files: usize,
    staged_files: usize,
    untracked_files: usize,
    remote: Option<GitRemote>,
    upstream: Option<String>,
    ahead: u64,
    behind: u64,
}

#[derive(Debug, Deserialize)]
#[serde(rename_all = "lowercase")]
enum GitAction {
    Fetch,
    Pull,
    Push,
}

#[derive(Debug, Serialize)]
#[serde(rename_all = "camelCase")]
struct GitActionResult {
    message: String,
    output: String,
    status: RepositoryStatus,
}

#[tauri::command]
async fn select_repository() -> Option<String> {
    rfd::AsyncFileDialog::new()
        .set_title("Choose a Git repository")
        .pick_folder()
        .await
        .map(|handle| handle.path().to_string_lossy().into_owned())
}

#[tauri::command]
async fn select_session() -> Option<String> {
    rfd::AsyncFileDialog::new()
        .set_title("Choose a Claude Code or Codex transcript")
        .add_filter("JSONL transcript", &["jsonl"])
        .pick_file()
        .await
        .map(|handle| handle.path().to_string_lossy().into_owned())
}

#[tauri::command]
async fn analyze_repository(
    app: tauri::AppHandle,
    request: AnalyzeRequest,
) -> Result<Value, String> {
    let repository = canonical_repository(&request.repository)?;
    let mut args = vec!["--json".to_string()];
    if let Some(session) = request.session.filter(|value| !value.trim().is_empty()) {
        args.extend(["--session".to_string(), session]);
    }
    if let Some(agent) = request.agent.filter(|value| !value.trim().is_empty()) {
        if agent != "claude" && agent != "codex" {
            return Err(format!("Unsupported agent override: {agent}"));
        }
        args.extend(["--agent".to_string(), agent]);
    }

    // Packaged builds use the signed sidecar. Development builds fall back to the
    // source checkout, keeping the same JSON boundary in both environments.
    let sidecar = app
        .shell()
        .sidecar("binaries/overscope-engine")
        .map(|command| command.args(&args).current_dir(&repository));
    let output = match sidecar {
        Ok(command) => match command.output().await {
            Ok(value) => ProcessOutput {
                success: value.status.success(),
                stdout: value.stdout,
                stderr: value.stderr,
            },
            Err(_) => run_development_engine(repository.clone(), args.clone()).await?,
        },
        Err(_) => run_development_engine(repository.clone(), args.clone()).await?,
    };

    parse_report(output)
}

#[tauri::command]
async fn repository_status(repository: String) -> Result<RepositoryStatus, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let repository = canonical_git_repository(&repository)?;
        read_repository_status(&repository)
    })
    .await
    .map_err(|error| format!("Git status task failed: {error}"))?
}

#[tauri::command]
async fn run_git_action(repository: String, action: GitAction) -> Result<GitActionResult, String> {
    tauri::async_runtime::spawn_blocking(move || {
        let repository = canonical_git_repository(&repository)?;
        execute_git_action(&repository, action)
    })
    .await
    .map_err(|error| format!("Git operation task failed: {error}"))?
}

fn execute_git_action(repository: &Path, action: GitAction) -> Result<GitActionResult, String> {
    let before = read_repository_status(repository)?;
    let remote = before
        .remote
        .as_ref()
        .ok_or_else(|| "This repository has no configured Git remote.".to_string())?;

    let (label, args) = match action {
        GitAction::Fetch => (
            "Fetched remote state",
            vec!["fetch", "--prune", remote.name.as_str()],
        ),
        GitAction::Pull => {
            if before.dirty {
                return Err(
                    "Pull is disabled while the working tree has changes. Commit or stash them first."
                        .to_string(),
                );
            }
            if before.upstream.is_none() {
                return Err(
                    "This branch has no upstream. Push it once to establish tracking.".to_string(),
                );
            }
            ("Fast-forwarded local branch", vec!["pull", "--ff-only"])
        }
        GitAction::Push => {
            if before.branch.is_none() {
                return Err("Create or switch to a branch before pushing.".to_string());
            }
            if before.upstream.is_some() {
                (
                    "Pushed local commits",
                    vec!["push", remote.name.as_str(), "HEAD"],
                )
            } else {
                (
                    "Pushed branch and established tracking",
                    vec!["push", "--set-upstream", remote.name.as_str(), "HEAD"],
                )
            }
        }
    };

    let output = git_output(repository, &args)?;
    let detail = command_detail(&output);
    if !output.status.success() {
        return Err(format!("Git operation failed: {detail}"));
    }
    Ok(GitActionResult {
        message: label.to_string(),
        output: detail,
        status: read_repository_status(repository)?,
    })
}

struct ProcessOutput {
    success: bool,
    stdout: Vec<u8>,
    stderr: Vec<u8>,
}

impl From<Output> for ProcessOutput {
    fn from(value: Output) -> Self {
        Self {
            success: value.status.success(),
            stdout: value.stdout,
            stderr: value.stderr,
        }
    }
}

async fn run_development_engine(
    repository: PathBuf,
    args: Vec<String>,
) -> Result<ProcessOutput, String> {
    tauri::async_runtime::spawn_blocking(move || {
        if let Ok(path) = std::env::var("OVERSCOPE_ENGINE_PATH") {
            return Command::new(path)
                .args(&args)
                .current_dir(&repository)
                .output()
                .map(ProcessOutput::from)
                .map_err(|error| format!("Could not start OVERSCOPE_ENGINE_PATH: {error}"));
        }

        let project = Path::new(env!("CARGO_MANIFEST_DIR")).join("../..");
        let mut command = if project.join("pyproject.toml").is_file() {
            let mut value = Command::new("uv");
            value.arg("run").arg("--project").arg(project).arg("overscope");
            value
        } else {
            Command::new("overscope")
        };
        command
            .args(&args)
            .current_dir(&repository)
            .output()
            .map(ProcessOutput::from)
            .map_err(|error| {
                format!(
                    "Could not start the Overscope analyzer ({error}). Rebuild the bundled sidecar."
                )
            })
    })
    .await
    .map_err(|error| format!("Analyzer task failed: {error}"))?
}

fn parse_report(output: ProcessOutput) -> Result<Value, String> {
    let stdout = String::from_utf8_lossy(&output.stdout);
    if let Ok(value) = serde_json::from_str::<Value>(&stdout) {
        if output.success {
            return Ok(value);
        }
        if let Some(message) = value
            .get("error")
            .and_then(|error| error.get("message"))
            .and_then(Value::as_str)
        {
            return Err(message.to_string());
        }
    }
    let stderr = String::from_utf8_lossy(&output.stderr);
    let detail = if !stderr.trim().is_empty() {
        stderr.trim()
    } else if !stdout.trim().is_empty() {
        stdout.trim()
    } else {
        "the analyzer returned no output"
    };
    Err(format!("Overscope analysis failed: {detail}"))
}

fn canonical_repository(raw: &str) -> Result<PathBuf, String> {
    let path = PathBuf::from(raw);
    let canonical = path
        .canonicalize()
        .map_err(|error| format!("Repository path is unavailable: {error}"))?;
    if !canonical.is_dir() {
        return Err("Choose a directory containing a Git repository.".to_string());
    }
    Ok(canonical)
}

fn canonical_git_repository(raw: &str) -> Result<PathBuf, String> {
    let repository = canonical_repository(raw)?;
    let output = git_output(&repository, &["rev-parse", "--show-toplevel"])?;
    if !output.status.success() {
        return Err("Choose a folder inside a Git repository.".to_string());
    }
    let root = String::from_utf8_lossy(&output.stdout).trim().to_string();
    PathBuf::from(root)
        .canonicalize()
        .map_err(|error| format!("Could not resolve the Git repository root: {error}"))
}

fn git_output(repository: &Path, args: &[&str]) -> Result<Output, String> {
    Command::new("git")
        .args(args)
        .current_dir(repository)
        .env("GIT_TERMINAL_PROMPT", "0")
        .output()
        .map_err(|error| format!("Could not run Git: {error}"))
}

fn git_text(repository: &Path, args: &[&str]) -> Option<String> {
    let output = git_output(repository, args).ok()?;
    if !output.status.success() {
        return None;
    }
    let value = String::from_utf8_lossy(&output.stdout).trim().to_string();
    (!value.is_empty()).then_some(value)
}

fn command_detail(output: &Output) -> String {
    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
    match (stdout.is_empty(), stderr.is_empty()) {
        (false, false) => format!("{stdout}\n{stderr}"),
        (false, true) => stdout,
        (true, false) => stderr,
        (true, true) => "Git completed without additional output.".to_string(),
    }
}

fn read_repository_status(repository: &Path) -> Result<RepositoryStatus, String> {
    let status = git_output(
        repository,
        &["status", "--porcelain=v1", "--untracked-files=normal"],
    )?;
    if !status.status.success() {
        return Err(format!(
            "Could not inspect repository: {}",
            command_detail(&status)
        ));
    }
    let porcelain = String::from_utf8_lossy(&status.stdout);
    let mut changed_files = 0;
    let mut staged_files = 0;
    let mut untracked_files = 0;
    for line in porcelain.lines().filter(|line| line.len() >= 2) {
        changed_files += 1;
        let marker = &line[..2];
        if marker == "??" {
            untracked_files += 1;
        } else if marker.as_bytes()[0] != b' ' {
            staged_files += 1;
        }
    }

    let branch = git_text(repository, &["branch", "--show-current"]);
    let head = git_text(repository, &["rev-parse", "--short=10", "HEAD"]);
    let upstream = git_text(
        repository,
        &[
            "rev-parse",
            "--abbrev-ref",
            "--symbolic-full-name",
            "@{upstream}",
        ],
    );
    let (ahead, behind) = upstream
        .as_ref()
        .and_then(|_| {
            git_text(
                repository,
                &["rev-list", "--left-right", "--count", "HEAD...@{upstream}"],
            )
        })
        .and_then(|counts| parse_ahead_behind(&counts))
        .unwrap_or((0, 0));

    let remote_name = if git_text(repository, &["remote", "get-url", "origin"]).is_some() {
        Some("origin".to_string())
    } else {
        git_text(repository, &["remote"])
            .and_then(|remotes| remotes.lines().next().map(str::to_string))
    };
    let remote = remote_name.and_then(|name| {
        git_text(repository, &["remote", "get-url", &name]).map(|url| {
            let (provider, transport) = classify_remote(&url);
            GitRemote {
                name,
                url,
                provider: provider.to_string(),
                transport: transport.to_string(),
            }
        })
    });

    Ok(RepositoryStatus {
        repository: repository.to_string_lossy().into_owned(),
        branch,
        head,
        dirty: changed_files > 0,
        changed_files,
        staged_files,
        untracked_files,
        remote,
        upstream,
        ahead,
        behind,
    })
}

fn parse_ahead_behind(value: &str) -> Option<(u64, u64)> {
    let mut parts = value.split_whitespace();
    let ahead = parts.next()?.parse().ok()?;
    let behind = parts.next()?.parse().ok()?;
    Some((ahead, behind))
}

fn classify_remote(url: &str) -> (&'static str, &'static str) {
    let lower = url.to_ascii_lowercase();
    let provider = if lower.contains("github.com") {
        "GitHub"
    } else if lower.contains("gitlab.com") {
        "GitLab"
    } else if lower.contains("bitbucket.org") {
        "Bitbucket"
    } else {
        "Git remote"
    };
    let transport = if url.starts_with("git@") || url.starts_with("ssh://") {
        "SSH"
    } else if url.starts_with("http://") || url.starts_with("https://") {
        "HTTPS"
    } else {
        "Local"
    };
    (provider, transport)
}

#[tauri::command]
fn reveal_file(repository: String, relative_path: String) -> Result<(), String> {
    let root = canonical_repository(&repository)?;
    let requested = root.join(relative_path);
    let target = requested.canonicalize().unwrap_or(requested);
    if !target.starts_with(&root) {
        return Err("Refusing to reveal a path outside the selected repository.".to_string());
    }

    #[cfg(target_os = "macos")]
    let status = Command::new("open").arg("-R").arg(&target).status();

    #[cfg(target_os = "windows")]
    let status = {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x08000000;
        Command::new("explorer")
            .arg(format!("/select,{}", target.display()))
            .creation_flags(CREATE_NO_WINDOW)
            .status()
    };

    #[cfg(all(not(target_os = "macos"), not(target_os = "windows")))]
    let status = Command::new("xdg-open")
        .arg(target.parent().unwrap_or(&root))
        .status();

    status
        .map_err(|error| format!("Could not reveal the file: {error}"))
        .and_then(|result| {
            if result.success() {
                Ok(())
            } else {
                Err("The system file browser could not reveal this path.".to_string())
            }
        })
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![
            select_repository,
            select_session,
            analyze_repository,
            repository_status,
            run_git_action,
            reveal_file
        ])
        .run(tauri::generate_context!())
        .expect("error while running Overscope");
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::fs;
    use std::time::{SystemTime, UNIX_EPOCH};

    #[test]
    fn parses_successful_report() {
        let value = parse_report(ProcessOutput {
            success: true,
            stdout: br#"{"schema_version":"1.0"}"#.to_vec(),
            stderr: vec![],
        })
        .expect("valid report");
        assert_eq!(value["schema_version"], "1.0");
    }

    #[test]
    fn surfaces_structured_analyzer_error() {
        let error = parse_report(ProcessOutput {
            success: false,
            stdout: br#"{"error":{"message":"No session matched"}}"#.to_vec(),
            stderr: vec![],
        })
        .expect_err("error report");
        assert_eq!(error, "No session matched");
    }

    #[test]
    fn parses_git_divergence_counts() {
        assert_eq!(parse_ahead_behind("3\t2"), Some((3, 2)));
        assert_eq!(parse_ahead_behind("not-a-count"), None);
    }

    #[test]
    fn classifies_common_remote_urls() {
        assert_eq!(
            classify_remote("git@github.com:acme/api.git"),
            ("GitHub", "SSH")
        );
        assert_eq!(
            classify_remote("https://gitlab.com/acme/api.git"),
            ("GitLab", "HTTPS")
        );
        assert_eq!(classify_remote("../bare.git"), ("Git remote", "Local"));
    }

    #[test]
    fn reads_status_and_pushes_to_an_existing_local_remote() {
        let suffix = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("clock")
            .as_nanos();
        let root = std::env::temp_dir().join(format!("overscope-git-{suffix}"));
        let repository = root.join("work");
        let remote = root.join("remote.git");
        fs::create_dir_all(&repository).expect("fixture directory");

        let git = |directory: &Path, args: &[&str]| {
            let output = git_output(directory, args).expect("git available");
            assert!(output.status.success(), "{}", command_detail(&output));
        };
        git(&repository, &["init", "-q", "-b", "main"]);
        git(&repository, &["config", "user.name", "Overscope Test"]);
        git(&repository, &["config", "user.email", "test@overscope.local"]);
        fs::write(repository.join("README.md"), "baseline\n").expect("baseline");
        git(&repository, &["add", "README.md"]);
        git(&repository, &["commit", "-qm", "baseline"]);
        let remote_text = remote.to_string_lossy().into_owned();
        git(&root, &["init", "-q", "--bare", &remote_text]);
        git(&repository, &["remote", "add", "origin", &remote_text]);
        git(&repository, &["push", "-q", "-u", "origin", "main"]);

        fs::write(repository.join("README.md"), "baseline\nnext\n").expect("change");
        git(&repository, &["add", "README.md"]);
        git(&repository, &["commit", "-qm", "next"]);
        let before = read_repository_status(&repository).expect("status before push");
        assert_eq!(before.ahead, 1);
        assert_eq!(before.behind, 0);
        assert_eq!(
            before.remote.as_ref().map(|item| item.transport.as_str()),
            Some("Local")
        );

        let result = execute_git_action(&repository, GitAction::Push).expect("local push");
        assert_eq!(result.status.ahead, 0);
        assert_eq!(result.message, "Pushed local commits");
        fs::remove_dir_all(root).expect("fixture cleanup");
    }
}
