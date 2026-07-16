use notify_rust::Notification;

pub fn init() -> bool {
    true
}

pub fn send_warning(level: u32) {
    let (summary, body) = match level {
        1 => ("ClassGuard: Warning", "You appear to be off-task. Please return to your studies."),
        2 => ("ClassGuard: Warning", "Second warning. Please return to class activities."),
        3 => ("ClassGuard: Warning", "Final warning. Faculty has been notified."),
        _ => ("ClassGuard: Warning", "Final warning. Faculty has been notified."),
    };
    let _ = Notification::new()
        .summary(summary)
        .body(body)
        .appname("ClassGuard")
        .timeout(10000)
        .show();
}

pub fn send_monitoring_paused(reason: &str) {
    let _ = Notification::new()
        .summary("ClassGuard: Monitoring Paused")
        .body(&format!("Reason: {}", reason))
        .appname("ClassGuard")
        .timeout(10000)
        .show();
}
