mod bridge;

use bridge::{ask_via_bridge, BridgeConfig};

#[tokio::main]
async fn main() {
    let prompt = std::env::args().skip(1).collect::<Vec<_>>().join(" ");
    let cfg = BridgeConfig::new(
        std::env::var("BRIDGE_CMD").unwrap_or_default(),
        std::env::var("BRIDGE_TIMEOUT_MS")
            .ok()
            .and_then(|ms| ms.parse::<u64>().ok())
            .unwrap_or(30_000),
    );

    match ask_via_bridge(&prompt, &cfg).await {
        Ok(answer) => println!("{answer}"),
        Err(err) => {
            eprintln!("Bridge error: {err}");
            std::process::exit(1);
        }
    }
}
