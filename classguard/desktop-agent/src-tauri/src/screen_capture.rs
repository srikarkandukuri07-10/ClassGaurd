use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::thread;
use std::time::Duration;
use tauri::AppHandle;
use screenshots::Screen;
use image::ImageOutputFormat;
use base64::{engine::general_purpose, Engine as _};
use std::io::Cursor;

fn capture_screen_base64() -> Option<String> {
    let screens = Screen::all().ok()?;
    let screen = screens.first()?;
    let image = screen.capture().ok()?;

    // Resize to 960x540 to minimise bandwidth
    let dynamic_img = image::DynamicImage::ImageRgba8(image);
    let resized = dynamic_img.resize(960, 540, image::imageops::FilterType::Triangle);

    let mut buffer = Vec::new();
    let mut cursor = Cursor::new(&mut buffer);
    resized.write_to(&mut cursor, ImageOutputFormat::Jpeg(55)).ok()?;

    Some(general_purpose::STANDARD.encode(buffer))
}

pub fn run_forever(
    server_url: &str,
    device_token: &str,
    _app_handle: &AppHandle,
    running: &Arc<AtomicBool>,
    monitoring_active: &Arc<AtomicBool>,
) {
    // Wait briefly so the WebSocket connection can establish first
    thread::sleep(Duration::from_secs(5));

    let scheme_ws = if server_url.contains("localhost") || server_url.contains("127.0.0.1") { "ws" } else { "wss" };
    let ws_url = format!("{}://{}/ws/agent?device_token={}", scheme_ws, server_url, device_token);

    let r = running.clone();
    let ma = monitoring_active.clone();
    let wu = ws_url.clone();

    thread::spawn(move || {
        while r.load(Ordering::SeqCst) {
            if !ma.load(Ordering::SeqCst) {
                thread::sleep(Duration::from_secs(2));
                continue;
            }

            let title = get_active_window_title();
            let screenshot = capture_screen_base64();

            if title.is_empty() && screenshot.is_none() {
                thread::sleep(Duration::from_secs(5));
                continue;
            }

            // Send as screen_frame over WebSocket
            match tungstenite::connect(&wu) {
                Ok((mut socket, _)) => {
                    let msg = serde_json::json!({
                        "event": "screen_frame",
                        "window_title": title,
                        "screenshot": screenshot,
                    });
                    let _ = socket.send(tungstenite::Message::Text(msg.to_string()));
                    let _ = socket.close(None);
                }
                Err(e) => {
                    eprintln!("[ScreenCapture] WS send failed: {}", e);
                }
            }

            thread::sleep(Duration::from_secs(5));
        }
    });
}

fn get_active_window_title() -> String {
    unsafe {
        let hwnd = winapi::um::winuser::GetForegroundWindow();
        if hwnd.is_null() {
            return String::new();
        }
        let length = winapi::um::winuser::GetWindowTextLengthW(hwnd) + 1;
        let mut buf: Vec<u16> = vec![0; length as usize];
        let len = winapi::um::winuser::GetWindowTextW(hwnd, buf.as_mut_ptr(), length);
        if len > 0 {
            String::from_utf16_lossy(&buf[..len as usize])
        } else {
            String::new()
        }
    }
}
