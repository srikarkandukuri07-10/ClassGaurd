use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use tauri::Emitter;
use tauri::AppHandle;
use tungstenite::{connect, Message};

pub fn run_forever(
    ws_url: &str,
    _http_url: &str,
    _device_token: &str,
    app_handle: &AppHandle,
    running: &Arc<AtomicBool>,
    monitoring_active: &Arc<AtomicBool>,
) {
    let app = app_handle.clone();
    let wu = ws_url.to_string();
    let r = running.clone();
    let ma = monitoring_active.clone();

    thread::spawn(move || {
        while r.load(Ordering::SeqCst) {
            match connect(&wu) {
                Ok((mut socket, _)) => {
                    println!("[WS] Connected");

                    let _ = app.emit("connection_state", serde_json::json!({ "connected": true }));

                    loop {
                        if !r.load(Ordering::SeqCst) {
                            break;
                        }

                        match socket.read() {
                            Ok(Message::Text(text)) => {
                                if let Ok(msg) = serde_json::from_str::<serde_json::Value>(&text) {
                                    let event = msg["event"].as_str().unwrap_or("");
                                    let data = msg.get("data");

                                    match event {
                                        "monitoring_started" => {
                                            ma.store(true, Ordering::SeqCst);
                                            let _ = app.emit("monitoring_state", serde_json::json!({ "active": true }));
                                            let _ = app.emit("monitoring_paused", serde_json::json!({ "paused": false, "reason": "" }));
                                        }
                                        "monitoring_stopped" => {
                                            ma.store(false, Ordering::SeqCst);
                                            let _ = app.emit("monitoring_state", serde_json::json!({ "active": false }));
                                            let _ = app.emit("monitoring_paused", serde_json::json!({ "paused": false, "reason": "" }));
                                        }
                                        "monitoring_paused" => {
                                            ma.store(false, Ordering::SeqCst);
                                            let reason = data.and_then(|d| d.get("reason")).and_then(|v| v.as_str()).unwrap_or("");
                                            let _ = app.emit("monitoring_paused", serde_json::json!({ "paused": true, "reason": reason }));
                                            let _ = crate::notifications::send_monitoring_paused(reason);
                                        }
                                        "warning" => {
                                            if let Some(d) = data {
                                                let level = d.get("level").and_then(|v| v.as_u64()).unwrap_or(1);
                                                let message = d.get("message").and_then(|v| v.as_str()).unwrap_or("");
                                                let _ = app.emit("warning", serde_json::json!({
                                                    "level": level,
                                                    "message": message,
                                                    "reason": d.get("reason").and_then(|v| v.as_str()).unwrap_or(""),
                                                }));
                                                let _ = crate::notifications::send_warning(level as u32);
                                            }
                                        }
                                        _ => {}
                                    }
                                }
                            }
                            Ok(Message::Close(_)) => {
                                println!("[WS] Server closed connection");
                                break;
                            }
                            Err(_e) => {
                                eprintln!("[WS] Read error");
                                break;
                            }
                            _ => {}
                        }
                    }
                }
                Err(e) => {
                    eprintln!("[WS] Connection failed: {}", e);
                    thread::sleep(Duration::from_secs(5));
                }
            }

            if !r.load(Ordering::SeqCst) {
                break;
            }
            thread::sleep(Duration::from_secs(3));
        }
    });
}
