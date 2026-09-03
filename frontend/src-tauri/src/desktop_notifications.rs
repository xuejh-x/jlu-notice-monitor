use tauri::{AppHandle, Emitter, Manager};

const MAX_TITLE_CHARS: usize = 200;
const MAX_BODY_CHARS: usize = 500;

fn valid_notification_route(route: &str) -> bool {
    if matches!(route, "/notices" | "/deadlines" | "/sources") {
        return true;
    }
    route.strip_prefix("/notices/").is_some_and(|id| {
        !id.is_empty() && !id.starts_with('0') && id.chars().all(|c| c.is_ascii_digit())
    })
}

fn validate_notification(title: &str, body: &str, route: &str) -> Result<(), String> {
    if title.trim().is_empty() || title.chars().count() > MAX_TITLE_CHARS {
        return Err("notification title is empty or too long".into());
    }
    if body.chars().count() > MAX_BODY_CHARS {
        return Err("notification body is too long".into());
    }
    if !valid_notification_route(route) {
        return Err("notification route is not allowed".into());
    }
    Ok(())
}

fn activate_route(app: &AppHandle, route: &str) -> Result<(), String> {
    if !valid_notification_route(route) {
        return Err("notification route is not allowed".into());
    }
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
    app.emit("notification-route", route)
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn show_windows_notification(
    app: AppHandle,
    title: String,
    body: String,
    route: String,
) -> Result<(), String> {
    validate_notification(&title, &body, &route)?;

    #[cfg(target_os = "windows")]
    {
        use tauri_winrt_notification::Toast;

        let app_id = if tauri::is_dev() {
            Toast::POWERSHELL_APP_ID.to_owned()
        } else {
            app.config().identifier.clone()
        };
        let activation_app = app.clone();
        let activation_route = route.clone();
        Toast::new(&app_id)
            .title(&title)
            .text1(&body)
            .add_button("查看", "open")
            .on_activated(move |_| {
                let _ = activate_route(&activation_app, &activation_route);
                Ok(())
            })
            .show()
            .map_err(|error| error.to_string())?;
    }

    #[cfg(not(target_os = "windows"))]
    {
        use tauri_plugin_notification::NotificationExt;
        app.notification()
            .builder()
            .title(title)
            .body(body)
            .show()
            .map_err(|error| error.to_string())?;
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::{valid_notification_route, validate_notification};

    #[test]
    fn notification_routes_are_internal_and_specific() {
        for route in [
            "/notices/1",
            "/notices/42",
            "/notices",
            "/deadlines",
            "/sources",
        ] {
            assert!(valid_notification_route(route));
        }
        for route in [
            "/notices/0",
            "/notices/nope",
            "https://example.test",
            "//example.test",
        ] {
            assert!(!valid_notification_route(route));
        }
    }

    #[test]
    fn notification_payload_is_bounded() {
        assert!(validate_notification("提醒", "正文", "/notices/1").is_ok());
        assert!(validate_notification("", "正文", "/notices/1").is_err());
        assert!(validate_notification(&"题".repeat(201), "正文", "/notices/1").is_err());
        assert!(validate_notification("提醒", &"文".repeat(501), "/notices/1").is_err());
    }
}
