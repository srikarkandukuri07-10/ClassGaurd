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
    capture_interval: &Arc<std::sync::atomic::AtomicU32>,
) {
    // Wait for ws_client to establish its connection first
    thread::sleep(Duration::from_secs(5));

    let scheme = if server_url.contains("localhost") || server_url.contains("127.0.0.1") { "http" } else { "https" };
    let classify_url = format!("{}://{}/api/ai/classify", scheme, server_url);
    let dt = device_token.to_string();

    let r  = running.clone();
    let ma = monitoring_active.clone();
    let cap_int = capture_interval.clone();

    thread::spawn(move || {
        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(20))
            .build()
            .unwrap_or_default();

        while r.load(Ordering::SeqCst) {
            if !ma.load(Ordering::SeqCst) {
                thread::sleep(Duration::from_secs(2));
                continue;
            }

            let title      = get_active_window_title();
            let screenshot = capture_screen_base64();

            if screenshot.is_some() {
                println!("[DEBUG] Screenshot captured successfully");
            } else {
                println!("[DEBUG] Screenshot capture failed or skipped");
            }

            if title.is_empty() && screenshot.is_none() {
                let interval_sec = cap_int.load(Ordering::SeqCst) as u64;
                thread::sleep(Duration::from_secs(interval_sec));
                continue;
            }

            let frame_body = serde_json::json!({
                "device_id":    dt,
                "window_title": title,
                "image":        screenshot,
            });

            match client.post(&classify_url).json(&frame_body).send() {
                Ok(resp) => {
                    if resp.status().is_success() {
                        println!("[DEBUG] Screen frame uploaded successfully for window: '{}'", title);
                    } else {
                        println!("[DEBUG] Screen frame upload returned status: {}", resp.status());
                    }
                }
                Err(e) => {
                    println!("[DEBUG] Failed to upload screen frame: {}", e);
                }
            }

            let interval_sec = cap_int.load(Ordering::SeqCst) as u64;
            thread::sleep(Duration::from_secs(interval_sec));
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
