use wrapper_service::{app_state_from_env, build_app, run_server, server_port_from_env};

#[tokio::main]
async fn main() {
    let state = app_state_from_env();
    let app = build_app(state);
    let port = server_port_from_env();

    run_server(app, port).await;
}
