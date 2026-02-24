use std::env;

pub struct AppConfig {
    port: u16,
    bridge_cmd: String,
    timeout_ms: u64,
}

impl AppConfig {
    pub fn from_env() -> Self {
        let port = env::var("PORT")
            .ok()
            .and_then(|value| value.parse::<u16>().ok())
            .unwrap_or(8080);

        let bridge_cmd = env::var("BRIDGE_CMD").unwrap_or_else(|_| "bridge".to_string());

        let timeout_ms = env::var("TIMEOUT_MS")
            .ok()
            .and_then(|value| value.parse::<u64>().ok())
            .unwrap_or(30_000);

        Self {
            port,
            bridge_cmd,
            timeout_ms,
        }
    }
}
