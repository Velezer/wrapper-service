use std::{env, net::SocketAddr};

use tokio::net::TcpListener;

mod api;

#[derive(Clone)]
pub struct AppState {
    model_name: String,
}

struct Config {
    host: String,
    port: u16,
    model_name: String,
}

impl Config {
    fn from_env() -> Self {
        let host = env::var("HOST").unwrap_or_else(|_| "0.0.0.0".to_string());
        let port = env::var("PORT")
            .ok()
            .and_then(|raw| raw.parse::<u16>().ok())
            .unwrap_or(3000);
        let model_name = env::var("MODEL_NAME").unwrap_or_else(|_| "default-model".to_string());

        Self {
            host,
            port,
            model_name,
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    dotenvy::dotenv().ok();

    let config = Config::from_env();
    let state = AppState {
        model_name: config.model_name,
    };

    let app = api::router(state);

    let addr: SocketAddr = format!("{}:{}", config.host, config.port).parse()?;
    let listener = TcpListener::bind(addr).await?;

    axum::serve(listener, app).await?;

    Ok(())
}
