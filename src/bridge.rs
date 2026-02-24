use std::error::Error;
use std::fmt;

use tokio::process::Command;
use tokio::time::{timeout, Duration};

pub struct BridgeConfig {
    bridge_cmd: String,
    timeout_ms: u64,
}

impl BridgeConfig {
    pub fn new(bridge_cmd: impl Into<String>, timeout_ms: u64) -> Self {
        Self {
            bridge_cmd: bridge_cmd.into(),
            timeout_ms,
        }
    }
}

#[derive(Debug)]
pub enum BridgeError {
    MissingCommand,
    Timeout,
    SpawnFailure(std::io::Error),
    NonZeroExit { code: Option<i32>, stderr: String },
    EmptyOutput,
}

impl fmt::Display for BridgeError {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Self::MissingCommand => write!(f, "bridge command is missing"),
            Self::Timeout => write!(f, "bridge command timed out"),
            Self::SpawnFailure(err) => write!(f, "failed to execute bridge command: {err}"),
            Self::NonZeroExit { code, stderr } => {
                write!(f, "bridge command exited with code {:?}: {}", code, stderr)
            }
            Self::EmptyOutput => write!(f, "bridge command produced empty output"),
        }
    }
}

impl Error for BridgeError {
    fn source(&self) -> Option<&(dyn Error + 'static)> {
        match self {
            Self::SpawnFailure(err) => Some(err),
            _ => None,
        }
    }
}

pub async fn ask_via_bridge(prompt: &str, cfg: &BridgeConfig) -> Result<String, BridgeError> {
    if cfg.bridge_cmd.trim().is_empty() {
        return Err(BridgeError::MissingCommand);
    }

    let mut cmd = Command::new("sh");
    cmd.arg("-c").arg(&cfg.bridge_cmd);
    cmd.env("BRIDGE_PROMPT", prompt);

    let output = timeout(Duration::from_millis(cfg.timeout_ms), cmd.output())
        .await
        .map_err(|_| BridgeError::Timeout)?
        .map_err(BridgeError::SpawnFailure)?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
        return Err(BridgeError::NonZeroExit {
            code: output.status.code(),
            stderr,
        });
    }

    let stdout = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if stdout.is_empty() {
        return Err(BridgeError::EmptyOutput);
    }

    Ok(stdout)
}
