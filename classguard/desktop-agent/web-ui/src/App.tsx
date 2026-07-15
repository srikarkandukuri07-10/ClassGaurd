import { useState, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import SetupView from "./SetupView";
import DashboardView from "./DashboardView";

interface StudentInfo {
  student_name: string;
  section: string;
  device_token: string;
  monitoring_enabled: boolean;
  monitoring_paused: boolean;
}

interface WarningEvent {
  level: number;
  message: string;
  reason: string;
}

export type ViewState = "loading" | "setup" | "dashboard";

function App() {
  const [view, setView] = useState<ViewState>("loading");
  const [student, setStudent] = useState<StudentInfo | null>(null);
  const [monitoringActive, setMonitoringActive] = useState(false);
  const [monitoringPaused, setMonitoringPaused] = useState(false);
  const [warnings, setWarnings] = useState<WarningEvent[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    const setup = async () => {
      try {
        const info = await invoke<StudentInfo | null>("check_token");
        if (info) {
          setStudent(info);
          setMonitoringActive(info.monitoring_enabled);
          setMonitoringPaused(info.monitoring_paused);
          setView("dashboard");
        } else {
          setView("setup");
        }
      } catch {
        setView("setup");
      }
    };
    setup();
  }, []);

  useEffect(() => {
    const unsub1 = listen<{ active: boolean }>("monitoring_state", (e) => {
      setMonitoringActive(e.payload.active);
    });
    const unsub2 = listen<WarningEvent>("warning", (e) => {
      setWarnings((prev) => [e.payload, ...prev].slice(0, 20));
    });
    const unsub3 = listen<{ paused: boolean }>("monitoring_paused", (e) => {
      setMonitoringPaused(e.payload.paused);
    });
    return () => {
      unsub1.then((f) => f());
      unsub2.then((f) => f());
      unsub3.then((f) => f());
    };
  }, []);

  const handleConnect = async (code: string, serverUrl: string) => {
    setError("");
    try {
      const info = await invoke<StudentInfo>("link_device", {
        code: code.toUpperCase(),
        serverUrl,
      });
      setStudent(info);
      setMonitoringActive(info.monitoring_enabled);
      setMonitoringPaused(info.monitoring_paused);
      setView("dashboard");
    } catch (e: any) {
      setError(typeof e === "string" ? e : e.message || "Connection failed");
    }
  };

  const handleDisconnect = async () => {
    await invoke("disconnect");
    setStudent(null);
    setMonitoringActive(false);
    setMonitoringPaused(false);
    setWarnings([]);
    setView("setup");
  };

  const handleRequestPause = async (reason: string) => {
    await invoke("request_pause", { reason });
  };

  if (view === "loading") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="text-center">
          <div className="w-10 h-10 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-500">Starting ClassGuard...</p>
        </div>
      </div>
    );
  }

  if (view === "setup") {
    return <SetupView onConnect={handleConnect} error={error} />;
  }

  return (
    <DashboardView
      student={student!}
      monitoringActive={monitoringActive}
      monitoringPaused={monitoringPaused}
      warnings={warnings}
      onDisconnect={handleDisconnect}
      onRequestPause={handleRequestPause}
    />
  );
}

export default App;
