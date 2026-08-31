mod backend;

use backend::{backend_status, retry_backend, BackendController};
use tauri::RunEvent;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let controller = BackendController::default();
    let setup_controller = controller.clone();
    let exit_controller = controller.clone();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .manage(controller)
        .invoke_handler(tauri::generate_handler![backend_status, retry_backend])
        .setup(move |app| {
            let app_handle = app.handle().clone();
            let controller = setup_controller.clone();
            tauri::async_runtime::spawn(async move {
                controller.ensure_started(&app_handle).await;
            });
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building tauri application");

    app.run(move |app_handle, event| {
        if let RunEvent::ExitRequested { api, code, .. } = event {
            if exit_controller.should_intercept_exit() {
                api.prevent_exit();
                let controller = exit_controller.clone();
                let app_handle = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    controller.shutdown().await;
                    app_handle.exit(code.unwrap_or(0));
                });
            }
        }
    });
}
