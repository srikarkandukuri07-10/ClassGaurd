#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::menu::{MenuBuilder, MenuItemBuilder, PredefinedMenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{Emitter, Manager};

mod commands;
mod notifications;
mod screen_capture;
mod ws_client;

struct AppState {
    device_token: Arc<Mutex<Option<String>>>,
    server_url: Arc<Mutex<String>>,
    monitoring_active: Arc<AtomicBool>,
    running: Arc<AtomicBool>,
}

fn main() {
    let _notif = notifications::init();

    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .manage(AppState {
            device_token: Arc::new(Mutex::new(None)),
            server_url: Arc::new(Mutex::new("classguard-backend.onrender.com".to_string())),
            monitoring_active: Arc::new(AtomicBool::new(false)),
            running: Arc::new(AtomicBool::new(true)),
        })
        .setup(|app| {
            let show = MenuItemBuilder::with_id("show", "Show Window").build(app)?;
            let disconnect = MenuItemBuilder::with_id("disconnect", "Disconnect").build(app)?;
            let quit = MenuItemBuilder::with_id("quit", "Quit").build(app)?;
            let separator = PredefinedMenuItem::separator(app)?;

            let menu = MenuBuilder::new(app)
                .item(&show)
                .item(&disconnect)
                .item(&separator)
                .item(&quit)
                .build()?;

            let _tray = TrayIconBuilder::new()
                .icon(app.default_window_icon().unwrap().clone())
                .menu(&menu)
                .on_menu_event(move |app, event| match event.id().as_ref() {
                    "show" => {
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                    "disconnect" => {
                        let state = app.state::<AppState>();
                        if let Ok(mut token) = state.device_token.lock() {
                            *token = None;
                        }
                        commands::clear_token_file();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.close();
                        }
                        std::process::exit(0);
                    }
                    "quit" => {
                        std::process::exit(0);
                    }
                    _ => {}
                })
                .on_tray_icon_event(|tray, event| {
                    if let TrayIconEvent::Click {
                        button: MouseButton::Left,
                        button_state: MouseButtonState::Up,
                        ..
                    } = event
                    {
                        let app = tray.app_handle();
                        if let Some(window) = app.get_webview_window("main") {
                            let _ = window.show();
                            let _ = window.set_focus();
                        }
                    }
                })
                .build(app)?;

            Ok(())
        })
        .on_window_event(|window, event| {
            if let tauri::WindowEvent::CloseRequested { api, .. } = event {
                api.prevent_close();
                let _ = window.hide();
            }
        })
        .invoke_handler(tauri::generate_handler![
            commands::check_token,
            commands::link_device,
            commands::disconnect,
            commands::request_pause,
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
